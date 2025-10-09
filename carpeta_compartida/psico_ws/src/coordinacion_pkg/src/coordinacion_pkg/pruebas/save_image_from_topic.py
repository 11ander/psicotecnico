#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import argparse
import threading
from datetime import datetime

import rospy
from sensor_msgs.msg import Image, CompressedImage, CameraInfo

try:
    from cv_bridge import CvBridge
    _HAS_BRIDGE = True
except Exception:
    _HAS_BRIDGE = False

import cv2
import numpy as np

class ImageSaver:
    def __init__(self, topic, out_dir, prefix, count, timeout, queue_size, use_camera_info):
        self.topic = topic
        self.out_dir = out_dir
        self.prefix = prefix
        self.count = count
        self.timeout = timeout
        self.queue_size = queue_size
        self.use_camera_info = use_camera_info

        os.makedirs(self.out_dir, exist_ok=True)
        self.bridge = CvBridge() if _HAS_BRIDGE else None

        self.saved = 0
        self.msg_event = threading.Event()
        self.last_stamp = None
        self.camera_model = None  # optional: store CameraInfo if needed

        # Subscribe lazily (we don’t know yet if it’s raw or compressed)
        # We’ll try both; only the matching one will deliver messages.
        self.sub_raw = rospy.Subscriber(self.topic, Image, self.cb_image, queue_size=self.queue_size)
        self.sub_cmp = rospy.Subscriber(self.topic, CompressedImage, self.cb_compressed, queue_size=self.queue_size)

        if self.use_camera_info:
            # Try to infer camera_info topic if it exists (common patterns)
            ci_guess = self.guess_camera_info_topic(self.topic)
            self.sub_ci = rospy.Subscriber(ci_guess, CameraInfo, self.cb_camerainfo, queue_size=1)
            rospy.loginfo("Listening for CameraInfo on: %s", ci_guess)
        else:
            self.sub_ci = None

    def guess_camera_info_topic(self, img_topic):
        # Typical mappings: replace last element with camera_info or append /camera_info
        if img_topic.endswith("/image_raw") or img_topic.endswith("/image_rect") or img_topic.endswith("/image_rect_color"):
            return img_topic.rsplit("/", 1)[0] + "/camera_info"
        # Fallback: common TIAGO xtion mapping
        if "/rgb/" in img_topic:
            return img_topic.split("/rgb/")[0] + "/rgb/camera_info"
        if "/depth/" in img_topic:
            return img_topic.split("/depth/")[0] + "/depth/camera_info"
        return img_topic + "/camera_info"

    def cb_camerainfo(self, msg):
        self.camera_model = msg  # store if later you want intrinsics

    def _save_cv_image(self, cv_img, stamp):
        # Build filename
        ts = datetime.fromtimestamp(stamp.to_sec()).strftime("%Y%m%d_%H%M%S_%f")
        name = f"{self.prefix}_{ts}_{self.saved:04d}.png"
        path = os.path.join(self.out_dir, name)
        ok = cv2.imwrite(path, cv_img)
        if ok:
            rospy.loginfo("Saved %s", path)
            self.saved += 1
        else:
            rospy.logerr("Failed to write %s", path)

    def cb_image(self, msg: Image):
        if self.saved >= self.count:
            return
        if not _HAS_BRIDGE:
            rospy.logerr("cv_bridge no está instalado. Instálalo y reintenta: sudo apt install ros-$ROS_DISTRO-cv-bridge")
            return
        try:
            # Force color to BGR for OpenCV
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self._save_cv_image(cv_img, msg.header.stamp if msg.header.stamp else rospy.Time.now())
            if self.saved >= self.count:
                self.msg_event.set()
        except Exception as e:
            rospy.logerr("Error convirtiendo Image: %s", e)

    def cb_compressed(self, msg: CompressedImage):
        if self.saved >= self.count:
            return
        try:
            np_arr = np.frombuffer(msg.data, dtype=np.uint8)
            cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)  # -> BGR
            if cv_img is None:
                rospy.logerr("cv2.imdecode devolvió None (posible corrupción de datos).")
                return
            stamp = msg.header.stamp if msg.header.stamp else rospy.Time.now()
            self._save_cv_image(cv_img, stamp)
            if self.saved >= self.count:
                self.msg_event.set()
        except Exception as e:
            rospy.logerr("Error decodificando CompressedImage: %s", e)

    def spin_until_done(self):
        if self.count <= 0:
            rospy.logwarn("count <= 0, nada que guardar.")
            return
        # Wait until we have saved desired count or timeout
        if not self.msg_event.wait(self.timeout):
            rospy.logwarn("Timeout alcanzado. Guardadas %d/%d imágenes.", self.saved, self.count)

def main():
    parser = argparse.ArgumentParser(description="Guardar imágenes de un topic ROS en PNG.")
    parser.add_argument("--topic", "-t", type=str, required=False,
                        default="/xtion/rgb/image_raw",
                        help="Topic de imagen (sensor_msgs/Image o sensor_msgs/CompressedImage).")
    parser.add_argument("--out", "-o", type=str, default="captures",
                        help="Carpeta de salida (se crea si no existe).")
    parser.add_argument("--prefix", "-p", type=str, default="frame",
                        help="Prefijo de nombre de archivo.")
    parser.add_argument("--count", "-n", type=int, default=1,
                        help="Número de imágenes a guardar (por defecto 1).")
    parser.add_argument("--timeout", "-w", type=float, default=10.0,
                        help="Tiempo máx. de espera en segundos.")
    parser.add_argument("--queue-size", "-q", type=int, default=10,
                        help="queue_size del suscriptor.")
    parser.add_argument("--camera-info", action="store_true",
                        help="(Opcional) Escuchar CameraInfo asociado.")
    args = parser.parse_args()

    rospy.init_node("image_topic_saver", anonymous=True)
    saver = ImageSaver(args.topic, args.out, args.prefix, args.count, args.timeout, args.queue_size, args.camera_info)
    saver.spin_until_done()

if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
