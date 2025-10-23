# app.py
import os
import uuid
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask, render_template, request, jsonify, redirect, url_for

# ==== ROS (ROS1 Noetic) ====
import rospy
import actionlib
from roslib.message import get_message_class

# -------------------------------------------------------------------------------------
# CONFIGURA AQUÍ TUS SERVIDORES DE ACCIÓN (paquete/Action, nombre del servidor, etc.)
# Cada prueba debe tener: display (nombre en UI), action_spec (<pkg>/<Action>Action),
# server_name (nombre del action server), result_mapper (opcional, para formatear result).
# -------------------------------------------------------------------------------------

def audicion_result_mapper(result_msg) -> Dict[str, Any]:
    # Audición: int32[4] resultados [num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2]
    # Se expondrá con nombres legibles en el glosario.
    try:
        arr = list(result_msg.resultados)
    except Exception:
        arr = []
    keys = ["Num llamadas P1", "Num llamadas P2", "Aciertos P2", "Fallos P2"]
    mapped = {}
    for i, k in enumerate(keys):
        mapped[k] = arr[i] if i < len(arr) else None
    return mapped

TESTS: Dict[str, Dict[str, Any]] = {
    "audicion": {
        "display": "Audición",
        "action_spec": "psicotecnico_msgs/AudicionAction",   # <-- AJUSTA EL PAQUETE/Action a tu entorno
        "server_name": "/audicion",                          # <-- Nombre del action server
        "result_mapper": audicion_result_mapper
    },
    "coordinacion": {
        "display": "Coordinación",
        # Suponiendo misma interfaz (bool ejecutar). Ajusta a tu paquete/Action real:
        "action_spec": "psicotecnico_msgs/CoordinacionAction",
        "server_name": "/coordinacion",
        "result_mapper": None  # genérico: serializamos campos del result
    },
    "vision": {
        "display": "Visión",
        "action_spec": "psicotecnico_msgs/VisionAction",
        "server_name": "/vision",
        "result_mapper": None
    },
    "reflejos": {
        "display": "Reflejos",
        "action_spec": "psicotecnico_msgs/ReflejosAction",
        "server_name": "/reflejos",
        "result_mapper": None
    },
}

# -------------------------------------------------------------------------------------
# Inicialización Flask
# -------------------------------------------------------------------------------------
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_change_me")

# -------------------------------------------------------------------------------------
# ROS init (como cliente) - deshabilita señales para coexistir con Flask
# -------------------------------------------------------------------------------------
if not rospy.core.is_initialized():
    rospy.init_node("psicotecnico_web_client", anonymous=True, disable_signals=True)

# -------------------------------------------------------------------------------------
# Gestión de jobs en memoria (simple)
# -------------------------------------------------------------------------------------
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

def set_job(job_id: str, data: Dict[str, Any]):
    with JOBS_LOCK:
        JOBS[job_id] = data

def get_job(job_id: str) -> Dict[str, Any]:
    with JOBS_LOCK:
        return JOBS.get(job_id, {})

def serialize_ros_message(msg) -> Any:
    """
    Convierte un mensaje ROS (Result) en dict/list legible.
    Si trae campos complejos, se intenta serializar por __slots__.
    """
    try:
        if hasattr(msg, "__slots__"):
            out = {}
            for s in msg.__slots__:
                val = getattr(msg, s)
                if hasattr(val, "__slots__"):
                    out[s] = serialize_ros_message(val)
                elif isinstance(val, (list, tuple)):
                    out[s] = [
                        serialize_ros_message(v) if hasattr(v, "__slots__") else v
                        for v in val
                    ]
                else:
                    out[s] = val
            return out
        # Si es primitivo/lista:
        if isinstance(msg, (list, tuple)):
            return list(msg)
        return msg
    except Exception:
        return str(msg)

