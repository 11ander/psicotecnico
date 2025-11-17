#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from pathlib import Path
import cv2
import numpy as np
from deepface import DeepFace
from collections import deque

# ================== Config general ==================
DB_PATH = Path("embeddings_db.json")
MODEL_NAME = "ArcFace"
DETECTOR_BACKEND = "opencv"      # si la cara sale pequeña a 1 m: "mediapipe"
COSINE_THRESHOLD = 0.35
STABILITY_FRAMES = 5

# ================== Cámara (Ubuntu / V4L2) ==================
CAM_INDEX = 0
USE_V4L2 = True
FRAME_W, FRAME_H = 1280, 720         # pide 720p MJPG
FOURCC = "MJPG"
TARGET_FPS = 25.0                    # cap de visualización

# ================== Rendimiento reconocimiento ==================
PROCESS_EVERY_N = 2                  # procesar cada N frames (1= cada frame)
PROC_RESIZE_W = 640                  # redimensionar copia para DeepFace (ancho)
SHOW_FPS = True

# ----------------------------------------------------

def open_camera(cam_index=CAM_INDEX, use_v4l2=USE_V4L2, w=FRAME_W, h=FRAME_H, fourcc=FOURCC):
    cap = cv2.VideoCapture(cam_index)  # por defecto
    if not cap.isOpened() and use_v4l2:
        cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        return None
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        # minimizar buffering si la build lo soporta
        CAP_PROP_BUFFERSIZE = 38
        cap.set(CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    # warm-up
    for _ in range(4):
        cap.read()
    return cap

def limit_fps(prev_t, target_fps=TARGET_FPS):
    if target_fps <= 0:
        return time.time()
    interval = 1.0 / target_fps
    now = time.time()
    dt = now - prev_t
    if dt < interval:
        time.sleep(interval - dt)
        now = time.time()
    return now

def load_db():
    if not DB_PATH.exists():
        raise FileNotFoundError("No existe embeddings_db.json. Da de alta usuarios primero con enroll_user.py")
    with open(DB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = []
    for u in data.get("users", []):
        users.append({"name": u["name"], "embedding": np.array(u["embedding"], dtype=np.float32)})
    return users

def cosine_distance(a, b):
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return 1.0 - float(np.dot(a, b))

def represent_on_resized(bgr_full):
    """Redimensiona a PROC_RESIZE_W (manteniendo aspect) y calcula embedding."""
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
    emb = np.array(reps[0]["embedding"], dtype=np.float32)
    return emb

def annotate(frame, text, org=(20, 40), color=(0, 255, 0)):
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

def main():
    users = load_db()
    if not users:
        print("No hay usuarios en la base. Ejecuta enroll_user.py primero.")
        return

    cap = open_camera()
    if cap is None or not cap.isOpened():
        print("No se pudo abrir la cámara (V4L2). Prueba otro /dev/videoN.")
        return

    cv2.namedWindow("Reconocimiento", cv2.WINDOW_NORMAL)

    recent_preds = deque(maxlen=STABILITY_FRAMES)
    last_label = "Desconocido"
    last_printed = None
    best_dist = 1e9

    prev_t = time.time()
    frame_idx = 0
    fps_t = time.time()
    fps = 0.0

    # imprime resolución real de la cámara (una vez)
    printed_shape = False

    while True:
        ok, frame = cap.read()
        if not ok:
            cv2.waitKey(1)
            continue

        if not printed_shape:
            print("[Cam]", frame.shape, "FOURCC:", FOURCC, "TARGET_FPS:", TARGET_FPS)
            printed_shape = True

        disp = frame.copy()
        h, w = disp.shape[:2]
        cv2.rectangle(disp, (int(w*0.15), int(h*0.15)), (int(w*0.85), int(h*0.85)), (255,255,255), 1)
        annotate(disp, "Reconocimiento (ESC para salir)", (20, h-18), (255,255,255))

        # Solo procesamos cada N frames para mantener fluidez
        if frame_idx % PROCESS_EVERY_N == 0:
            try:
                emb = represent_on_resized(frame)
                emb = emb / (np.linalg.norm(emb) + 1e-9)

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
                        # imprime cuando cambia a reconocido
                        if last_label != "Desconocido" and last_label != last_printed:
                            conf = max(0.0, min(1.0, 1.0 - (best_dist / COSINE_THRESHOLD)))
                            msg = f"[FACE] {last_label}  dist={best_dist:.3f}  conf~{conf*100:.1f}%"
                            print(msg)
                            last_printed = last_label

            except Exception:
                recent_preds.append("Desconocido")

        # overlay de estado (último resultado)
        annotate(disp, f"{last_label}  (dist={best_dist:.3f})",
                 (20, 40), (0,255,0) if last_label!="Desconocido" else (0,0,255))

        # FPS medido
        if SHOW_FPS:
            now = time.time()
            dt = now - fps_t
            if dt > 0:
                fps = 0.9*fps + 0.1*(1.0/dt)
            fps_t = now
            cv2.putText(disp, f"FPS:{fps:.1f}  proc/ {PROCESS_EVERY_N}  in:{w}x{h}",
                        (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20,220,20), 2, cv2.LINE_AA)

        cv2.imshow("Reconocimiento", disp)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break

        # cap de FPS de UI
        prev_t = limit_fps(prev_t, TARGET_FPS)
        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()