#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
from collections import deque
import numpy as np
import cv2
import rospy
from sensor_msgs.msg import CompressedImage, Image

# --- Qt (PyQt5 -> fallback PySide6) ---
try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    QtModule = "PyQt5"
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    QtModule = "PySide6"

# cv_bridge solo si usas Image (no necesario para CompressedImage)
try:
    from cv_bridge import CvBridge
    HAS_BRIDGE = True
except Exception:
    HAS_BRIDGE = False
    CvBridge = None


class FrameBuffer(QtCore.QObject):
    """Buffer para reproducir fluido: push en callbacks, pop en el QTimer."""
    def __init__(self, maxlen=300, buffered=True, prebuffer=60):
        super().__init__()
        self.buffered = buffered
        self.prebuffer = prebuffer
        self._dq = deque(maxlen=maxlen)
        self._lock = QtCore.QReadWriteLock()
        self._received = 0

        # Para modo 'live' (sin latencia): solo mantenemos el último frame
        self._last = None

    def push(self, bgr):
        if bgr is None:
            return
        self._received += 1
        self._lock.lockForWrite()
        if self.buffered:
            self._dq.append(bgr)
        else:
            self._last = bgr
        self._lock.unlock()

    def ready(self):
        """¿Hay frames suficientes para empezar? (solo en buffered)"""
        if not self.buffered:
            return True
        self._lock.lockForRead()
        ok = len(self._dq) >= self.prebuffer
        self._lock.unlock()
        return ok

    def pop_for_render(self):
        """Devuelve el frame a mostrar:
           - buffered: FIFO (más suave, más latencia)
           - live: el último disponible (mínima latencia)
        """
        self._lock.lockForWrite()
        frame = None
        if self.buffered:
            if self._dq:
                frame = self._dq.popleft()
        else:
            frame = self._last
        self._lock.unlock()
        return frame

    def stats(self):
        self._lock.lockForRead()
        ln = len(self._dq)
        self._lock.unlock()
        return self._received, ln


class CompressedSubscriber(QtCore.QObject):
    """Suscriptor a CompressedImage (rápido, poco tráfico)."""
    def __init__(self, topic, fb: FrameBuffer, queue_size=5):
        super().__init__()
        self.topic = topic
        self.fb = fb
        self.sub = rospy.Subscriber(topic, CompressedImage, self._cb, queue_size=queue_size)
        rospy.loginfo("Subscribed to (CompressedImage): %s", topic)

    def _cb(self, msg: CompressedImage):
        try:
            np_arr = np.frombuffer(msg.data, dtype=np.uint8)
            bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if bgr is not None:
                self.fb.push(bgr)
        except Exception as e:
            rospy.logerr_throttle(2.0, f"Error decoding compressed: {e}")


class RawSubscriber(QtCore.QObject):
    """Suscriptor a Image (por si necesitas raw)."""
    def __init__(self, topic, fb: FrameBuffer, queue_size=1):
        super().__init__()
        if not HAS_BRIDGE:
            rospy.logwarn("cv_bridge no disponible; instala ros-$ROS_DISTRO-cv-bridge para usar raw.")
        self.topic = topic
        self.fb = fb
        self.bridge = CvBridge() if HAS_BRIDGE else None
        self.sub = rospy.Subscriber(topic, Image, self._cb, queue_size=queue_size)
        rospy.loginfo("Subscribed to (Image): %s", topic)

    def _cb(self, msg: Image):
        if self.bridge is None:
            return
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self.fb.push(bgr)
        except Exception as e:
            rospy.logerr_throttle(2.0, f"Error converting raw: {e}")


class ImageWidget(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setText("Esperando frames...")

    @staticmethod
    def bgr_to_qimage(bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
        return qimg.copy()  # asegurar vida de datos

    def show_frame(self, bgr):
        if bgr is None:
            return
        qimg = self.bgr_to_qimage(bgr)
        pix = QtGui.QPixmap.fromImage(qimg)
        scaled = pix.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.setPixmap(scaled)

    def resizeEvent(self, ev):
        if self.pixmap():
            self.setPixmap(self.pixmap().scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        super().resizeEvent(ev)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, topic, fps, buffered, prebuffer, maxbuf, use_raw, queue_size):
        super().__init__()
        self.setWindowTitle(f"ROS Compressed Viewer ({'buffered' if buffered else 'live'}) @ {fps} FPS")
        self.viewer = ImageWidget()
        self.setCentralWidget(self.viewer)
        self.status = self.statusBar()

        # Buffer
        self.fb = FrameBuffer(maxlen=maxbuf, buffered=buffered, prebuffer=prebuffer)

        # Suscriptor
        if use_raw:
            self.sub = RawSubscriber(topic, self.fb, queue_size=queue_size)
        else:
            self.sub = CompressedSubscriber(topic, self.fb, queue_size=max(queue_size, 5))

        # Timer de reproducción
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000.0 / fps))

        # Actualiza barra de estado
        self.info_timer = QtCore.QTimer(self)
        self.info_timer.timeout.connect(self._update_status)
        self.info_timer.start(500)

    @QtCore.pyqtSlot()
    def _tick(self):
        if not self.fb.ready():
            # Aún rellenando prebuffer
            return
        frame = self.fb.pop_for_render()
        if frame is not None:
            self.viewer.show_frame(frame)

    def _update_status(self):
        rec, ln = self.fb.stats()
        self.status.showMessage(f"Recibidos: {rec} | En buffer: {ln} | Qt: {QtModule}")


def parse_args():
    ap = argparse.ArgumentParser(description="Visor ROS (compressed/raw) con buffer para fluidez.")
    ap.add_argument("--topic", "-t", type=str, default="/xtion/rgb/image_raw/compressed",
                    help="Topic de imagen. Ej: /xtion/rgb/image_raw/compressed (CompressedImage) o /xtion/rgb/image_raw (Image).")
    ap.add_argument("--fps", type=float, default=25.0, help="FPS de reproducción (p.ej. 25).")
    ap.add_argument("--buffered", action="store_true",
                    help="Activar reproducción bufferizada (más fluida, más latencia).")
    ap.add_argument("--prebuffer", type=int, default=50,
                    help="Frames a acumular antes de empezar (solo buffered).")
    ap.add_argument("--maxbuf", type=int, default=300,
                    help="Tamaño máximo del buffer (solo buffered).")
    ap.add_argument("--raw", action="store_true",
                    help="Usar sensor_msgs/Image en lugar de CompressedImage.")
    ap.add_argument("--queue-size", type=int, default=5,
                    help="queue_size del suscriptor ROS.")
    return ap.parse_args()


def main():
    args = parse_args()

    # Arrancar ROS sin capturar señales (las maneja Qt)
    rospy.init_node("qt_image_view_buffered", anonymous=True, disable_signals=True)

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(topic=args.topic, fps=args.fps, buffered=args.buffered,
                     prebuffer=args.prebuffer, maxbuf=args.maxbuf,
                     use_raw=args.raw, queue_size=args.queue_size)
    win.resize(960, 600)
    win.show()

    # Hilo para rospy.spin (ROS1)
    import threading
    spin_thread = threading.Thread(target=rospy.spin, daemon=True)
    spin_thread.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
