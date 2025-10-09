#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import threading
import argparse

import numpy as np
import cv2
import rospy
from sensor_msgs.msg import CompressedImage, Image

# MediaPipe
import mediapipe as mp
mp_drawing  = mp.solutions.drawing_utils
mp_styles   = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic

# ---------- Fuente ROS (mantiene solo el último frame decodificado) ----------
class RosImageSource:
    def __init__(self, topic, compressed=True, queue_size=5):
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
            # Para topics de tipo sensor_msgs/Image (raw) necesitas cv_bridge
            from cv_bridge import CvBridge
            self._bridge = CvBridge()
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

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="/xtion/rgb/image_raw/compressed",
                    help="Topic de la cámara (CompressedImage o Image)")
    ap.add_argument("--compressed", action="store_true",
                    help="Marcar si el topic es CompressedImage (JPEG). Si no, se asume Image (raw).")
    ap.add_argument("--fps_cap", type=float, default=30.0,
                    help="Límite de FPS de procesado/visualización (0 = sin límite)")
    ap.add_argument("--mirror", action="store_true", help="Vista espejo")
    ap.add_argument("--complexity", type=int, default=1, choices=[0,1,2],
                    help="Holistic model_complexity")
    args = ap.parse_args()

    # ROS: no capturamos señales (usamos OpenCV loop)
    rospy.init_node("holistic_ros_cam", anonymous=True, disable_signals=True)

    src = RosImageSource(topic=args.topic, compressed=args.compressed, queue_size=5)

    # Hilo de spin para ROS
    threading.Thread(target=rospy.spin, daemon=True).start()

    # MediaPipe Holistic
    with mp_holistic.Holistic(
        static_image_mode=False,
        model_complexity=args.complexity,
        smooth_landmarks=True,
        refine_face_landmarks=True,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as holistic:

        print(f"[Holistic] complexity={args.complexity} | topic={args.topic} | compressed={args.compressed}")
        prev_t = time.time()
        frame_interval = (1.0/args.fps_cap) if args.fps_cap > 0 else 0.0

        while not rospy.is_shutdown():
            bgr = src.latest_bgr()
            if bgr is None:
                # Espera corta para no quemar CPU si aún no llegan frames
                time.sleep(0.002)
                continue

            if args.mirror:
                bgr = cv2.flip(bgr, 1)

            # MediaPipe usa RGB
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            results = holistic.process(rgb)

            # Dibujo de landmarks
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    bgr, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style()
                )
            if results.face_landmarks:
                mp_drawing.draw_landmarks(
                    bgr, results.face_landmarks, mp_holistic.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_styles.get_default_face_mesh_tesselation_style()
                )
                mp_drawing.draw_landmarks(
                    bgr, results.face_landmarks, mp_holistic.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_styles.get_default_face_mesh_contours_style()
                )
            if results.left_hand_landmarks:
                mp_drawing.draw_landmarks(
                    bgr, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_hand_landmarks_style(),
                    connection_drawing_spec=mp_styles.get_default_hand_connections_style()
                )
            if results.right_hand_landmarks:
                mp_drawing.draw_landmarks(
                    bgr, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_styles.get_default_hand_landmarks_style(),
                    connection_drawing_spec=mp_styles.get_default_hand_connections_style()
                )

            # FPS overlay
            now = time.time()
            fps = 1.0 / (now - prev_t) if now > prev_t else 0.0
            prev_t = now
            cv2.putText(bgr, f"FPS: {fps:.1f} | recv:{src.received_count()}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20,220,20), 2, cv2.LINE_AA)

            cv2.imshow("Holistic from ROS (q para salir)", bgr)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

            # Cap de FPS de procesado (opcional)
            if frame_interval > 0:
                t_spent = time.time() - now
                t_sleep = frame_interval - t_spent
                if t_sleep > 0:
                    time.sleep(t_sleep)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
