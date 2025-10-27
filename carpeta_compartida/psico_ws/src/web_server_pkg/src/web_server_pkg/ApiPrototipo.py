#!/usr/bin/env python3
import os
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import rospy
import actionlib
from rpi_pkg.msg import MemoriaAction, MemoriaGoal, ReflejosAction, ReflejosGoal

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

rospy.init_node('puente_web_ros', anonymous=True)

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
            elif id_prueba == "reflejos":
                puntuacion = ejecutar_prueba_reflejos()
            else:
                puntuacion = None

            ahora = datetime.now()
            SESION["pruebas_completadas"].append(id_prueba)
            SESION["resultados"].append({
                "prueba": id_prueba,
                "puntuacion": puntuacion,
                "hora": ahora.strftime("%H:%M:%S")
            })

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
