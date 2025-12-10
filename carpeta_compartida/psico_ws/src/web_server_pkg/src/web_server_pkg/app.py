#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import random
import io
import csv
from pathlib import Path

import unicodedata
from difflib import SequenceMatcher

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    send_file,
)

# ==== ROS (ROS1 Noetic) ====
import rospy
import actionlib
from roslib.message import get_message_class

# ==== Import internos del paquete ====
# Modo 1: como paquete instalado (roslaunch / catkin)
# Modo 2 (fallback): ejecución directa desde src/web_server_pkg/src/web_server_pkg
try:
    from web_server_pkg.report import build_pdf_bytes
    from web_server_pkg.speak_api import TiagoSpeaker
    from web_server_pkg.pruebas_client import (
        MemoriaClient,
        ReflejosClient,
        AudicionClient,
        CoordinacionClient,
        VisionClient
    )
    from web_server_pkg.checkpoint_follower_api import Follower as CheckpointFollower
except ImportError:
    from report import build_pdf_bytes
    from speak_api import TiagoSpeaker
    from pruebas_client import (
        MemoriaClient,
        ReflejosClient,
        AudicionClient,
        CoordinacionClient,
        VisionClient
    )
    from checkpoint_follower_api import Follower as CheckpointFollower

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = Path(BASE_DIR) / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_CSV = DATA_DIR / "history.csv"

NO_LOGIN = "--no-login" in sys.argv
MUTE = ("--mute" in sys.argv) or (os.environ.get("PSICO_MUTE", "0") in ("1", "true", "True", "YES", "yes"))
NO_TEST = "--no-test" in sys.argv


app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_change_me")

# ------------------- Estado en memoria -------------------
SESION = {
    "ejecutando": False,
    "pruebas_completadas": [],  # lista de claves: ["memoria", "reflejos", ...]
    "resultados": [],           # [{prueba, puntuacion, hora, detalles?, respuesta_usuario?}]
    "paciente": {},             # {nombre: ...}
    "total_pruebas": 0,         # para progreso
    "current": "",              # clave de prueba en ejecución (para hint)
}
REGISTRO = []
HISTORICO = []

# --- Sincronización especial para Audición P2 ---
AUDICION_LOCK = threading.Lock()
AUDICION_EVENT = None      # type: Optional[threading.Event]
AUDICION_INDEX = None      # type: Optional[int]

# --- Sincronización especial para Visión (input de frases) ---
VISION_LOCK = threading.Lock()
VISION_EVENT = None        # type: Optional[threading.Event]
VISION_INDEX = None        # type: Optional[int]

# === Movilidad / checkpoints TIAGo ===
PREPROGRAMMED_POINTS = {
    "inicio":        [1.4998722751648397, -0.7247556435570256,  0.989510915323257,   0.14445812007682451],
    "puerta":        [-0.03339960212487537, -0.9941108864627621, 0.985343590657674,   0.17058138336243545],
    "mesa":          [3.672146707374831, -2.2359272006142015,  -0.6552174338382382,  0.7554403446960151],
    "vision1":       [2.9012330405494886, -1.293344511139235,  -0.4588533251208141,  0.888512029195763],
    "vision2":       [2.2037956776648566,  0.061978901102042926, -0.5214428312970412, 0.8532862202619502],
    "vision3":       [1.5780124426358513,  1.4079240508893582, -0.6134467796664745,  0.7897360625657358],
    "coordinacion":  [6.647815751420979, -2.0986998827950143,   0.9628602192184542,  0.27000036712306563],
}
_FOLLOWER = None
_FOLLOWER_LOCK = threading.Lock()

def get_follower() -> CheckpointFollower:
    global _FOLLOWER
    with _FOLLOWER_LOCK:
        if _FOLLOWER is None:
            registrar("Inicializando Follower de checkpoints…")
            _FOLLOWER = CheckpointFollower()
        return _FOLLOWER


