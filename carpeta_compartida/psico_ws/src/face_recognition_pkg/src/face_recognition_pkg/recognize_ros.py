#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconocimiento facial con DeepFace leyendo directamente de un tópico ROS (TIAGO /xtion).

Ejecución (sin argumentos, ajustes por defecto "de fábrica"):
    python recognize_ros.py

Predeterminados equivalentes a:
    --topic /xtion/rgb/image_raw/compressed --compressed --fps_cap 25

Requisitos:
  - ROS Noetic (rospy, sensor_msgs)
  - numpy, opencv-python, deepface
  - (opcional) cv_bridge si usas topics RAW (Image en lugar de CompressedImage)
  - embeddings_db.json generado previamente por vuestro enrolador (en el cwd)

Notas:
  - Imprime por consola el nombre cuando se estabiliza un identificado distinto a "Desconocido".
  - Ventana OpenCV muestra el último resultado, FPS y un rectángulo guía.
"""
import json
import time
import threading
from pathlib import Path
from collections import deque

import numpy as np
import cv2
import rospy
from sensor_msgs.msg import CompressedImage, Image

from deepface import DeepFace

# ================== Config general ==================
DB_PATH = Path("embeddings_db.json")
MODEL_NAME = "ArcFace"              # Sugeridos: ArcFace, Facenet512, VGG-Face
DETECTOR_BACKEND = "opencv"         # Si la cara sale muy pequeña: "mediapipe" o "retinaface"
COSINE_THRESHOLD = 0.35              # Más bajo = más estricto
STABILITY_FRAMES = 5                 # Mayoría simple sobre últimos N labels

# ================== Fuente ROS (por defecto TIAGO) ==================
ROS_TOPIC = "/xtion/rgb/image_raw/compressed"
ROS_COMPRESSED = True                # True => sensor_msgs/CompressedImage; False => sensor_msgs/Image
ROS_QUEUE_SIZE = 5

# ================== Rendimiento y visualización ==================
PROCESS_EVERY_N = 2                  # Procesar cada N frames (1 = cada frame)
PROC_RESIZE_W = 640                  # Redimension para DeepFace (ancho destino)
UI_FPS_CAP = 25.0                    # Límite de refresco UI (equivale a --fps_cap 25)
SHOW_FPS = True
MIRROR_VIEW = False                  # Vista espejo
WINDOW_TITLE = "Reconocimiento desde ROS (TIAGO)"

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
            self._sub = rospy.Subscriber(self.topic, CompressedImage, self._cb_compressed,
                                         queue_size=queue_size)
            rospy.loginfo("Suscrito a CompressedImage: %s | queue_size=%d", self.topic, queue_size)
        else:
            # cv_bridge solo si es necesario
            try:
                from cv_bridge import CvBridge  # noqa
                self._bridge = CvBridge()
            except Exception as e:
                rospy.logerr("cv_bridge no disponible pero ROS_COMPRESSED=False: %s", e)
                raise
            self._sub = rospy.Subscriber(self.topic, Image, self._cb_raw,
                                         queue_size=queue_size)
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

# ------------------- DeepFace utilidades -------------------

def load_db():
    if not DB_PATH.exists():
        raise FileNotFoundError("No existe embeddings_db.json. Da de alta usuarios primero con enroll_user.py")
    with open(DB_PATH, "r", encoding="utf-8") as f:
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
    """Redimensiona a PROC_RESIZE_W (mantiene aspect) y calcula embedding."""
    h, w = bgr_full.shape[:2]
    if w > PROC_RESIZE_W:
        scale = PROC_RESIZE_W / float(w)
        bgr = cv2.resize(bgr_full, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
    else:
        bgr = bgr_full
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    reps = DeepFace.represent(
        img_path=rgb,
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        enforce_detection=True
    )
    # Usamos el primer rostro detectado
    emb = np.array(reps[0]["embedding"], dtype=np.float32)
    # Normalizamos una sola vez aquí
    emb = emb / (np.linalg.norm(emb) + 1e-9)
    return emb


# ------------------- UI helpers -------------------

def annotate(frame, text, org=(20, 40), color=(0, 255, 0)):
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)


def limit_fps(prev_t: float, target_fps: float) -> float:
    if target_fps <= 0:
        return time.time()
    interval = 1.0 / target_fps
    now = time.time()
    dt = now - prev_t
    if dt < interval:
        time.sleep(interval - dt)
        now = time.time()
    return now


# ------------------- Main -------------------

def main():
    users = load_db()
    if not users:
        print("No hay usuarios en la base. Ejecuta enroll_user.py primero.")
        return

    # ROS: deshabilitamos captura de señales para controlar el loop con OpenCV
    rospy.init_node("recognize_ros", anonymous=True, disable_signals=True)
    src = RosImageSource(topic=ROS_TOPIC, compressed=ROS_COMPRESSED, queue_size=ROS_QUEUE_SIZE)

    # Hilo ROS para callbacks
    threading.Thread(target=rospy.spin, daemon=True).start()

    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)

    recent_preds = deque(maxlen=STABILITY_FRAMES)
    last_label = "Desconocido"
    last_printed = None
    best_dist_display = 9.999

    prev_t = time.time()
    frame_idx = 0
    fps_t = time.time()
    fps = 0.0

    print(f"[ROS Cam] topic={ROS_TOPIC} | compressed={ROS_COMPRESSED} | fps_cap={UI_FPS_CAP}")

    while not rospy.is_shutdown():
        bgr = src.latest_bgr()
        if bgr is None:
            # Aún no hay frames, evita quemar CPU
            time.sleep(0.002)
            continue

        if MIRROR_VIEW:
            bgr = cv2.flip(bgr, 1)

        disp = bgr.copy()
        h, w = disp.shape[:2]
        cv2.rectangle(disp, (int(w*0.15), int(h*0.15)), (int(w*0.85), int(h*0.85)), (255,255,255), 1)
        annotate(disp, "Reconocimiento (q/ESC para salir)", (20, h-18), (255,255,255))

        # Procesamos cada N frames
        if frame_idx % PROCESS_EVERY_N == 0:
            try:
                emb = represent_on_resized(bgr)

                best_name = "Desconocido"
                best_dist = 1e9
                for u in users:
                    dist = cosine_distance(emb, u["embedding"])
                    if dist < best_dist:
                        best_dist = dist
                        best_name = u["name"] if dist < COSINE_THRESHOLD else "Desconocido"

                recent_preds.append(best_name)
                # estabilización por mayoría
                if len(recent_preds) == STABILITY_FRAMES:
                    candidates, counts = np.unique(recent_preds, return_counts=True)
                    majority = candidates[np.argmax(counts)]
                    if majority != last_label:
                        last_label = majority
                        if last_label != "Desconocido" and last_label != last_printed:
                            conf = max(0.0, min(1.0, 1.0 - (best_dist / COSINE_THRESHOLD)))
                            msg = f"[FACE] {last_label}  dist={best_dist:.3f}  conf~{conf*100:.1f}%"
                            print(msg)
                            last_printed = last_label
                best_dist_display = best_dist

            except Exception as e:
                # Si no detecta rostro o cualquier error, marcamos "Desconocido"
                recent_preds.append("Desconocido")
                best_dist_display = 9.999
                # Mensaje esporádico para depurar, sin inundar
                rospy.logwarn_throttle(2.0, f"DeepFace no devolvió embedding: {e}")

        # Overlay de estado (último resultado)
        annotate(disp, f"{last_label}  (dist={best_dist_display:.3f})",
                 (20, 40), (0,255,0) if last_label != "Desconocido" else (0,0,255))

        # FPS medido
        if SHOW_FPS:
            now = time.time()
            dt = now - fps_t
            if dt > 0:
                fps = 0.9*fps + 0.1*(1.0/dt)
            fps_t = now
            cv2.putText(disp, f"FPS:{fps:.1f}  proc/ {PROCESS_EVERY_N}  recv:{src.received_count()}  in:{w}x{h}",
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20,220,20), 2, cv2.LINE_AA)

        cv2.imshow(WINDOW_TITLE, disp)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):  # ESC o 'q'
            break

        # Cap de FPS de UI
        prev_t = limit_fps(prev_t, UI_FPS_CAP)
        frame_idx += 1

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
