import os
import time
import argparse
import cv2
import mediapipe as mp

mp_drawing  = mp.solutions.drawing_utils
mp_styles   = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="/dev/video0", help="Ruta V4L2 (/dev/videoX) o índice (0,1...)")
    ap.add_argument("--width",  type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps",    type=int, default=30)
    ap.add_argument("--mirror", action="store_true", help="Vista espejo")
    ap.add_argument("--complexity", type=int, default=1, choices=[0,1,2], help="Holistic model_complexity")
    args = ap.parse_args()

    # Permite pasar índice numérico o ruta /dev/videoX
    cap_source = args.device
    if args.device.isdigit():
        cap_source = int(args.device)

    # Abrir cámara con backend V4L2
    cap = cv2.VideoCapture(cap_source, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"No se pudo abrir la cámara con {cap_source} (V4L2). Prueba otro /dev/videoX o índice.")
        return

    # Intentar forzar MJPG para ganar FPS y reducir carga de CPU
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS,          args.fps)

    # (Opcional) mostrar lo que realmente quedó
    real_w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    real_fps= cap.get(cv2.CAP_PROP_FPS)
    print(f"[V4L2] {cap_source} -> {real_w}x{real_h} @ {real_fps:.1f} FPS")

    # Config Holistic
    with mp_holistic.Holistic(
        static_image_mode=False,
        model_complexity=args.complexity,   # 0 rápido | 1 balance | 2 más preciso
        smooth_landmarks=True,
        refine_face_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as holistic:

        prev_t = time.time()
        while True:
            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer un frame.")
                break

            if args.mirror:
                frame = cv2.flip(frame, 1)

            # MediaPipe trabaja en RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = holistic.process(rgb)

            # Dibujo pose
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
                )

            # Dibujo face mesh (tesselación + contornos)
            if results.face_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.face_landmarks,
                    mp_holistic.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_styles.get_default_face_mesh_tesselation_style()
                )
                mp_drawing.draw_landmarks(
                    frame,
                    results.face_landmarks,
                    mp_holistic.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_styles.get_default_face_mesh_contours_style()
                )

            # Dibujo manos
            if results.left_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.left_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_hand_landmarks_style(),
                    connection_drawing_spec=mp_styles.get_default_hand_connections_style()
                )
            if results.right_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.right_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_hand_landmarks_style(),
                    connection_drawing_spec=mp_styles.get_default_hand_connections_style()
                )

            # FPS simple
            now = time.time()
            fps = 1.0 / (now - prev_t) if now > prev_t else 0.0
            prev_t = now
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 220, 20), 2, cv2.LINE_AA)

            cv2.imshow("MediaPipe Holistic (q para salir)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
