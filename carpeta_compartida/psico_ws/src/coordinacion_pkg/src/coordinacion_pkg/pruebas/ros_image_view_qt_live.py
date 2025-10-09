#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import numpy as np
import cv2
import rospy
from sensor_msgs.msg import CompressedImage

# --- Qt (PyQt5 -> fallback PySide6) ---
try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    QtModule = "PyQt5"
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    QtModule = "PySide6"

# ====== PARÁMETROS FIJOS (CAJA NEGRA) ======
TOPIC = "/xtion/rgb/image_raw/compressed"
FPS = 25
QUEUE_SIZE = 5
# ===========================================


class LiveCompressedSource(QtCore.QObject):
    """Mantiene SOLO el último frame decodificado (BGR) desde CompressedImage."""
    def __init__(self, topic=TOPIC, queue_size=QUEUE_SIZE):
        super().__init__()
        self.topic = topic
        self._lock = QtCore.QReadWriteLock()
        self._last_bgr = None
        self._received = 0
        self.sub = rospy.Subscriber(self.topic, CompressedImage, self._cb, queue_size=queue_size)
        rospy.loginfo("Suscrito (CompressedImage): %s | queue_size=%d", self.topic, queue_size)

    def _cb(self, msg: CompressedImage):
        try:
            np_arr = np.frombuffer(msg.data, dtype=np.uint8)
            bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if bgr is None:
                return
            self._lock.lockForWrite()
            self._last_bgr = bgr
            self._received += 1
            self._lock.unlock()
        except Exception as e:
            rospy.logerr_throttle(2.0, f"Error decodificando compressed: {e}")

    def latest_bgr(self):
        self._lock.lockForRead()
        frame = self._last_bgr
        self._lock.unlock()
        return frame

    def received_count(self):
        self._lock.lockForRead()
        n = self._received
        self._lock.unlock()
        return n


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
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ROS Live Compressed Viewer @ {int(FPS)} FPS | {TOPIC}")
        self.viewer = ImageWidget()
        self.setCentralWidget(self.viewer)
        self.status = self.statusBar()

        self.src = LiveCompressedSource(topic=TOPIC, queue_size=QUEUE_SIZE)

        # Timer de render fijo (LIVE)
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000.0 / max(FPS, 1.0)))

        # Info de estado
        self.info_timer = QtCore.QTimer(self)
        self.info_timer.timeout.connect(self._update_status)
        self.info_timer.start(500)

    @QtCore.pyqtSlot()
    def _tick(self):
        frame = self.src.latest_bgr()
        if frame is not None:
            self.viewer.show_frame(frame)

    def _update_status(self):
        rec = self.src.received_count()
        self.status.showMessage(f"Recibidos: {rec} | Topic: {TOPIC} | Qt: {QtModule}")


def main():
    # Arranca ROS sin capturar señales (las maneja Qt)
    rospy.init_node("qt_image_view_live_fixed", anonymous=True, disable_signals=True)

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(960, 600)
    win.show()

    # Hilo para rospy.spin (ROS1)
    import threading
    threading.Thread(target=rospy.spin, daemon=True).start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
