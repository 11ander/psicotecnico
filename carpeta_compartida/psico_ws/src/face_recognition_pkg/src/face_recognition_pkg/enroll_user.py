#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
from pathlib import Path
import cv2
import numpy as np
from deepface import DeepFace
from datetime import datetime

# ================== Config cámara (Ubuntu / V4L2) ==================
CAM_INDEX = 0                  # /dev/video0 (ajusta si toca)
USE_V4L2 = True                # intenta abrir con backend V4L2
FRAME_W, FRAME_H = 1280, 720   # resolución deseada
TARGET_FPS = 25.0              # límite de FPS en vista previa
FOURCC = "MJPG"                # suele ir mejor con webcams en Linux

# ================== Config DeepFace / Enrolamiento ==================
DB_PATH = Path("embeddings_db.json")
MODEL_NAME = "ArcFace"          # Preciso y rápido en CPU
DETECTOR_BACKEND = "opencv"     # Si quieres más robustez a caras pequeñas, prueba "mediapipe"
POSES = [
    "Mira de frente",
    "Gira la cabeza ligeramente a la IZQUIERDA",
    "Gira la cabeza ligeramente a la DERECHA",
    "Inclina un poco la cabeza hacia ARRIBA",
]
FRAMES_PER_POSE = 12            # Capturamos varios y elegimos el más nítido
LAPLACE_MIN_FOCUS = 60.0        # Umbral de nitidez mínimo aconsejado

# ================== Utilidades de cámara ==================
def open_camera(cam_index=CAM_INDEX, use_v4l2=USE_V4L2, w=FRAME_W, h=FRAME_H, fourcc=FOURCC):
    # 1) Intenta abrir con backend por defecto
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened() and use_v4l2:
        # 2) Intenta V4L2 explícito
        cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L2)

    if not cap.isOpened():
        return None

    # Ajustes deseados (que acepte lo que pueda)
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        # Nota: CV_CAP_PROP_FPS es “best effort” en muchas webcams
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    except Exception:
        pass

    # Warm-up de la cámara
    for _ in range(5):
        cap.read()
    return cap

def limit_fps(prev_t, target_fps=TARGET_FPS):
    """Retorna el nuevo timestamp tras dormir lo necesario para aproximar FPS."""
    if target_fps <= 0:
        return time.time()
    interval = 1.0 / target_fps
    now = time.time()
    dt = now - prev_t
    if dt < interval:
        time.sleep(interval - dt)
    return time.time()

# ================== DeepFace helpers ==================
def variance_of_laplacian(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def best_face_frame(frames):
    # Devuelve el frame más nítido entre los que sí detectan cara (por Laplaciano)
    scored = []
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        score = variance_of_laplacian(gray)
        scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None

def represent_face(bgr_img):
    # DeepFace espera RGB
    rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
    reps = DeepFace.represent(
        img_path=rgb,
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        enforce_detection=True
    )
    # Tomamos el primer rostro detectado
    return np.array(reps[0]["embedding"], dtype=np.float32)

# ================== Persistencia ==================
def load_db():
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": []}

def save_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def add_or_update_user(db, name, embedding_vec):
    # Si ya existe, actualizamos con la media nueva de todas sus huellas
    for user in db["users"]:
        if user["name"].lower() == name.lower():
            prev = np.array(user["embedding"], dtype=np.float32)
            merged = (prev + embedding_vec) / 2.0
            user["embedding"] = merged.tolist()
            user["updated_at"] = datetime.utcnow().isoformat()
            return db
    # Si no existe, lo añadimos
    db["users"].append({
        "name": name,
        "embedding": embedding_vec.tolist(),
        "created_at": datetime.utcnow().isoformat()
    })
    return db

# ================== Main ==================
def main():
    name = input("Introduce el NOMBRE del usuario a registrar: ").strip()
    if not name:
        print("Nombre vacío. Saliendo.")
        return

    cap = open_camera()
    if cap is None or not cap.isOpened():
        print("No se pudo abrir la cámara (V4L2). Verifica /dev/video* y permisos.")
        return

    # Ventana adaptable (suele ir mejor en Wayland/X11)
    cv2.namedWindow("Alta de usuario", cv2.WINDOW_NORMAL)

    collected_embeddings = []
    print("\nInstrucciones:")
    print("- Colócate centrado, con buena luz (evita contraluz).")
    print("- Quita gafas de sol o mascarillas.")
    print("- Mantén la cara dentro del recuadro.\n")

    prev_t = time.time()

    for idx, pose_text in enumerate(POSES, start=1):
        print(f"[{idx}/{len(POSES)}] {pose_text}. Pulsa ESPACIO para empezar a capturar esta pose.")
        # Vista previa fluida ~25 FPS hasta pulsar espacio
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            disp = frame.copy()
            h, w = disp.shape[:2]
            cv2.rectangle(disp, (int(w*0.15), int(h*0.15)), (int(w*0.85), int(h*0.85)), (255,255,255), 2)
            cv2.putText(disp, pose_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
            cv2.putText(disp, "Pulsa ESPACIO para capturar / ESC para salir", (20, h-20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.imshow("Alta de usuario", disp)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                cap.release()
                cv2.destroyAllWindows()
                return
            if key == 32:  # SPACE
                break
            # cap de FPS
            prev_t = limit_fps(prev_t, TARGET_FPS)

        # Capturamos varios frames para escoger el más nítido
        batch = []
        for _ in range(FRAMES_PER_POSE):
            ok, frame = cap.read()
            if ok:
                batch.append(frame)
            # captura rápida: no capamos FPS aquí para quedarnos con los “mejores” instantáneos

        best = best_face_frame(batch)
        if best is None:
            print("No se encontraron caras nítidas en esta pose. Repitiendo…")
            continue

        # Comprobación de nitidez (opcional, solo informativa)
        sharp = variance_of_laplacian(cv2.cvtColor(best, cv2.COLOR_BGR2GRAY))
        if sharp < LAPLACE_MIN_FOCUS:
            print(f"Aviso: imagen poco nítida (score={sharp:.1f}). Intenta más luz/estabilidad.")

        try:
            emb = represent_face(best)
            collected_embeddings.append(emb)
            print("✓ Pose capturada.")
        except Exception as e:
            print(f"No se pudo extraer el embedding de esta pose: {e}. Repitiendo…")
            continue

    cap.release()
    cv2.destroyAllWindows()

    if not collected_embeddings:
        print("No se obtuvo ninguna pose válida. Saliendo.")
        return

    # Media de embeddings y normalización (mejora comparaciones por coseno)
    mean_emb = np.mean(collected_embeddings, axis=0)
    mean_emb = mean_emb / (np.linalg.norm(mean_emb) + 1e-9)

    db = load_db()
    db = add_or_update_user(db, name, mean_emb)
    save_db(db)
    print(f"Usuario '{name}' registrado correctamente en {DB_PATH}.")

if __name__ == "__main__":
    main()
