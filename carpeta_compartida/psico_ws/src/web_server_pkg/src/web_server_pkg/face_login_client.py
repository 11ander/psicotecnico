#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import rospy
import actionlib
from face_recognition_pkg.msg import FaceRecognitionAction, FaceRecognitionGoal

class FaceLoginClient:
    """
    Cliente ROS para el action 'face_recognition_action'.
    Se inicializa de forma perezosa (lazy) y es seguro para usar desde Flask.
    """

    _init_lock = threading.Lock()
    _initialized = False
    _client = None

    ACTION_NAME = "face_recognition_action"

    @classmethod
    def _ensure_init(cls, wait_server_timeout=10.0):
        """Inicializa rospy y el SimpleActionClient solo una vez."""
        if cls._initialized:
            return

        with cls._init_lock:
            if cls._initialized:
                return

            # Importante: disable_signals=True para no interferir con Flask
            rospy.init_node("web_login_face_client", anonymous=True, disable_signals=True)
            cls._client = actionlib.SimpleActionClient(cls.ACTION_NAME, FaceRecognitionAction)

            ok = cls._client.wait_for_server(rospy.Duration(wait_server_timeout))
            if not ok:
                raise RuntimeError(
                    f"No se encontró el servidor de acción '{cls.ACTION_NAME}' en {wait_server_timeout:.1f}s. "
                    "Asegúrate de tener lanzado el face_recognition_action_server en otra terminal."
                )

            cls._initialized = True

    @classmethod
    def recognize_user(cls, timeout=20.0):
        """
        Envía un goal ejecutar=True y espera resultado hasta 'timeout' segundos.
        Devuelve el nombre reconocido (str) o None si no hay reconocimiento a tiempo.
        """
        cls._ensure_init()

        goal = FaceRecognitionGoal()
        goal.ejecutar = True

        cls._client.send_goal(goal)
        finished = cls._client.wait_for_result(rospy.Duration(timeout))
        if not finished:
            # Cancelar educadamente si se excede el timeout
            cls._client.cancel_goal()
            return None

        result = cls._client.get_result()
        if not result:
            return None
        nombre = (result.nombre or "").strip()
        return nombre if nombre else None