def mover_robot_a_puerta_inicio():
    """
    Intenta mover al TIAGo a la puerta al arrancar el webserver,
    para que ya esté colocado cuando se haga el login por cara.
    """
    follower = get_follower()

    def _worker():
        import time

        # 1) Elegir coordenadas de la puerta
        try:
            if hasattr(follower, "punto_puerta"):
                coords = follower.punto_puerta
                registrar(f"Movilidad (inicio): usando follower.punto_puerta = {coords}")
            else:
                coords = PREPROGRAMMED_POINTS.get("puerta")
                registrar(f"Movilidad (inicio): usando PREPROGRAMMED_POINTS['puerta'] = {coords}")
        except Exception as e:
            registrar(f"ERROR obteniendo coordenadas de la puerta: {e}")
            return

        if not coords:
            registrar("Movilidad (inicio): no hay coordenadas definidas para 'puerta'.")
            return

        # 2) Intentar mover varias veces
        for intento in range(3):
            try:
                registrar("Movilidad (inicio): yendo a la puerta para el login…")
                ok = follower.enviar_puntos([coords])
                if ok:
                    registrar("Movilidad (inicio): robot colocado en la puerta, listo para el login.")
                    return
                else:
                    registrar(f"Movilidad (inicio): intento {intento+1} fallido al mover a la puerta. Reintentando...")
                    time.sleep(3.0)
            except Exception as e:
                registrar(f"ERROR moviendo el robot a la puerta al inicio: {e}")
                time.sleep(3.0)

        registrar("Movilidad (inicio): no se pudo colocar al robot en la puerta tras varios intentos.")

    threading.Thread(target=_worker, daemon=True).start()


def mover_robot_a_mesa_despues_login(nombre_paciente: str):
    """
    Tras un login correcto, mueve al robot a la mesa y le pide al paciente
    que se siente.
    """
    follower = get_follower()

    def _worker():
        import time

        # 1) Elegir coordenadas de la mesa
        try:
            if hasattr(follower, "punto_mesa"):
                coords = follower.punto_mesa
                registrar(f"Movilidad (login): usando follower.punto_mesa = {coords}")
            else:
                coords = PREPROGRAMMED_POINTS.get("medio")
                registrar(f"Movilidad (login): usando PREPROGRAMMED_POINTS['medio'] = {coords}")
        except Exception as e:
            registrar(f"ERROR obteniendo coordenadas de mesa tras login: {e}")
            return

        if not coords:
            registrar("Movilidad (login): no hay coordenadas definidas para la mesa.")
            return

        # 2) Intentar mover varias veces
        for intento in range(2):
            try:
                registrar("Movilidad (login): yendo a la mesa para comenzar las pruebas…")
                ok = follower.enviar_puntos([coords])
                if ok:
                    registrar("Movilidad (login): robot colocado en la mesa.")
                    # Pequeña pausa y mensaje al paciente
                    time.sleep(1.0)
                    speak_async("Puedes sentarte aquí, por favor.", lang_id="es_ES")
                    return
                else:
                    registrar(f"Movilidad (login): intento {intento+1} fallido al mover a la mesa. Reintentando...")
                    time.sleep(2.0)
            except Exception as e:
                registrar(f"ERROR moviendo el robot a la mesa tras login: {e}")
                time.sleep(2.0)

        registrar("Movilidad (login): no se pudo colocar al robot en la mesa tras varios intentos.")

    threading.Thread(target=_worker, daemon=True).start()



def registrar(mensaje: str):
    hora = datetime.now().strftime("%H:%M:%S")
    entrada = f"[{hora}] {mensaje}"
    REGISTRO.append(entrada)
    print(entrada, flush=True)

# ------------------- ROS init -------------------
if not rospy.core.is_initialized():
    rospy.init_node('puente_web_ros', anonymous=True, disable_signals=True)

# Instancia del speaker (TTS /tts)
_speaker = TiagoSpeaker()

def speak_async(text: str, lang_id: str = "es_ES"):
    """Respeta el mute global."""
    if MUTE:
        registrar(f"[MUTE] TTS omitido: {text}")
        return
    try:
        _speaker.speak_async(text, lang_id=lang_id)
    except Exception as e:
        registrar(f"TTS error: {e}")

# ------------------- Face recognition (genérico por roslib) -------------------
FACE_ACTION_SPEC = "face_recognition_pkg/FaceRecognitionAction"
FACE_SERVER_NAME = "face_recognition_action"

