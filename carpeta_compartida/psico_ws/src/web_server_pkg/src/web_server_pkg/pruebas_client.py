#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
from typing import Optional, Dict, Any

import rospy
import actionlib
from rpi_pkg.msg import MemoriaAction, MemoriaGoal, ReflejosAction, ReflejosGoal
from audicion_pkg.msg import AudicionAction, AudicionGoal
from coordinacion_pkg.msg import MobilityExamAction, MobilityExamGoal


class _BaseClient:
    _lock = threading.Lock()
    _inited = False

    @classmethod
    def _ensure_node(cls, node_name: str):
        if not rospy.core.is_initialized():
            with cls._lock:
                if not rospy.core.is_initialized():
                    rospy.init_node(node_name, anonymous=True, disable_signals=True)


class MemoriaClient(_BaseClient):
    ACTION_NAME = "memoria"

    @classmethod
    def run(cls, wait_server_timeout: float = 5.0, result_timeout: float = 60.0) -> float:
        cls._ensure_node("web_memoria_client")
        client = actionlib.SimpleActionClient(cls.ACTION_NAME, MemoriaAction)
        if not client.wait_for_server(rospy.Duration(wait_server_timeout)):
            return -1.0
        goal = MemoriaGoal(input=True)
        client.send_goal(goal)
        client.wait_for_result(rospy.Duration(result_timeout))
        res = client.get_result()
        return res.result if res else -1.0


class ReflejosClient(_BaseClient):
    ACTION_NAME = "reflejos"

    @classmethod
    def run(cls, wait_server_timeout: float = 5.0, result_timeout: float = 60.0) -> float:
        cls._ensure_node("web_reflejos_client")
        client = actionlib.SimpleActionClient(cls.ACTION_NAME, ReflejosAction)
        if not client.wait_for_server(rospy.Duration(wait_server_timeout)):
            return -1.0
        goal = ReflejosGoal(input=True)
        client.send_goal(goal)
        client.wait_for_result(rospy.Duration(result_timeout))
        res = client.get_result()
        return res.result if res else -1.0


class AudicionClient(_BaseClient):
    ACTION_NAME = "audicion_action"

    @classmethod
    def run(cls, wait_server_timeout: float = 5.0, result_timeout: float = 180.0) -> Optional[Dict[str, Any]]:
        """
        Devuelve un diccionario con:
          - pulsador_emitidos, pulsador_aciertos, pulsador_fallos, nota_p1
          - conteo_emitidos
          - requiere_input=True e input_schema para pedir en el front el valor de P2 contado por el paciente
        """
        cls._ensure_node("web_audicion_client")
        client = actionlib.SimpleActionClient(cls.ACTION_NAME, AudicionAction)
        if not client.wait_for_server(rospy.Duration(wait_server_timeout)):
            return None

        goal = AudicionGoal()
        if hasattr(goal, "ejecutar"):
            goal.ejecutar = True

        client.send_goal(goal)
        client.wait_for_result(rospy.Duration(result_timeout))
        res = client.get_result()
        if not res:
            return None

        # Esperamos array de 4 enteros: [p1_total, p2_total, p2_aciertos, p2_fallos]
        try:
            p1_total, p2_total, p2_aciertos, p2_fallos = list(res.resultados)
        except Exception:
            return None

        puls_emitidos = int(p2_total)
        puls_aciertos = int(p2_aciertos)
        puls_fallos   = int(p2_fallos)
        conteo_emitidos = int(p1_total)

        # Nota P1 (pulsador) basada en p2 resultados, tal como veníais usando
        puls_emitidos_safe = max(1, puls_emitidos)
        nota_p1 = round(10.0 * (puls_aciertos / puls_emitidos_safe), 2)

        detalles = {
            "pulsador_emitidos": puls_emitidos,
            "pulsador_aciertos": puls_aciertos,
            "pulsador_fallos":   puls_fallos,
            "nota_p1": float(nota_p1),

            "conteo_emitidos": conteo_emitidos,   # Para P2 (conteo)
            "requiere_input": True,
            "input_schema": {
                "titulo": "Audición – Respuesta del paciente (P2: Conteo)",
                "descripcion": "Introduce cuántos pitidos dijo haber escuchado el paciente en la PRUEBA 2 (conteo).",
                "campos": [
                    {"name": "p2_contados_paciente", "label": "¿Cuántos pitidos escuchaste en la PRUEBA 2?", "type": "number", "min": 0}
                ]
            }
        }
        return detalles


class CoordinacionClient:
    """
    Cliente para la prueba de coordinación / movilidad.
    Lanza el action 'mobility_exam_action' con ejecutar=True
    y devuelve:
      - score_100: nota 0–100 del servidor
      - informe: lista de líneas de texto (MobilityExamResult.informe)
      - csv_path, report_path: rutas a los ficheros generados
    """

    ACTION_NAME = "mobility_exam_action"
    _lock = threading.Lock()
    _client = None

    @classmethod
    def _get_client(cls, wait_server_timeout: float = 10.0):
        """
        Inicializa el SimpleActionClient solo una vez.
        NO hace init_node porque el nodo ya lo has inicializado en app.py
        (puente_web_ros).
        """
        if cls._client is not None:
            return cls._client

        with cls._lock:
            if cls._client is not None:
                return cls._client

            client = actionlib.SimpleActionClient(cls.ACTION_NAME, MobilityExamAction)
            ok = client.wait_for_server(rospy.Duration(wait_server_timeout))
            if not ok:
                raise RuntimeError(
                    f"No se encontró el servidor de acción '{cls.ACTION_NAME}' "
                    f"en {wait_server_timeout:.1f}s. ¿Está lanzado mobility_exam_action_server?"
                )

            cls._client = client
            return cls._client

    @classmethod
    def run(cls, timeout: float = 600.0):
        """
        Ejecuta la prueba completa.
        Devuelve (score_100, informe, csv_path, report_path)
        donde score_100 ∈ [0, 100].
        """
        client = cls._get_client()

        goal = MobilityExamGoal()
        goal.ejecutar = True

        client.send_goal(goal)
        finished = client.wait_for_result(rospy.Duration(timeout))
        if not finished:
            client.cancel_goal()
            raise RuntimeError("La prueba de coordinación ha excedido el tiempo máximo.")

        result = client.get_result()
        if not result:
            raise RuntimeError("La prueba de coordinación no devolvió resultado.")

        score_100   = float(result.score)
        informe     = list(result.informe or [])
        csv_path    = str(result.csv_path or "")
        report_path = str(result.report_path or "")

        return score_100, informe, csv_path, report_path