def run_single_action(test_key: str) -> Dict[str, Any]:
    """
    Ejecuta un ActionClient para una prueba específica con Goal.ejecutar=True
    Retorna un dict con estado y resultados ya "mapeados" (si hay mapper).
    """
    cfg = TESTS[test_key]
    action_spec = cfg["action_spec"]
    server_name = cfg["server_name"]

    # Cargamos dinámicamente el tipo <Pkg>/<Name>Action
    action_cls = get_message_class(action_spec)
    if action_cls is None:
        raise RuntimeError(f"No se pudo cargar la Action '{action_spec}'. Verifica el paquete y la compilación.")

    # Derivar los tipos Goal/Result:
    # En ROS1, para una Action llamada FooAction, las clases son FooAction, FooGoal, FooResult...
    goal_type_name = action_spec.replace("Action", "Goal")
    result_type_name = action_spec.replace("Action", "Result")
    goal_cls = get_message_class(goal_type_name)
    result_cls = get_message_class(result_type_name)
    if goal_cls is None or result_cls is None:
        raise RuntimeError(f"No se pudieron derivar Goal/Result de '{action_spec}'.")

    client = actionlib.SimpleActionClient(server_name, action_cls)

    # Esperar servidor (con timeout razonable)
    if not client.wait_for_server(rospy.Duration(10.0)):
        raise RuntimeError(f"Action server '{server_name}' no disponible.")

    # Construir y enviar Goal
    goal = goal_cls()
    # Por interfaz estandarizada, usamos bool ejecutar
    if not hasattr(goal, "ejecutar"):
        raise RuntimeError(f"El Goal de '{action_spec}' no tiene campo 'ejecutar'.")
    goal.ejecutar = True

    client.send_goal(goal)
    # Esperar a que termine (puedes ajustar el timeout si alguna prueba dura más)
    finished = client.wait_for_result(rospy.Duration(600.0))
    if not finished:
        client.cancel_goal()
        raise RuntimeError(f"Timeout esperando resultado de '{server_name}'.")

    result_msg = client.get_result()
    # Mapeo específico (si se definió)
    mapper = cfg.get("result_mapper")
    if callable(mapper):
        mapped = mapper(result_msg)
    else:
        mapped = serialize_ros_message(result_msg)

    return {
        "test_key": test_key,
        "test_display": cfg["display"],
        "server": server_name,
        "action_spec": action_spec,
        "ok": True,
        "result": mapped,
    }

def run_sequence(job_id: str, ordered_tests: List[str]):
    """
    Ejecuta la secuencia completa, actualiza el estado del job y guarda resultados.
    """
    set_job(job_id, {
        "job_id": job_id,
        "state": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "current": None,
        "done": [],
        "error": None,
        "results": {},  # test_key -> result dict
        "order": ordered_tests,
    })

    for t in ordered_tests:
        try:
            # Actualizar "current"
            data = get_job(job_id)
            data["current"] = t
            set_job(job_id, data)

            # Ejecutar prueba
            outcome = run_single_action(t)

            # Guardar resultados
            data = get_job(job_id)
            data["done"].append(t)
            data["results"][t] = outcome
            data["current"] = None
            set_job(job_id, data)

        except Exception as e:
            data = get_job(job_id)
            data["state"] = "error"
            data["error"] = {
                "test": t,
                "message": str(e),
                "trace": traceback.format_exc(),
            }
            set_job(job_id, data)
            return

    data = get_job(job_id)
    data["state"] = "done"
    data["finished_at"] = datetime.utcnow().isoformat() + "Z"
    set_job(job_id, data)

# -------------------------------------------------------------------------------------
# Rutas Flask
# -------------------------------------------------------------------------------------

@app.route("/")
def index():
    # Pasamos las pruebas disponibles a la UI
    tests = [{"key": k, "display": v["display"]} for k, v in TESTS.items()]
    return render_template("index.html", tests=tests)

@app.route("/run", methods=["POST"])
def run_tests():
    """
    Inicia un job con el orden de pruebas. Espera JSON:
    { "order": ["audicion", "vision", ...] }
    """
    payload = request.get_json(force=True, silent=True) or {}
    order = payload.get("order", [])

    # Validar claves
    valid_order = [t for t in order if t in TESTS.keys()]
    if not valid_order:
        return jsonify({"error": "Debes enviar un orden válido de pruebas."}), 400

    job_id = str(uuid.uuid4())
    thread = threading.Thread(target=run_sequence, args=(job_id, valid_order), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    data = get_job(job_id)
    if not data:
        return jsonify({"error": "Job no encontrado"}), 404
    return jsonify(data)

@app.route("/summary/<job_id>")
def summary(job_id):
    data = get_job(job_id)
    if not data:
        return redirect(url_for("index"))
    if data.get("state") != "done":
        # Si no terminó, vuelve a la pantalla principal (o puedes mostrar progreso)
        return redirect(url_for("index"))
    return render_template("summary.html", job=data)

# -------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Puedes usar host 0.0.0.0 si vas a exponer en Docker
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