def face_login(max_minutes: float = 20.0) -> Optional[str]:
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

    client.send_goal(goal)

    start = rospy.Time.now()
    check_step = rospy.Duration(2.0)
    limit = rospy.Duration(max_minutes * 60.0)

    registrar("Login: colócate frente a la cámara del TIAGo, mira al objetivo y mantén la cara iluminada.")

    while not rospy.is_shutdown():
        if client.wait_for_result(check_step):
            result = client.get_result()
            if result:
                nombre = (getattr(result, "nombre", "") or "").strip()
                if nombre:
                    registrar(f"Login: reconocido '{nombre}'.")
                    return nombre
            client.send_goal(goal)

        if (rospy.Time.now() - start) > limit:
            try:
                client.cancel_goal()
            except Exception:
                pass
            registrar("Login: 20 minutos sin reconocimiento. Revisa iluminación/encuadre.")
            return None


def save_session_csv(sesion: Dict[str, Any], csv_path: Path = HISTORY_CSV):
    """
    Guarda la sesión en CSV (solo notas). Audición incluye nota_p1/nota_p2/nota_final.
    Cabeceras se crean si el archivo no existe.
    """
    # Extraer notas por prueba
    notas = {
        "memoria": None,
        "reflejos": None,
        "audicion": None,
        "audicion_p1": None,
        "audicion_p2": None,
        "coordinacion": None,
        "vision": None,
    }

    for p in (sesion.get("pruebas") or []):
        pk = (p.get("prueba") or "").lower()
        if pk == "memoria":
            notas["memoria"] = p.get("puntuacion")
        elif pk == "reflejos":
            notas["reflejos"] = p.get("puntuacion")
        elif pk == "audicion":
            d = (p.get("detalles") or {})
            notas["audicion"]    = p.get("puntuacion")
            notas["audicion_p1"] = d.get("nota_p1")
            notas["audicion_p2"] = d.get("nota_p2")
        elif pk == "coordinacion":
            notas["coordinacion"] = p.get("puntuacion")
        elif pk == "vision":                                  
            notas["vision"] = p.get("puntuacion")

    row = {
        "fecha": sesion.get("fecha", ""),
        "hora":  sesion.get("hora", ""),
        "paciente": (sesion.get("paciente") or {}).get("nombre", ""),
        "memoria": notas["memoria"],
        "reflejos": notas["reflejos"],
        "audicion": notas["audicion"],
        "audicion_p1": notas["audicion_p1"],
        "audicion_p2": notas["audicion_p2"],
        "coordinacion": notas["coordinacion"],
        "vision": notas["vision"],
    }


    header = list(row.keys())
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new_file:
            w.writeheader()
        w.writerow(row)


def _seed_fake_session(nombre: str = "Prueba"):
    """Genera una sesión ficticia con 3 pruebas y la deja lista en HISTORICO y SESION."""
    mem = round(random.uniform(5.0, 10.0), 2)
    ref = round(random.uniform(5.0, 10.0), 2)
    aud_p1 = round(random.uniform(5.0, 10.0), 2)
    aud_p2 = round(random.uniform(5.0, 10.0), 2)
    aud_final = round((aud_p1 + aud_p2) / 2.0, 2)
    coord = round(random.uniform(5.0, 10.0), 2)

    ts = datetime.now()
    sesion = {
        "fecha": ts.strftime("%Y-%m-%d"),
        "hora":  ts.strftime("%H:%M:%S"),
        "paciente": {"nombre": nombre},
        "pruebas": [
            {"prueba": "memoria",      "puntuacion": mem,      "hora": ts.strftime("%H:%M:%S")},
            {"prueba": "reflejos",     "puntuacion": ref,      "hora": ts.strftime("%H:%M:%S")},
            {"prueba": "audicion",     "puntuacion": aud_final,"hora": ts.strftime("%H:%M:%S"),
             "detalles": {"nota_p1": aud_p1, "nota_p2": aud_p2}},
            {"prueba": "coordinacion", "puntuacion": coord,    "hora": ts.strftime("%H:%M:%S")},
        ]
    }

    SESION.update({
        "ejecutando": False,
        "pruebas_completadas": ["memoria", "reflejos", "audicion", "coordinacion"],
        "resultados": list(sesion["pruebas"]),
        "paciente": {"nombre": nombre},
        "total_pruebas": 4,
        "current": "",
    })

# ------------------- Helpers Vision (normalizar texto a puntucacion) -------------------
def _normalize_text_for_score(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    # eliminar acentos
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # minúsculas, solo letras/números/espacios
    s = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in s)
    # colapsar espacios
    return " ".join(s.split())

