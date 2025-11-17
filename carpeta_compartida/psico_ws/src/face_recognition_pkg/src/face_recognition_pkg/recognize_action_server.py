#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor de acción para reconocimiento facial.
- Espera un goal ejecutar=True.
- Cuando reconoce a alguien (estable por mayoría), devuelve Result.nombre y termina.

Ejemplo de ejecución recomendada (pasando db_path):
  rosrun face_recognition_pkg recognize_action_server.py \
    _db_path:=package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Action server de reconocimiento facial optimizado:
- Hilo principal: UI + estabilización + control de acción
- Hilo worker: inferencia DeepFace sobre el frame más reciente (cola tamaño 1)
- FPS real (ventana de 1s)
"""

import os
import json
import time
import threading
from pathlib import Path
from collections import deque

import numpy as np
import cv2
import rospy
import actionlib
from sensor_msgs.msg import CompressedImage, Image

from deepface import DeepFace
from face_recognition_pkg.msg import (
    FaceRecognitionAction,
    FaceRecognitionResult,
    FaceRecognitionFeedback,
)

# ================== Parámetros ==================
MODEL_NAME = "ArcFace"
DETECTOR_BACKEND = "opencv"     # cambia a "mediapipe" si caras muy pequeñas
COSINE_THRESHOLD = 0.35
STABILITY_FRAMES = 5

ROS_TOPIC = "/xtion/rgb/image_raw/compressed"
ROS_COMPRESSED = True
ROS_QUEUE_SIZE = 5

# Rendimiento
PROC_RESIZE_W = 640             # ancho para la inferencia DeepFace
DEEPFACE_INTERVAL_MS = 120      # mínimo tiempo entre inferencias (~8.3 Hz). Sube/baja según CPU/GPU
ENABLE_UI = True                # pon a False en Docker/headless para máxima fluidez

# Ventana / visual
WINDOW_TITLE = "FaceRecognition Action Server"
MIRROR_VIEW = False

# ----------------------------------------------------
class RosImageSource:
    """Suscriptor ROS que mantiene solo el último frame decodificado en BGR."""
    def __init__(self, topic: str, compressed: bool = True, queue_size: int = 5):
        self.topic = topic
        self.compressed = compressed
        self._lock = threading.Lock()
        self._last_bgr = None
        self._count = 0

        if self.compressed:
            self._sub = rospy.Subscriber(
                self.topic, CompressedImage, self._cb_compressed, queue_size=queue_size
            )
            rospy.loginfo("Suscrito a CompressedImage: %s | queue_size=%d", self.topic, queue_size)
        else:
            from cv_bridge import CvBridge  # requiere paquete instalado
            self._bridge = CvBridge()
            self._sub = rospy.Subscriber(self.topic, Image, self._cb_raw, queue_size=queue_size)
            rospy.loginfo("Suscrito a Image RAW: %s | queue_size=%d", self.topic, queue_size)

    def _cb_compressed(self, msg: CompressedImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                return
            with self._lock:
                self._last_bgr = bgr
                self._count += 1
        except Exception as e:
            rospy.logerr_throttle(2.0, f"Decodificación JPEG falló: {e}")

    def _cb_raw(self, msg: Image):
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            with self._lock:
                self._last_bgr = bgr
                self._count += 1
        except Exception as e:
            rospy.logerr_throttle(2.0, f"cv_bridge falló: {e}")

    def latest_bgr(self):
        with self._lock:
            return None if self._last_bgr is None else self._last_bgr.copy()

    def received_count(self):
        with self._lock:
            return self._count


# ------------------- DeepFace helpers -------------------
def _resolve_db_path() -> Path:
    import rospkg
    param = rospy.get_param("~db_path", "").strip()
    if not param:
        return Path(os.getcwd()) / "embeddings_db.json"
    if param.startswith("package://"):
        rest = param[len("package://"):]
        if "/" not in rest:
            raise ValueError("db_path package:// mal formado. Debe ser package://<pkg>/ruta/archivo.json")
        pkg, rel = rest.split("/", 1)
        pkg_path = rospkg.RosPack().get_path(pkg)
        return Path(pkg_path) / rel
    return Path(param)

def load_db():
    db_path = _resolve_db_path()
    rospy.loginfo("Usando embeddings DB: %s", db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"No existe {db_path}. Indica ~db_path o coloca embeddings_db.json en el directorio actual."
        )
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = []
    for u in data.get("users", []):
        users.append({"name": u["name"], "embedding": np.array(u["embedding"], dtype=np.float32)})
    return users

def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return 1.0 - float(np.dot(a, b))

def represent_on_resized(bgr_full: np.ndarray) -> np.ndarray:
    h, w = bgr_full.shape[:2]
    if w > PROC_RESIZE_W:
        scale = PROC_RESIZE_W / float(w)
        bgr = cv2.resize(bgr_full, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        bgr = bgr_full
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    reps = DeepFace.represent(
        img_path=rgb,
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        enforce_detection=True,
    )
    emb = np.array(reps[0]["embedding"], dtype=np.float32)
    emb = emb / (np.linalg.norm(emb) + 1e-9)
    return emb


# ------------------- Worker de inferencia -------------------
class InferenceWorker(threading.Thread):
    """
    Toma frames de una cola (capacidad 1) y publica resultados en variables compartidas.
    """
    def __init__(self, users, frame_source, result_lock, result_state, stop_event):
        super().__init__(daemon=True)
        self.users = users
        self.frame_source = frame_source      # queue-like: put/get non-block con drop
        self.result_lock = result_lock
        self.result_state = result_state      # dict: {"best_name":str, "best_dist":float, "t":float}
        self.stop_event = stop_event
        self.last_infer_t = 0.0

    def classify(self, emb: np.ndarray):
        best_name = "Desconocido"
        best_dist = 1e9
        for u in self.users:
            dist = cosine_distance(emb, u["embedding"])
            if dist < best_dist:
                best_dist = dist
                best_name = u["name"] if dist < COSINE_THRESHOLD else "Desconocido"
        return best_name, best_dist

    def run(self):
        while not self.stop_event.is_set() and not rospy.is_shutdown():
            frame = self.frame_source.get_latest()
            if frame is None:
                time.sleep(0.002)
                continue

            # Throttle de inferencia
            now = time.perf_counter()
            if (now - self.last_infer_t) * 1000.0 < DEEPFACE_INTERVAL_MS:
                time.sleep(0.001)
                continue
            self.last_infer_t = now

            try:
                emb = represent_on_resized(frame)
                name, dist = self.classify(emb)
                with self.result_lock:
                    self.result_state["best_name"] = name
                    self.result_state["best_dist"] = float(dist)
                    self.result_state["t"] = time.time()
            except Exception as e:
                # si no hay cara / error, no pisamos con desconocido; dejamos que estabilice
                rospy.logwarn_throttle(2.0, f"Inferencia fallida/No face: {e}")


# ------------------- Cola de último frame (capacidad 1) -------------------
class LatestFrameBuffer:
    """
    Buffer de un solo frame: set(bgr) pisa el anterior; get_latest() devuelve copia inmediata.
    Evita que el worker se quede atrás: siempre procesa lo más nuevo.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._bgr = None

    def set(self, bgr):
        with self._lock:
            self._bgr = bgr

    def get_latest(self):
        with self._lock:
            if self._bgr is None:
                return None
            return self._bgr.copy()


