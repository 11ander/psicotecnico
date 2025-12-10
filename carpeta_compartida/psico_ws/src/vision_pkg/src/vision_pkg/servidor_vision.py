#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Servidor de acción de la prueba de visión para TIAGo.

Responsabilidades de ESTE nodo:
  - Mover la base a las posiciones de visión (punto_vision2 y punto_vision3).
  - Colocar el brazo en una pose para mostrar el cuaderno.
  - Girar la muñeca 180º para mostrar la parte trasera del cuaderno.
  - Dar mensajes cortos de contexto (“lee la primera frase”, “lee la segunda frase”).
  - Devolver en el VisionResult las frases originales que están escritas en el cuaderno.

IMPORTANTE:
  - La EXPLICACIÓN general de la prueba de visión y las instrucciones largas
    al paciente las da el webserver (Flask), NO este servidor.
  - Aquí solo damos mensajes cortos sincronizados con los movimientos.

Este script asume que están corriendo:
  * /arm_controller/follow_joint_trajectory
  * /gripper_controller/command
  * /joint_states
  * /move_base/goal y /robot_pose
  * /tts
"""

import math
import copy

import rospy
import actionlib

from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal

from pal_interaction_msgs.msg import TtsAction, TtsGoal

from vision_pkg.msg import VisionAction, VisionResult, VisionFeedback

# Usamos el Follower del profe para la base
# Probamos varias rutas posibles para poder reutilizar el mismo archivo
try:
    from web_server_pkg.checkpoint_follower_api import Follower as CheckpointFollower
except ImportError:
    try:
        from mover_pkg.checkpoint_follower_api import Follower as CheckpointFollower
    except ImportError:
        # Por si tienes el script en el propio vision_pkg
        from checkpoint_follower_api import Follower as CheckpointFollower


# ------------- Constantes de la prueba -------------

# Articulaciones del brazo TIAGo (orden esperado por /arm_controller)
ARM_JOINTS = [
    "arm_1_joint",
    "arm_2_joint",
    "arm_3_joint",
    "arm_4_joint",
    "arm_5_joint",
    "arm_6_joint",
    "arm_7_joint",
]

# Joint del gripper (solo controlamos un dedo; el otro se mueve solidario)
GRIPPER_JOINT = "gripper_left_finger_joint"

# Pose "bonita" para mostrar el cuaderno delante del robot
# Ajusta estos valores si ves que la postura no es la que quieres.
ARM_POSE_MOSTRAR_CUADERNO = [
    1.46,   # arm_1_joint
    1.02,   # arm_2_joint
    -0.08,  # arm_3_joint
    0.97,   # arm_4_joint
    1.53,   # arm_5_joint
    -1.39,  # arm_6_joint
    -1.77,  # arm_7_joint
]

# Tiempos de espera para que el paciente lea (ajusta a gusto)
TIEMPO_LECTURA_1 = 6.0  # segundos primera frase
TIEMPO_LECTURA_2 = 6.0  # segundos segunda frase

# Frases que están escritas físicamente en el cuaderno
# (el webserver usará esto para corregir lo que introduzca el paciente).
FRASE_1_ORIGINAL = "La carretera está mojada."
FRASE_2_ORIGINAL = "Conduce siempre con precaución."

# Mensajes cortos hablados durante la prueba
MENSAJE_FRASE_1 = "Por favor, lee en voz alta la primera frase que ves en la hoja."
MENSAJE_FRASE_2 = "Ahora, sin levantarte, lee en voz alta la segunda frase que aparece por la parte de atrás del cuaderno."


# ---------------------------------------------------
#   Control sencillo del brazo y gripper
# ---------------------------------------------------

class ArmController(object):
    """
    Control directo del brazo y gripper usando:
      - /arm_controller/follow_joint_trajectory
      - /gripper_controller/command
      - /joint_states
    """

    def __init__(self):
        # Cliente del brazo
        self._arm_client = actionlib.SimpleActionClient(
            "/arm_controller/follow_joint_trajectory",
            FollowJointTrajectoryAction,
        )
        rospy.loginfo("[VisionArm] Esperando servidor /arm_controller/follow_joint_trajectory...")
        if not self._arm_client.wait_for_server(rospy.Duration(10.0)):
            rospy.logerr("[VisionArm] No se encontró el servidor del brazo.")
            raise RuntimeError("Sin servidor de brazo")

        # Publicador del gripper
        self._gripper_pub = rospy.Publisher(
            "/gripper_controller/command",
            JointTrajectory,
            queue_size=1,
        )
        rospy.sleep(0.5)
        rospy.loginfo("[VisionArm] Control de brazo y gripper listo.")

    # ---- Lectura de joints ----

    def get_current_arm_positions(self, timeout=5.0):
        """
        Lee /joint_states y devuelve una lista con las posiciones
        de ARM_JOINTS en el mismo orden.
        """
        msg = rospy.wait_for_message("/joint_states", JointState, timeout=timeout)

        pos_map = {name: pos for name, pos in zip(msg.name, msg.position)}

        try:
            positions = [pos_map[j] for j in ARM_JOINTS]
        except KeyError as e:
            rospy.logerr(f"[VisionArm] No se encontró la articulación {e} en /joint_states.")
            raise

        return positions

    # ---- Movimiento del brazo ----

    def move_arm(self, target_positions, duration=3.0):
        """
        Envía una trayectoria simple al brazo (un solo punto en 'duration' segundos).
        """
        if len(target_positions) != len(ARM_JOINTS):
            rospy.logerr("[VisionArm] Número de joints no coincide con ARM_JOINTS.")
            return False

        jt = JointTrajectory()
        jt.joint_names = ARM_JOINTS

        point = JointTrajectoryPoint()
        point.positions = list(target_positions)
        # TIAGo exige velocidades (aunque sean cero)
        point.velocities = [0.0] * len(ARM_JOINTS)
        point.time_from_start = rospy.Duration(duration)

        jt.points = [point]

        goal = FollowJointTrajectoryGoal()
        goal.trajectory = jt
        goal.goal_time_tolerance = rospy.Duration(1.0)

        rospy.loginfo(f"[VisionArm] Moviendo brazo a {target_positions} en {duration:.1f}s.")
        self._arm_client.send_goal(goal)
        finished = self._arm_client.wait_for_result(rospy.Duration(duration + 3.0))

        if not finished:
            rospy.logwarn("[VisionArm] Timeout esperando resultado del movimiento.")
            return False

        state = self._arm_client.get_state()
        ok = (state == 3)  # 3 == SUCCEEDED en actionlib
        if ok:
            rospy.loginfo("[VisionArm] Movimiento completado.")
        else:
            rospy.logerr(f"[VisionArm] Movimiento fallido. Estado actionlib = {state}")
        return ok

    # ---- Gripper ----

    def _send_gripper_position(self, position, duration=2.0):
        """
        Envía comando sencillo al gripper: una sola joint GRIPPER_JOINT.
        position en radianes, pero para TIAGo suele ser proporcional a la apertura.
        """
        traj = JointTrajectory()
        traj.joint_names = [GRIPPER_JOINT]

        point = JointTrajectoryPoint()
        point.positions = [position]
        point.velocities = [0.0]
        point.time_from_start = rospy.Duration(duration)

        traj.points = [point]

        rospy.loginfo(f"[VisionArm] Enviando gripper a posición {position:.3f}.")
        self._gripper_pub.publish(traj)
        rospy.sleep(duration + 0.5)

    def close_gripper(self):
        """Cierra el gripper (cogiendo el cuaderno)."""
        self._send_gripper_position(0.01, duration=2.0)

    def open_gripper(self):
        """Abre el gripper (soltar cuaderno)."""
        self._send_gripper_position(0.08, duration=2.0)

    # ---- Gestos específicos de la prueba ----

    def pose_mostrar_cuaderno(self):
        """
        Lleva el brazo a una pose predefinida que hace que el cuaderno
        quede aproximadamente delante del robot.
        """
        return self.move_arm(ARM_POSE_MOSTRAR_CUADERNO, duration=4.0)

    def rotar_muneca_180(self):
        """
        Gira la muñeca (última joint) 180 grados respecto a su estado actual.
        Sirve para mostrar la parte de atrás del cuaderno.
        """
        current = self.get_current_arm_positions()
        target = copy.deepcopy(current)
        target[-1] = target[-1] + math.pi  # rotar muñeca 180º
        rospy.loginfo(
            f"[VisionArm] Rotando muñeca 180 grados (arm_7 de {current[-1]:.3f} a {target[-1]:.3f})."
        )
        return self.move_arm(target, duration=3.0)


# ---------------------------------------------------
#   Servidor de acción de Visión
# ---------------------------------------------------

class VisionServer(object):
    """
    Action server 'vision_action' para la prueba de visión.

    Goal:
      - bool ejecutar

    Result (VisionResult):
      - string frase_1   # frase frontal del cuaderno
      - string frase_2   # frase trasera del cuaderno
      - bool ok          # True si la secuencia ha ido razonablemente bien

    Feedback (VisionFeedback):
      - string fase
    """

    def __init__(self):
        # Servidor de acción
        self._as = actionlib.SimpleActionServer(
            "vision_action",
            VisionAction,
            execute_cb=self.execute_cb,
            auto_start=False,
        )

        # TTS
        self._tts_client = actionlib.SimpleActionClient("/tts", TtsAction)
        rospy.loginfo("[VisionServer] Esperando servidor /tts...")
        if not self._tts_client.wait_for_server(rospy.Duration(8.0)):
            rospy.logwarn("[VisionServer] No se encontró /tts. Se usarán solo logs para voz.")
            self._tts_client = None
        else:
            rospy.loginfo("[VisionServer] Conectado a /tts.")

        # Checkpoint follower para la base
        try:
            rospy.loginfo("[VisionServer] Inicializando CheckpointFollower...")
            self._follower = CheckpointFollower()
            rospy.loginfo("[VisionServer] CheckpointFollower listo.")
        except Exception as e:
            rospy.logerr(f"[VisionServer] ERROR inicializando CheckpointFollower: {e}")
            self._follower = None

        # Control de brazo
        try:
            self._arm = ArmController()
        except Exception as e:
            rospy.logerr(f"[VisionServer] ERROR inicializando ArmController: {e}")
            self._arm = None

        self._as.start()
        rospy.loginfo("[VisionServer] Action server 'vision_action' listo.")

    # ---- Helpers ----

    def _publish_feedback(self, fase: str):
        fb = VisionFeedback()
        fb.fase = fase
        self._as.publish_feedback(fb)
        rospy.loginfo(f"[VisionServer] Fase: {fase}")

    def _say(self, text: str, lang_id: str = "es_ES", timeout: float = 10.0):
        if not text:
            return
        if self._tts_client is None:
            rospy.loginfo(f"[VisionServer][TTS SIM] {text}")
            return

        goal = TtsGoal()
        goal.rawtext.text = text
        goal.rawtext.lang_id = lang_id

        try:
            self._tts_client.send_goal_and_wait(
                goal,
                rospy.Duration(timeout),
                rospy.Duration(timeout),
            )
        except Exception as e:
            rospy.logerr(f"[VisionServer] Error enviando TTS: {e}")

    def _move_base_to(self, punto, nombre: str):
        """
        Usa CheckpointFollower para mover la base a un punto concreto.
        'punto' debe ser una lista [x, y, oz, ow].
        """
        if self._follower is None:
            rospy.logwarn(f"[VisionServer] No hay follower, no puedo mover a {nombre}.")
            return False
        try:
            rospy.loginfo(f"[VisionServer] Moviendo base a {nombre}: {punto}")
            ok = self._follower.enviar_puntos([punto])
            if not ok:
                rospy.logwarn(f"[VisionServer] Movimiento a {nombre} no confirmado.")
            else:
                rospy.loginfo(f"[VisionServer] Llegado a {nombre}.")
            return ok
        except Exception as e:
            rospy.logerr(f"[VisionServer] ERROR moviendo base a {nombre}: {e}")
            return False

    # ---- Callback del action ----

    def execute_cb(self, goal):
        if not goal.ejecutar:
            rospy.loginfo("[VisionServer] Goal con ejecutar=False → ok=False.")
            result = VisionResult()
            result.ok = False
            # Por coherencia, rellenamos también las frases
            result.frase_1 = FRASE_1_ORIGINAL
            result.frase_2 = FRASE_2_ORIGINAL
            self._as.set_succeeded(result)
            return

        rospy.loginfo("[VisionServer] Iniciando prueba de visión.")
        ok_global = True

        try:
            # Guardar postura inicial del brazo para volver luego
            initial_arm_joints = None
            if self._arm is not None:
                try:
                    initial_arm_joints = self._arm.get_current_arm_positions()
                    rospy.loginfo(f"[VisionServer] Postura inicial brazo: {initial_arm_joints}")
                except Exception as e:
                    rospy.logwarn(f"[VisionServer] No se pudo leer postura inicial del brazo: {e}")

            # 1) Mover base a posición cercana (punto_vision2)
            if self._follower is not None and hasattr(self._follower, "punto_vision2"):
                self._publish_feedback("moviendo_punto_vision2")
                self._move_base_to(self._follower.punto_vision2, "punto_vision2")
            else:
                rospy.logwarn("[VisionServer] No existe punto_vision2 en follower.")

            if self._as.is_preempt_requested():
                rospy.logwarn("[VisionServer] Preempt solicitado tras mover a vision2.")
                self._as.set_preempted()
                return

            # 2) Subir brazo y mostrar cuaderno (mano hacia abajo)
            if self._arm is not None:
                self._publish_feedback("subiendo_brazo")
                if not self._arm.pose_mostrar_cuaderno():
                    rospy.logwarn("[VisionServer] No se pudo alcanzar pose de mostrar cuaderno.")
                    ok_global = False
                self._arm.close_gripper()
            else:
                rospy.logwarn("[VisionServer] Sin control de brazo, no puedo subir el brazo.")
                ok_global = False

            # 3) Leer primera frase
            self._publish_feedback("leyendo_frase_1")
            self._say(MENSAJE_FRASE_1)
            rospy.sleep(TIEMPO_LECTURA_1)

            if self._as.is_preempt_requested():
                rospy.logwarn("[VisionServer] Preempt solicitado tras primera lectura.")
                self._as.set_preempted()
                return

            # 4) Mover base a posición lejana (punto_vision3), manteniendo brazo arriba
            if self._follower is not None and hasattr(self._follower, "punto_vision3"):
                self._publish_feedback("moviendo_punto_vision3")
                self._move_base_to(self._follower.punto_vision3, "punto_vision3")
            else:
                rospy.logwarn("[VisionServer] No existe punto_vision3 en follower.")

            if self._as.is_preempt_requested():
                rospy.logwarn("[VisionServer] Preempt solicitado tras mover a vision3.")
                self._as.set_preempted()
                return

            # 5) Girar muñeca 180 grados (mostrar parte de atrás del cuaderno)
            if self._arm is not None:
                self._publish_feedback("girando_muneca")
                if not self._arm.rotar_muneca_180():
                    rospy.logwarn("[VisionServer] No se pudo girar la muñeca 180 grados.")
                    ok_global = False
            else:
                rospy.logwarn("[VisionServer] Sin control de brazo, no puedo girar muñeca.")
                ok_global = False

            # 6) Leer segunda frase
            self._publish_feedback("leyendo_frase_2")
            self._say(MENSAJE_FRASE_2)
            rospy.sleep(TIEMPO_LECTURA_2)

            if self._as.is_preempt_requested():
                rospy.logwarn("[VisionServer] Preempt solicitado tras segunda lectura.")
                self._as.set_preempted()
                return

            # 7) Bajar brazo a postura inicial
            if self._arm is not None and initial_arm_joints is not None:
                self._publish_feedback("bajando_brazo")
                if not self._arm.move_arm(initial_arm_joints, duration=4.0):
                    rospy.logwarn("[VisionServer] No se pudo volver a la postura inicial del brazo.")
                    ok_global = False
                self._arm.open_gripper()

            # 8) Resultado final
            self._publish_feedback("fin")
            res = VisionResult()
            res.frase_1 = FRASE_1_ORIGINAL
            res.frase_2 = FRASE_2_ORIGINAL
            res.ok = bool(ok_global)
            self._as.set_succeeded(res)
            rospy.loginfo(f"[VisionServer] Prueba de visión finalizada. ok = {res.ok}")

        except Exception as e:
            rospy.logerr(f"[VisionServer] Excepción durante la prueba de visión: {e}")
            res = VisionResult()
            res.frase_1 = FRASE_1_ORIGINAL
            res.frase_2 = FRASE_2_ORIGINAL
            res.ok = False
            self._as.set_aborted(res)


# ---------------------------------------------------
#   main
# ---------------------------------------------------

if __name__ == "__main__":
    rospy.init_node("servidor_vision")
    server = VisionServer()
    rospy.spin()