def _similarity_0_1(ref: str, usr: str) -> float:
    a = _normalize_text_for_score(ref)
    b = _normalize_text_for_score(usr)
    if not a and not b:
        return 1.0
    if a and not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def _score_vision_phrase_0_10(ref: str, usr: str) -> float:
    ratio = _similarity_0_1(ref, usr)
    score = 10.0 * ratio
    if score < 0.0: score = 0.0
    if score > 10.0: score = 10.0
    return score



# ------------------- Helpers speaker / nombres -------------------
TEST_DISPLAY = {
    "memoria": "Memoria",
    "reflejos": "Reflejos",
    "audicion": "Audición",
    "coordinacion": "Coordinación / Movilidad",
    "vision": "Visión",
}


TEST_INTROS = {
    "memoria": (
        "En esta prueba de memoria voy a encender una secuencia de luces en los pulsadores. "
        "Cuando termine, tendrás que repetir la misma secuencia pulsando los botones en el mismo orden. "
        "Cada vez que lo hagas bien, la secuencia será un poco más larga."
    ),
    "reflejos": (
        "En esta prueba de reflejos se encenderá un único pulsador con una luz. "
        "Tu tarea es pulsar lo más rápido posible el botón que se encienda. "
        "La luz irá cambiando de sitio de forma aleatoria y, según avances de nivel, se encenderá cada vez más rápido."
    ),
    "audicion": (
        "En la prueba de audición vamos a hacer dos partes. "
        "En la primera parte, cada vez que escuches un bip deberás pulsar el botón número seis del cuadro de mandos, "
        "que está señalado. Pulsa siempre que escuches el sonido. "
        "En la segunda parte escucharás varios bip seguidos, tendrás que contarlos mentalmente "
        "y al final escribir el número total en la casilla que verás en la pantalla."
    ),
    "coordinacion": (
        "En la prueba de coordinación y marcha te pediré que te levantes de la silla. "
        "Me colocaré en la zona más alejada de la sala y necesitaré que camines hacia adelante y hacia atrás, "
        "intentando ir lo más recto posible. "
        "Voy a analizar tu forma de andar, la estabilidad del tronco y la simetría de la marcha. "
        "Esta prueba es orientativa y no sustituye a una valoración médica."
    ),
    "vision": (
        "En la prueba de visión te enseñaré primero una frase escrita en un cuaderno. "
        "Deberás leerla y recordarla. Después me alejaré y te enseñaré otra frase en la parte de atrás del cuaderno. "
        "Cuando terminemos, tendrás que escribir en la pantalla las dos frases que recuerdas."
    ),
}

def ordinal_es_femenino(n: int) -> str:
    base = ["primera", "segunda", "tercera", "cuarta", "quinta",
            "sexta", "séptima", "octava", "novena", "décima"]
    if 1 <= n <= len(base):
        return base[n-1]
    return f"{n}ª"

# ------------------- Rutas -------------------
def require_login():
    return bool(session.get("user"))

@app.route("/")
def inicio():
    if not require_login():
        return redirect(url_for("login"))
    if not SESION["paciente"].get("nombre"):
        SESION["paciente"]["nombre"] = session.get("user", "")
    if NO_TEST and not HISTORICO:
        _seed_fake_session(nombre=session.get("user","Prueba") or "Prueba")
    return render_template("index.html")



