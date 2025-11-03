#!/usr/bin/env python3
import os
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import rospy
import actionlib

from rpi_pkg.msg import MemoriaAction, MemoriaGoal, ReflejosAction, ReflejosGoal
from audicion_pkg.msg import AudicionAction, AudicionGoal  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

SESION = {
    "ejecutando": False,
    "pruebas_completadas": [],
    "resultados": [],         
    "paciente": {}
}
REGISTRO = []
HISTORICO = []

def registrar(mensaje: str):
    hora = datetime.now().strftime("%H:%M:%S")
    entrada = f"[{hora}] {mensaje}"
    REGISTRO.append(entrada)
    print(entrada, flush=True)

rospy.init_node('puente_web_ros', anonymous=True, disable_signals=True)

def ejecutar_prueba_memoria():
    registrar("Enviando objetivo a /memoria...")
    cliente = actionlib.SimpleActionClient('memoria', MemoriaAction)
    if not cliente.wait_for_server(timeout=rospy.Duration(5.0)):
        registrar("ERROR: El servidor de acción 'memoria' no está disponible.")
        return -1.0
    objetivo = MemoriaGoal(input=True)
    cliente.send_goal(objetivo)
    cliente.wait_for_result(rospy.Duration(60.0))
    resultado = cliente.get_result()
    puntuacion = resultado.result if resultado else -1.0
    registrar(f"Prueba de memoria finalizada. Puntuación: {puntuacion}")
    return puntuacion

def ejecutar_prueba_reflejos():
    registrar("Enviando objetivo a /reflejos...")
    cliente = actionlib.SimpleActionClient('reflejos', ReflejosAction)
    if not cliente.wait_for_server(timeout=rospy.Duration(5.0)):
        registrar("ERROR: El servidor de acción 'reflejos' no está disponible.")
        return -1.0
    objetivo = ReflejosGoal(input=True)
    cliente.send_goal(objetivo)
    cliente.wait_for_result(rospy.Duration(60.0))
    resultado = cliente.get_result()
    puntuacion = resultado.result if resultado else -1.0
    registrar(f"Prueba de reflejos finalizada. Puntuación: {puntuacion}")
    return puntuacion

def ejecutar_prueba_audicion():
    registrar("Enviando objetivo a /audicion_action...")
    cliente = actionlib.SimpleActionClient('audicion_action', AudicionAction)
    if not cliente.wait_for_server(timeout=rospy.Duration(5.0)):
        registrar("ERROR: El servidor de acción 'audicion_action' no está disponible.")
        return None

    try:
        objetivo = AudicionGoal()
        if hasattr(objetivo, "ejecutar"):
            objetivo.ejecutar = True
    except Exception:
        objetivo = None

    cliente.send_goal(objetivo)
    cliente.wait_for_result(rospy.Duration(180.0))
    resultado = cliente.get_result()

    if not resultado:
        registrar("ERROR: No se recibió result en audición.")
        return None

    try:
        p1_total, p2_total, p2_aciertos, p2_fallos = list(resultado.resultados)
    except Exception as e:
        registrar(f"ERROR: Formato de resultado inesperado en audición: {e}")
        return None

    registrar(f"Audición OK → (devuelto) P1_total={p1_total} | P2_total={p2_total} | P2_aciertos={p2_aciertos} | P2_fallos={p2_fallos}")


    puls_emitidos = int(p2_total)
    puls_aciertos = int(p2_aciertos)
    puls_fallos   = int(p2_fallos)
    conteo_emitidos = int(p1_total)

    puls_emitidos_safe = max(1, puls_emitidos)
    nota_p1 = round(10.0 * (puls_aciertos / puls_emitidos_safe), 2)

    detalles = {
        "pulsador_emitidos": puls_emitidos,
        "pulsador_aciertos": puls_aciertos,
        "pulsador_fallos":   puls_fallos,
        "nota_p1": float(nota_p1),

        "conteo_emitidos": conteo_emitidos,  
        "requiere_input": True,
        "input_schema": {
            "titulo": "Audición – Respuesta del paciente (P2: Conteo)",
            "descripcion": "Introduce cuántos pitidos dijo haber escuchado el paciente en la PRUEBA 2 (conteo).",
            "campos": [
                {"name": "p2_contados_paciente", "label": "¿Cuántos pitidos escuchaste en la PRUEBA 2?", "type": "number", "min": 0}
            ]
        }
    }
    return detalles

