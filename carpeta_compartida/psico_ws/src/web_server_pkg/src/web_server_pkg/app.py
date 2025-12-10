#!/usr/bin/env python3
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file

from report import build_pdf_bytes
import io

# ==== ROS (ROS1 Noetic) ====
import rospy
import actionlib
from roslib.message import get_message_class

from speak_api import TiagoSpeaker
from pruebas_client import MemoriaClient, ReflejosClient, AudicionClient, CoordinacionClient

import csv
from pathlib import Path

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

# === Movilidad / checkpoints TIAGo ===
PREPROGRAMMED_POINTS = {
    "puerta":  [1.801448077821011,  -0.7272143308845652,  -0.17600744219629474, 0.9843888359238527],
    "puerta2": [0.75413808767915,    0.6935195599805307,   0.8738231258256374,  0.48624391489489344],
    "medio":   [3.6704948592312454, -1.8971807817955268,  -0.34134149988312906, 0.9399393493505502],
    "fondo":   [6.128891746903331,  -2.156612477116119,  -0.100474241670117,   0.9949396598592374],
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


# ------------------- Helpers speaker / nombres -------------------
TEST_DISPLAY = {
    "memoria": "Memoria",
    "reflejos": "Reflejos",
    "audicion": "Audición",
    "coordinacion": "Coordinación / Movilidad",
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

        # 1) OPCIONAL: mover al punto de inicio antes de empezar las pruebas
        try:
            if hasattr(follower, "punto_inicio"):
                registrar("Movilidad automática: yendo al punto de inicio…")
                follower.enviar_puntos([follower.punto_puerta])
        except Exception as e:
            registrar(f"ERROR moviendo al punto de inicio: {e}")
            
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
                    coords = follower.punto_vision3

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

            speak_async(f"Vamos a realizar la {orden_txt} prueba, que es: {nombre_legible}", lang_id="es_ES")

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


            SESION["pruebas_completadas"].append(id_prueba)
            SESION["resultados"].append(payload)

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
            save_session_csv(sesion)   # <-- AQUÍ es el punto 2.3
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

    except Exception as e:
        registrar(f"ERROR calculando notas de audición: {e}")

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

    # Construimos la lista de puntos a enviar [[x, y, oz, ow]]
    puntos = []

    if modo == "preset":
        key = (datos.get("preset") or "").lower()
        coords = PREPROGRAMMED_POINTS.get(key)
        if not coords:
            return jsonify(ok=False, error="Posición preprogramada desconocida"), 400
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

    follower = get_follower()

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
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