@app.route("/login", methods=["GET"])
def login():
    if session.get("user"):
        return redirect(url_for("inicio"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    if NO_LOGIN:
        session["user"] = "Prueba"
        SESION["paciente"]["nombre"] = "Prueba"
        speak_async("Bienvenido de pruebas a la consulta, pase por aquí", lang_id="es_ES")
        
        if NO_TEST and not HISTORICO:
            _seed_fake_session(nombre="Prueba")

        # ⬇️ Nuevo: después del saludo, ir a la mesa y decir que se siente
        mover_robot_a_mesa_despues_login("Prueba")

        return jsonify(ok=True, user="Prueba")

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
        SESION["paciente"]["nombre"] = nombre
        speak_async(f"Bienvenido {nombre} a la consulta, pase por aquí", lang_id="es_ES")

        # ⬇️ Nuevo: mover a la mesa y hablar al llegar
        mover_robot_a_mesa_despues_login(nombre)

        return jsonify(ok=True, user=nombre)
    except Exception as e:
        return jsonify(ok=False, error=str(e))




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/whoami")
def whoami():
    return jsonify(user=session.get("user", ""))

@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/start", methods=["POST"])
def iniciar_pruebas():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401

    datos: Dict[str, Any] = request.get_json(force=True)
    secuencia_pruebas = datos.get("order", [])

    # Fijamos el nombre del paciente desde la sesión siempre
    SESION["paciente"]["nombre"] = session.get("user", "")

    REGISTRO.clear()
    SESION.update({
        "ejecutando": True,
        "pruebas_completadas": [],
        "resultados": [],
        "total_pruebas": len(secuencia_pruebas),
        "current": "",
    })

    def worker():
        follower = get_follower()

        for idx, id_prueba in enumerate(secuencia_pruebas, start=1):
            SESION["current"] = id_prueba
            nombre_legible = TEST_DISPLAY.get(id_prueba, id_prueba.capitalize())
            orden_txt = ordinal_es_femenino(idx)

            # Elegir a qué punto ir según la prueba
            coords = None
            try:
                if id_prueba == "memoria" and hasattr(follower, "punto_mesa"):
                    coords = follower.punto_mesa

                elif id_prueba == "reflejos" and hasattr(follower, "punto_mesa"):
                    coords = follower.punto_mesa

                elif id_prueba == "audicion" and hasattr(follower, "punto_vision3"):
                    coords = follower.punto_vision3

                elif id_prueba == "coordinacion" and hasattr(follower, "punto_vision3"):
                    coords = follower.punto_coordinacion

                # Si hay coordenada, mover el robot
                if coords is not None:
                    registrar(f"Movilidad automática: yendo a posición para la prueba {nombre_legible}…")
                    ok = follower.enviar_puntos([coords])
                    if not ok:
                        registrar("Advertencia: movimiento no confirmado por Follower.")
                    else:
                        registrar("Movilidad automática: movimiento completado.")
            except Exception as e:
                registrar(f"ERROR moviendo el robot antes de la prueba {nombre_legible}: {e}")

            # Anuncio por voz
            speak_async(f"Vamos a realizar la {orden_txt} prueba, que es: {nombre_legible}", lang_id="es_ES")

            # 👉 Nueva explicación corta de la prueba
            intro = TEST_INTROS.get(id_prueba)
            if intro:
                speak_async(intro, lang_id="es_ES")

            # Ejecutar la prueba
            if id_prueba == "memoria":
                puntuacion = MemoriaClient.run()
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": puntuacion,
                    "hora": datetime.now().strftime("%H:%M:%S")
                }

            elif id_prueba == "reflejos":
                puntuacion = ReflejosClient.run()
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": puntuacion,
                    "hora": datetime.now().strftime("%H:%M:%S")
                }

            elif id_prueba == "audicion":
                det = AudicionClient.run()
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": None,  # se completa tras input P2
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "detalles": det or {},
                }


            elif id_prueba == "vision":     
                det = VisionClient.run()
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": None,  # se completa tras input del examinador
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "detalles": det or {},
                }

            elif id_prueba == "coordinacion":
                # El action devuelve 0–100, lo normalizamos a 0–10 para el informe
                try:
                    score_100, informe, csv_path, report_path = CoordinacionClient.run()
                    puntuacion = round(score_100 / 10.0, 1)
                    payload = {
                        "prueba": id_prueba,
                        "puntuacion": puntuacion,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "detalles": {
                            "score_0_100": score_100,
                            "informe": informe,
                            "csv_path": csv_path,
                            "report_path": report_path,
                        },
                    }
                except Exception as e:
                    registrar(f"ERROR en prueba de coordinación: {e}")
                    payload = {
                        "prueba": id_prueba,
                        "puntuacion": None,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "detalles": {"error": str(e)},
                    }

            else:
                payload = {
                    "prueba": id_prueba,
                    "puntuacion": None,
                    "hora": datetime.now().strftime("%H:%M:%S")
                }

            # Guardamos el resultado en la lista (para que aparezca en el panel y se pueda rellenar P2)
            idx_resultado = len(SESION["resultados"])
            SESION["resultados"].append(payload)

            # --- Lógica especial para pruebas que requieren input desde el front ---
            detalles = (payload.get("detalles") or {})

            if id_prueba == "audicion" and detalles.get("requiere_input"):
                global AUDICION_EVENT, AUDICION_INDEX

                with AUDICION_LOCK:
                    AUDICION_EVENT = threading.Event()
                    AUDICION_INDEX = idx_resultado

                registrar("Esperando a que el examinador introduzca la respuesta de Audición (P2) en la web…")
                AUDICION_EVENT.wait()
                registrar("Respuesta de Audición P2 recibida. Continuando con la siguiente prueba.")

                SESION["pruebas_completadas"].append(id_prueba)

            elif id_prueba == "vision" and detalles.get("requiere_input"):   # ⬅️ NUEVO
                global VISION_EVENT, VISION_INDEX

                with VISION_LOCK:
                    VISION_EVENT = threading.Event()
                    VISION_INDEX = idx_resultado

                registrar("Esperando a que el examinador introduzca las frases de la prueba de Visión en la web…")
                VISION_EVENT.wait()
                registrar("Respuesta de Visión recibida. Continuando con la siguiente prueba.")

                SESION["pruebas_completadas"].append(id_prueba)

            else:
                SESION["pruebas_completadas"].append(id_prueba)


        # ---- FINAL DE SECUENCIA ----
        SESION["current"] = ""
        SESION["ejecutando"] = False
        ts = datetime.now()
        sesion = {
            "fecha": ts.strftime("%Y-%m-%d"),
            "hora":  ts.strftime("%H:%M:%S"),
            "paciente": dict(SESION.get("paciente", {})),
            "pruebas": list(SESION.get("resultados", []))
        }
        HISTORICO.append(sesion)

        # >>> Guardar la sesión PRIVADA en CSV (solo notas)
        try:
            save_session_csv(sesion)
        except Exception as e:
            registrar(f"ERROR guardando CSV: {e}")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(ok=True)



