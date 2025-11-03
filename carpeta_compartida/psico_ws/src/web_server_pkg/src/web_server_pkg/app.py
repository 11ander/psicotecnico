#!/usr/bin/env python3
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# ==== ROS (ROS1 Noetic) ====
import rospy
import actionlib
from rpi_pkg.msg import MemoriaAction, MemoriaGoal, ReflejosAction, ReflejosGoal

# Face recognition action (ya lo tienes corriendo en otra terminal)
from roslib.message import get_message_class

from speak_api import TiagoSpeaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_change_me")

# ------------------- Estado en memoria -------------------
SESION = {
    "ejecutando": False,
    "pruebas_completadas": [],
    "resultados": [],          # [{prueba, puntuacion, hora}]
    "paciente": {}             # {nombre, ...} (libre)
}
REGISTRO = []                 # logs en vivo
HISTORICO = []                # sesiones anteriores

def registrar(mensaje: str):
    hora = datetime.now().strftime("%H:%M:%S")
    entrada = f"[{hora}] {mensaje}"
    REGISTRO.append(entrada)
    print(entrada, flush=True)

# ------------------- ROS init -------------------
if not rospy.core.is_initialized():
    rospy.init_node('puente_web_ros', anonymous=True, disable_signals=True)

# Instancia del speaker 
speaker = TiagoSpeaker(prefer_pal_tts=True)


# ------------------- Face recognition (cliente Action) -------------------
FACE_ACTION_SPEC = "face_recognition_pkg/FaceRecognitionAction"
FACE_SERVER_NAME = "face_recognition_action"

def face_login(max_minutes: float = 20.0) -> Optional[str]:
    """
    Espera indefinidamente a que el servidor de reconocimiento facial devuelva un nombre,
    con un límite máximo de `max_minutes`. Si no se reconoce a nadie, devuelve None.
    """
    action_cls = get_message_class(FACE_ACTION_SPEC)
    if action_cls is None:
        raise RuntimeError(f"No se pudo cargar la Action '{FACE_ACTION_SPEC}'. ¿Está compilada?")

    goal_cls = get_message_class(FACE_ACTION_SPEC.replace("Action", "Goal"))
    if goal_cls is None:
        raise RuntimeError(f"No se pudo derivar Goal para '{FACE_ACTION_SPEC}'.")

    client = actionlib.SimpleActionClient(FACE_SERVER_NAME, action_cls)
    if not client.wait_for_server(rospy.Duration(10.0)):
        raise RuntimeError(f"Action server '{FACE_SERVER_NAME}' no disponible.")

    goal = goal_cls()
    if not hasattr(goal, "ejecutar"):
        raise RuntimeError("El Goal de FaceRecognition no tiene campo 'ejecutar'.")
    goal.ejecutar = True

    # Enviamos UNA vez el goal; el servidor termina cuando reconoce a alguien
    client.send_goal(goal)

    start = rospy.Time.now()
    check_step = rospy.Duration(2.0)  # re-chequeo cada 2 s sin bloquear
    limit = rospy.Duration(max_minutes * 60.0)

    registrar("Login: colócate frente a la cámara del TIAGo, mira al objetivo y mantén la cara iluminada.")

    while not rospy.is_shutdown():
        # Espera 'check_step'; si acaba antes porque hay resultado, devolvemos nombre
        if client.wait_for_result(check_step):
            result = client.get_result()
            if result:
                nombre = (getattr(result, "nombre", "") or "").strip()
                if nombre:
                    registrar(f"Login: reconocido '{nombre}'.")
                    return nombre
            # Si por alguna razón vuelve sin nombre, reenvía el goal
            client.send_goal(goal)

        # ¿Se superó el límite?
        if (rospy.Time.now() - start) > limit:
            try:
                client.cancel_goal()
            except Exception:
                pass
            registrar("Login: 20 minutos sin reconocimiento. Revisa iluminación/encuadre.")
            return None


# ------------------- Acciones de rpi_pkg -------------------
def ejecutar_prueba_memoria() -> float:
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

def ejecutar_prueba_reflejos() -> float:
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

# ------------------- Rutas -------------------
def require_login():
    if not session.get("user"):
        return False
    return True

@app.route("/")
def inicio():
    # Si no has hecho login (reconocimiento facial), pide login
    if not require_login():
        return redirect(url_for("login"))
    return render_template("index.html")  # tu panel actual

# ---- Login por reconocimiento facial ----
@app.route("/login", methods=["GET"])
def login():
    if session.get("user"):
        return redirect(url_for("inicio"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    try:
        nombre = face_login(max_minutes=20.0)
        if not nombre:
            return jsonify(
                ok=False,
                error=(
                    "No se reconoció ningún rostro en 20 minutos. "
                    "Acerca el rostro a cámara, mira al objetivo y mejora la iluminación de la sala."
                )
            )
        session["user"] = nombre

        # Mensaje de bienvenida con TTS (no bloquea la respuesta HTTP)
        try:
            speaker.speak_async(f"Bienvenido {nombre} a la consulta, pase por aquí", lang_id="es_ES")
        except Exception as e:
            registrar(f"TTS error al saludar: {e}")


        return jsonify(ok=True, user=nombre)
    except Exception as e:
        return jsonify(ok=False, error=str(e))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---- API existente (protegemos por login) ----
@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/start", methods=["POST"])
def iniciar_pruebas():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401

    datos: Dict[str, Any] = request.get_json(force=True)
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
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401
    return jsonify(estado=SESION, registro=REGISTRO)

@app.route("/history")
def obtener_historial():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401
    return jsonify(filas=HISTORICO)

@app.route("/history/clear", methods=["POST"])
def limpiar_historial():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401
    HISTORICO.clear()
    return jsonify(ok=True)

# ------------------- Main -------------------
if __name__ == "__main__":
    # Recuerda lanzar antes el action server de reconocimiento facial
    # rosrun face_recognition_pkg recognize_action_server.py _db_path:=package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
