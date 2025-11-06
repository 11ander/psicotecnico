#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pequeña API para hacer hablar al TIAGo usando el action /tts (pal_interaction_msgs).

Uso como librería (desde tu app Flask):
    from speak_api import TiagoSpeaker
    spk = TiagoSpeaker(wait_timeout=10.0)  # espera hasta 10s a que /tts esté disponible
    spk.speak("Hola, soy TIAGo.", lang_id="es_ES", say_timeout=5.0)

Uso como script:
    python3 speak_api.py
    -> hará decir "Este es el mensaje de prueba"
"""

import threading
from typing import Optional

import rospy
import actionlib
from pal_interaction_msgs.msg import TtsAction, TtsGoal


class TiagoSpeaker:
    """
    Wrapper ligero para publicar texto al TTS de TIAGo.

    - Reutiliza un único SimpleActionClient a /tts.
    - Protege las llamadas con un lock por si lo usas desde varios hilos (Flask).
    - No crea nodo ROS si ya existe; si no existe, puede crear uno (opcional).
    """

    def __init__(
        self,
        tts_action_name: str = "/tts",
        create_node_if_needed: bool = False,
        node_name: str = "tiago_speaker_client",
        wait_timeout: float = 10.0,
    ):
        """
        :param tts_action_name: Nombre del action de TTS (por defecto /tts)
        :param create_node_if_needed: Si True, hará rospy.init_node si no hay nodo iniciado
        :param node_name: Nombre del nodo si hay que crearlo
        :param wait_timeout: Segundos para esperar a que /tts esté disponible
        """
        if create_node_if_needed and not rospy.core.is_initialized():
            rospy.init_node(node_name, anonymous=True, disable_signals=True)

        self._tts_name = tts_action_name
        self._client = actionlib.SimpleActionClient(self._tts_name, TtsAction)
        self._lock = threading.Lock()

        rospy.loginfo(f"[TiagoSpeaker] Esperando TTS server en '{self._tts_name}'...")
        ok = self._client.wait_for_server(rospy.Duration(wait_timeout))
        if not ok:
            raise RuntimeError(
                f"No se encontró el action server de TTS en '{self._tts_name}' "
                f"dentro de {wait_timeout} s. ¿Está corriendo TIAGo/tts?"
            )
        rospy.loginfo("[TiagoSpeaker] Conectado a TTS server.")

    def speak(
        self,
        text: str,
        lang_id: str = "es_ES",
        say_timeout: float = 5.0,
    ) -> bool:
        """
        Envía un texto al TTS y espera a que termine (o a que expire el timeout).

        :param text: Texto a decir (sin SSML; usa TtsGoal.rawtext)
        :param lang_id: Idioma. Ej: "es_ES". (Con "en_ES" puede funcionar según setup, pero lo normal es es_ES)
        :param say_timeout: Timeout de espera para la ejecución (segundos)
        :return: True si el action reporta fin dentro del timeout, False en caso contrario
        """
        if not text:
            rospy.logwarn("[TiagoSpeaker] Texto vacío; no se envía al TTS.")
            return False

        goal = TtsGoal()
        # Campo rawtext (según pal_interaction_msgs/TtsGoal)
        goal.rawtext.text = text
        goal.rawtext.lang_id = lang_id

        with self._lock:
            try:
                # send_goal_and_wait(goal, exec_timeout, preempt_timeout)
                self._client.send_goal_and_wait(
                    goal,
                    rospy.Duration(say_timeout),
                    rospy.Duration(say_timeout),
                )
                rospy.loginfo(f"[TiagoSpeaker] TTS OK: '{text}'")
                return True
            except Exception as e:
                rospy.logerr(f"[TiagoSpeaker] Error enviando TTS: {e}")
                return False

    def speak_async(self, text: str, lang_id: str = "es_ES") -> None:
        """
        Envía el goal sin bloquear. Útil si no quieres bloquear el hilo.
        (No hay confirmación de finalización en esta función.)
        """
        if not text:
            rospy.logwarn("[TiagoSpeaker] Texto vacío; no se envía al TTS.")
            return
        goal = TtsGoal()
        goal.rawtext.text = text
        goal.rawtext.lang_id = lang_id
        with self._lock:
            try:
                self._client.send_goal(goal)
                rospy.loginfo(f"[TiagoSpeaker] TTS async enviado: '{text}'")
            except Exception as e:
                rospy.logerr(f"[TiagoSpeaker] Error enviando TTS async: {e}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Prueba rápida: crea nodo si no existe, se conecta a /tts y dice un texto.
    Requisitos:
      - roscore levantado
      - servidor /tts disponible en la red ROS
    """
    try:
        # Creamos nodo si es necesario para uso standalone:
        speaker = TiagoSpeaker(create_node_if_needed=True, wait_timeout=10.0)
        ok = speaker.speak("Este es el mensaje de prueba", lang_id="es_ES", say_timeout=5.0)
        if not ok:
            rospy.logwarn("El TTS no confirmó dentro del timeout.")
    except Exception as e:
        rospy.logerr(f"No se pudo ejecutar la prueba de TTS: {e}")