@app.route("/status")
def obtener_estado():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401
    # Incluimos usuario para mostrar en navbar sin otro endpoint si quieres
    return jsonify(estado=SESION, registro=REGISTRO, user=session.get("user", ""))



# === Endpoint para registrar respuesta del paciente en Audición (P2) ===
@app.route("/answer", methods=["POST"])
def responder_resultado():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401

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
        
        elif item.get("prueba") == "vision":
            det = item.get("detalles", {}) or {}

            ref1 = (det.get("frase_1") or "").strip()
            ref2 = (det.get("frase_2") or "").strip()
            usr1 = (values.get("vision_frase_1") or "").strip()
            usr2 = (values.get("vision_frase_2") or "").strip()

            nota_f1 = round(_score_vision_phrase_0_10(ref1, usr1), 2)
            nota_f2 = round(_score_vision_phrase_0_10(ref2, usr2), 2)
            nota_final = round((nota_f1 + nota_f2) / 2.0, 2)

            det["frase_1_usuario"] = usr1
            det["frase_2_usuario"] = usr2
            det["nota_f1"] = float(nota_f1)
            det["nota_f2"] = float(nota_f2)

            item["puntuacion"] = float(nota_final)
            item["detalles"] = det


    except Exception as e:
        registrar(f"ERROR calculando notas de audición/visión: {e}")


    # Si estábamos bloqueados esperando esta respuesta (Audición P2), despertamos el hilo
    global AUDICION_EVENT, AUDICION_INDEX
    with AUDICION_LOCK:
        if AUDICION_EVENT is not None and idx == AUDICION_INDEX:
            AUDICION_EVENT.set()
            AUDICION_EVENT = None
            AUDICION_INDEX = None

    global VISION_EVENT, VISION_INDEX
    with VISION_LOCK:
        if VISION_EVENT is not None and idx == VISION_INDEX:
            VISION_EVENT.set()
            VISION_EVENT = None
            VISION_INDEX = None


    return jsonify(ok=True)




@app.route("/report/latest")
def report_latest():
    # Alias: reutiliza la lógica de report_pdf
    return report_pdf()



# Histórico: no exponer a UI
@app.route("/history")
def obtener_historial():
    return jsonify(filas=[])

@app.route("/history/clear", methods=["POST"])
def limpiar_historial():
    try:
        if HISTORY_CSV.exists():
            HISTORY_CSV.unlink()
        HISTORICO.clear()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.route("/report/pdf", methods=["GET"])