# ------------------- Action Server -------------------
class FaceRecognitionActionServer:
    def __init__(self):
        rospy.init_node("face_recognition_action_server", anonymous=True)

        # Sugerencias TF para menos ruido
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

        rospy.loginfo("Cargando base de embeddings...")
        self.users = load_db()
        if not self.users:
            rospy.logwarn("La base de usuarios está vacía.")

        # Pre-warm (carga pesos y compila gráficos, reduce lag de primera inferencia)
        _dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        try:
            _ = represent_on_resized(_dummy)
        except Exception:
            pass

        self.src = RosImageSource(topic=ROS_TOPIC, compressed=ROS_COMPRESSED, queue_size=ROS_QUEUE_SIZE)
        threading.Thread(target=rospy.spin, daemon=True).start()

        # Infra de worker
        self.frame_buf = LatestFrameBuffer()
        self.result_lock = threading.Lock()
        self.result_state = {"best_name": "Desconocido", "best_dist": 9.999, "t": 0.0}
        self.stop_event = threading.Event()

        self.server = actionlib.SimpleActionServer(
            "face_recognition_action",
            FaceRecognitionAction,
            execute_cb=self.execute_cb,
            auto_start=False,
        )
        self.server.start()
        rospy.loginfo("Servidor de acción 'face_recognition_action' listo y esperando objetivos.")

    def execute_cb(self, goal):
        rospy.loginfo(f"Recibido goal: ejecutar={goal.ejecutar}")

        feedback = FaceRecognitionFeedback()
        result = FaceRecognitionResult()

        if not goal.ejecutar:
            feedback.estado = "Goal con ejecutar=False. Nada que hacer."
            self.server.publish_feedback(feedback)
            rospy.sleep(0.2)
            self.server.set_aborted(result, "ejecutar=False")
            return

        # Lanzar worker de inferencia
        self.stop_event.clear()
        worker = InferenceWorker(self.users, self.frame_buf, self.result_lock, self.result_state, self.stop_event)
        worker.start()

        # Estabilización por mayoría
        recent_preds = deque(maxlen=STABILITY_FRAMES)
        last_label = "Desconocido"

        # FPS real de visualización
        disp_times = deque(maxlen=60)  # timestamps de frames mostrados

        # UI
        if ENABLE_UI:
            try:
                cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
            except Exception:
                pass

        feedback.estado = "Esperando frames de cámara..."
        self.server.publish_feedback(feedback)

        try:
            while not rospy.is_shutdown():
                if self.server.is_preempt_requested():
                    feedback.estado = "Preempted por el cliente. Abortando."
                    self.server.publish_feedback(feedback)
                    self.server.set_preempted()
                    break

                bgr = self.src.latest_bgr()
                if bgr is None:
                    time.sleep(0.002)
                    continue

                # Empuja el frame más reciente al worker (pisa el anterior)
                self.frame_buf.set(bgr)

                # Lee último resultado del worker
                with self.result_lock:
                    best_name = self.result_state["best_name"]
                    best_dist = self.result_state["best_dist"]

                # Mayoría deslizante
                recent_preds.append(best_name)
                if len(recent_preds) == STABILITY_FRAMES:
                    candidates, counts = np.unique(recent_preds, return_counts=True)
                    majority = candidates[np.argmax(counts)]
                    if majority != last_label:
                        last_label = majority
                        feedback.estado = f"Votación estable: {last_label}"
                        self.server.publish_feedback(feedback)

                    if last_label != "Desconocido":
                        result.nombre = last_label
                        rospy.loginfo(f"[FACE] Reconocido: {last_label} (dist~{best_dist:.3f})")
                        self.server.set_succeeded(result)
                        break

                # UI / FPS real
                if ENABLE_UI:
                    disp = bgr if not MIRROR_VIEW else cv2.flip(bgr, 1)
                    h, w = disp.shape[:2]
                    cv2.rectangle(disp, (int(w*0.15), int(h*0.15)), (int(w*0.85), int(h*0.85)), (255,255,255), 1)

                    # FPS reales (frames mostrados/segundo)
                    t_now = time.time()
                    disp_times.append(t_now)
                    # borra timestamps más antiguos de 1s
                    while disp_times and (t_now - disp_times[0]) > 1.0:
                        disp_times.popleft()
                    fps_real = float(len(disp_times))

                    cv2.putText(
                        disp,
                        f"{last_label} (dist={best_dist:.3f})  FPS:{fps_real:.1f}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0) if last_label != "Desconocido" else (0, 0, 255),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        disp,
                        f"recv:{self.src.received_count()}  infer every ~{DEEPFACE_INTERVAL_MS}ms",
                        (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (20, 220, 20),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.imshow(WINDOW_TITLE, disp)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        feedback.estado = "UI cerrada por usuario. Preempting."
                        self.server.publish_feedback(feedback)
                        self.server.set_preempted()
                        break

                # Pequeño yield para no quemar CPU si UI off
                if not ENABLE_UI:
                    time.sleep(0.001)

        finally:
            self.stop_event.set()
            try:
                if ENABLE_UI:
                    cv2.destroyWindow(WINDOW_TITLE)
            except Exception:
                pass

    # (no cambiamos main/ros spin)

def main():
    try:
        _ = FaceRecognitionActionServer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


if __name__ == "__main__":
    main()
