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
    - NO revienta el proceso si /tts no está disponible: lo deja marcado como no disponible
      y lo indica con logs cuando se le llama.
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
        :param wait_timeout: Segundos para intentar conectar con /tts en el arranque
        """
        if create_node_if_needed and not rospy.core.is_initialized():
            rospy.init_node(node_name, anonymous=True, disable_signals=True)

        self._tts_name = tts_action_name
        self._client = actionlib.SimpleActionClient(self._tts_name, TtsAction)
        self._lock = threading.Lock()

        # Estado interno de conexión
        self._available = False          # si hemos conseguido conectar con /tts alguna vez
        self._initialized = False        # si ya hemos intentado la primera conexión
        self._connect_lock = threading.Lock()
        self._wait_timeout = float(wait_timeout)

        # Intento de conexión inicial (NO lanza excepción si falla)
        self._try_connect(initial=True)

    # ------------------------------------------------------------------ #
    #  Conexión al servidor de TTS                                       #
    # ------------------------------------------------------------------ #

    def _try_connect(self, initial: bool = False, extra_timeout: Optional[float] = None) -> bool:
        """
        Intenta conectar con el servidor de TTS si aún no está disponible.

        :param initial: True si es el intento inicial (solo para logs más claros)
        :param extra_timeout: timeout específico para este intento (si None, usa self._wait_timeout)
        :return: True si queda conectado, False si no.
        """
        timeout = float(extra_timeout) if extra_timeout is not None else self._wait_timeout

        with self._connect_lock:
            # Si ya está marcado como disponible, no hacemos nada
            if self._available:
                return True

            # Solo para el primer intento (por información)
            ctx = "inicial" if initial else "reintento"
            rospy.loginfo(f"[TiagoSpeaker] ({ctx}) Esperando TTS server en '{self._tts_name}' (timeout={timeout:.1f}s)...")

            ok = False
            try:
                ok = self._client.wait_for_server(rospy.Duration(timeout))
            except Exception as e:
                rospy.logerr(f"[TiagoSpeaker] Error esperando al TTS en '{self._tts_name}': {e}")
                ok = False

            self._initialized = True
            if not ok:
                rospy.logerr(
                    f"[TiagoSpeaker] No se encontró el action server de TTS en '{self._tts_name}' "
                    f"dentro de {timeout:.1f} s. El TTS se considera NO disponible."
                )
                self._available = False
                return False

            self._available = True
            rospy.loginfo("[TiagoSpeaker] Conectado a TTS server.")
            return True

    # ------------------------------------------------------------------ #
    #  Métodos públicos                                                  #
    # ------------------------------------------------------------------ #

    def speak(
        self,
        text: str,
        lang_id: str = "es_ES",
        say_timeout: float = 5.0,
    ) -> bool:
        """
        Envía un texto al TTS y espera a que termine (o a que expire el timeout).

        :param text: Texto a decir (sin SSML; usa TtsGoal.rawtext)
        :param lang_id: Idioma. Ej: "es_ES".
        :param say_timeout: Timeout de espera para la ejecución (segundos)
        :return: True si el action reporta fin dentro del timeout, False en caso contrario
        """
        if not text:
            rospy.logwarn("[TiagoSpeaker] Texto vacío; no se envía al TTS.")
            return False

        # Si aún no tenemos TTS disponible, intentamos (re)conectar rápidamente
        if not self._available:
            # Reintento corto (por ejemplo, 2s) por si el TTS se ha levantado después
            self._try_connect(initial=False, extra_timeout=2.0)

        if not self._available:
            rospy.logwarn(f"[TiagoSpeaker] TTS NO disponible. No se puede decir: '{text}'")
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

        # Si aún no tenemos TTS disponible, intentamos (re)conectar rápidamente
        if not self._available:
            self._try_connect(initial=False, extra_timeout=2.0)

        if not self._available:
            rospy.logwarn(f"[TiagoSpeaker] TTS NO disponible. No se puede decir (async): '{text}'")
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
            rospy.logwarn("El TTS no confirmó dentro del timeout o no estaba disponible.")
    except Exception as e:
        rospy.logerr(f"No se pudo ejecutar la prueba de TTS: {e}")