def report_pdf():
    if not require_login():
        return "No autenticado", 401
    if not HISTORICO:
        return "No hay sesiones para generar informe", 404

    sesion = HISTORICO[-1]
    logo_path = os.path.join(BASE_DIR, "static", "img", "logo-deusto.png")

    try:
        pdf_bytes = build_pdf_bytes(sesion, logo_path)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"informe_{sesion.get('fecha','')}_{sesion.get('hora','')}.pdf"
        )
    except Exception as e:
        registrar(f"ERROR generando PDF: {e}")
        return f"Error generando PDF: {e}", 500


@app.route("/admin")
def admin_panel():
    if not require_login():
        return redirect(url_for("login"))
    return render_template("admin_index.html")


@app.route("/admin/history")
def obtener_historial_admin():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401

    filas = []
    for ses in HISTORICO:
        pruebas_desc = []
        for p in ses.get("pruebas", []):
            pk = (p.get("prueba") or "").lower()
            nombre = TEST_DISPLAY.get(pk, pk.capitalize())
            nota = p.get("puntuacion", None)
            if nota is not None:
                pruebas_desc.append(f"{nombre}: {nota}/10")
            else:
                pruebas_desc.append(nombre)

        filas.append({
            "fecha": ses.get("fecha", ""),
            "hora":  ses.get("hora", ""),
            "paciente": (ses.get("paciente") or {}).get("nombre", ""),
            "pruebas": ", ".join(pruebas_desc),
        })

    return jsonify(ok=True, filas=filas)


@app.route("/admin/move", methods=["POST"])
def admin_move():
    if not require_login():
        return jsonify(ok=False, error="No autenticado"), 401

    datos = request.get_json(force=True) or {}
    modo = datos.get("mode")

    if modo not in ("preset", "coords"):
        return jsonify(ok=False, error="Modo inválido"), 400

    # Conectamos ya con el follower (lo reutilizamos abajo)
    follower = get_follower()

    # Construimos la lista de puntos a enviar [[x, y, oz, ow]]
    puntos = []

    if modo == "preset":
        key = (datos.get("preset") or "").lower()
        if not key:
            return jsonify(ok=False, error="Posición preprogramada no indicada"), 400

        # 1) Intentar usar atributo del Follower: punto_inicio, punto_puerta, etc.
        attr_name = f"punto_{key}"
        coords = None
        if hasattr(follower, attr_name):
            coords = getattr(follower, attr_name)
            registrar(f"Movilidad admin: usando follower.{attr_name} = {coords}")
        else:
            # 2) Fallback al diccionario PREPROGRAMMED_POINTS
            coords = PREPROGRAMMED_POINTS.get(key)
            registrar(f"Movilidad admin: usando PREPROGRAMMED_POINTS['{key}'] = {coords}")

        if not coords:
            return jsonify(ok=False, error=f"Posición preprogramada desconocida: {key}"), 400

        puntos.append(coords)
        desc = f"preprogramada '{key}'"

    else:  # modo == "coords"
        coords = datos.get("coords") or []
        if not isinstance(coords, list) or len(coords) != 4:
            return jsonify(ok=False, error="coords debe ser una lista [x, y, oz, ow]"), 400

        try:
            x, y, oz, ow = [float(v) for v in coords]
        except Exception:
            return jsonify(ok=False, error="Las coordenadas deben ser numéricas"), 400

        puntos.append([x, y, oz, ow])
        desc = f"manual [{x:.3f}, {y:.3f}, {oz:.3f}, {ow:.3f}]"

    def worker():
        try:
            registrar(f"Movilidad: enviando posición {desc} al TIAGo…")
            ok = follower.enviar_puntos(puntos)
            if ok is False:
                registrar("Movilidad: el Follower devolvió fallo al mover el robot.")
            else:
                registrar("Movilidad: movimiento completado.")
        except Exception as e:
            registrar(f"ERROR en movimiento de movilidad TIAGo: {e}")

    threading.Thread(target=worker, daemon=True).start()

    return jsonify(ok=True, message=f"Movimiento {desc} enviado al robot.")


# ------------------- Main -------------------
if __name__ == "__main__":
    # Flags útiles:
    #   python3 app.py --no-login
    #   python3 app.py --no-login --mute --no-test

    mover_robot_a_puerta_inicio()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