@app.route("/")
def inicio():
    return render_template("indexPrototipo.html")

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/start", methods=["POST"])
def iniciar_pruebas():
    datos = request.get_json(force=True)
    secuencia_pruebas = datos.get("order", [])
    info_paciente = datos.get("patient", {})

    REGISTRO.clear()
    SESION.update({
        "ejecutando": True,
        "pruebas_completadas": [],
        "resultados": [],
        "paciente": info_paciente
    })

    def trabajador_fondo():
        for id_prueba in secuencia_pruebas:
            if id_prueba == "memoria":
                puntuacion = ejecutar_prueba_memoria()
                payload = {"prueba": id_prueba, "puntuacion": puntuacion, "hora": datetime.now().strftime("%H:%M:%S")}

            elif id_prueba == "reflejos":
                puntuacion = ejecutar_prueba_reflejos()
                payload = {"prueba": id_prueba, "puntuacion": puntuacion, "hora": datetime.now().strftime("%H:%M:%S")}

            elif id_prueba == "audicion":
                detalles = ejecutar_prueba_audicion()
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": None, 
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "detalles": detalles or {},
                }
            else:
                payload = {"prueba": id_prueba, "puntuacion": None, "hora": datetime.now().strftime("%H:%M:%S")}

            SESION["pruebas_completadas"].append(id_prueba)
            SESION["resultados"].append(payload)

        SESION["ejecutando"] = False
        ts = datetime.now()
        HISTORICO.append({
            "fecha": ts.strftime("%Y-%m-%d"),
            "hora":  ts.strftime("%H:%M:%S"),
            "paciente": dict(SESION.get("paciente", {})),
            "pruebas": list(SESION.get("resultados", []))
        })

    threading.Thread(target=trabajador_fondo, daemon=True).start()
    return jsonify(ok=True)

@app.route("/status")
def obtener_estado():
    return jsonify(estado=SESION, registro=REGISTRO)

@app.route("/history")
def obtener_historial():
    return jsonify(filas=HISTORICO)

@app.route("/history/clear", methods=["POST"])
def limpiar_historial():
    HISTORICO.clear()
    return jsonify(ok=True)

@app.route("/answer", methods=["POST"])
def responder_resultado():
    datos = request.get_json(force=True)
    idx = datos.get("index", None)
    values = datos.get("values", {})

    if idx is None or not isinstance(idx, int):
        return jsonify(ok=False, error="index inválido"), 400

    try:
        item = SESION["resultados"][idx]
    except Exception:
        return jsonify(ok=False, error="índice fuera de rango"), 404

    item["respuesta_usuario"] = values
    try:
        if item.get("prueba") == "audicion":
            det = item.get("detalles", {}) or {}
            emitidos_p2 = int(det.get("conteo_emitidos", 0))
            contado_p2  = int(values.get("p2_contados_paciente", -1))

            aciertos_p2_inf = max(0, emitidos_p2 - abs(emitidos_p2 - contado_p2))
            emitidos_p2_safe = max(1, emitidos_p2)
            nota_p2 = round(10.0 * (aciertos_p2_inf / emitidos_p2_safe), 2)

            det["p2_contados_paciente"] = contado_p2
            det["p2_aciertos_inferidos"] = int(aciertos_p2_inf)
            det["nota_p2"] = float(nota_p2)

            if "nota_p1" in det:
                try:
                    item["puntuacion"] = round((float(det["nota_p1"]) + float(det["nota_p2"])) / 2.0, 2)
                except Exception:
                    item["puntuacion"] = det.get("nota_p2", None)
            else:
                item["puntuacion"] = det.get("nota_p2", None)

            item["detalles"] = det

    except Exception as e:
        registrar(f"ERROR calculando notas de audición: {e}")

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
