#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Secuencia de pick & place sencillo para TIAGo: "coger el cuaderno/papel".

Flujo:
  1) Mueve la base a una posición de aproximación lejana (pre-pick-lejos).
  2) Coloca el brazo en la pose de coger papel.
  3) Se aproxima a una posición intermedia cercana.
  4) Se aproxima a la posición final exacta de pick.
  5) Cierra el gripper para agarrar el cuaderno.
  6) Mueve la base a una posición cómoda final para empezar la prueba de visión.

Seguridad:
  - Si haces Ctrl+C en cualquier momento:
      * Se manda cmd_vel = 0 a la base varias veces.
      * Se cancelan todas las goals del brazo.
      * El nodo termina de forma limpia.
"""

import math
import copy
import sys
import traceback

import rospy
import actionlib

from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal

# Follower (para mover la base con /move_base/goal)
try:
    from web_server_pkg.checkpoint_follower_api import Follower as CheckpointFollower
except ImportError:
    try:
        from mover_pkg.checkpoint_follower_api import Follower as CheckpointFollower
    except ImportError:
        # Versión local en vision_pkg
        from checkpoint_follower_api import Follower as CheckpointFollower


# -------------------------------
#   Constantes de este script
# -------------------------------

# Articulaciones de brazo que controla TIAGo (orden importante)
ARM_JOINTS = [
    "arm_1_joint",
    "arm_2_joint",
    "arm_3_joint",
    "arm_4_joint",
    "arm_5_joint",
    "arm_6_joint",
    "arm_7_joint",
]

# Joints del gripper (los dos dedos)
GRIPPER_JOINTS = [
    "gripper_right_finger_joint",
    "gripper_left_finger_joint",
]

# Posiciones del gripper
#  - 0.0, 0.0  → cerrado (lo has comprobado con rostopic pub)
#  - 0.08, 0.08 → abierto (valor típico)
GRIPPER_CLOSED_POS = 0.0
GRIPPER_OPEN_POS   = 0.08

# --------- Puntos de base (map -> base_link) medidos por ti ---------

# 1) Pose previa donde el brazo se va a levantar para prepararse
#    (la que llamaste "Posicion brevia a todo")
PUNTO_PRE_PICK_LEJOS = [1.556, 0.647, -0.256, 0.967]
PUNTO_PRE_PICK_CERCA = [1.643060720827577, 0.589980337939326, -0.19464213198275995, 0.9808743244968775]

# Nueva posición FINAL donde realmente está la mesa con el papel
PUNTO_PICK_FINAL = [
    1.783533181500816,
    0.5726345814148441,
    -0.214270946751168,
    0.9767742632657549,
]

PUNTO_SALIDA = [1.816, 0.513, 0.37, 0.929]

# ---- Pose de brazo para coger el papel (tomada de tu /joint_states) ----
#   arm_1_joint:  0.8398282308364908
#   arm_2_joint: -0.2697552429314761
#   arm_3_joint: -1.7603665118592093
#   arm_4_joint:  1.0485439793221247
#   arm_5_joint: -2.0677267392366407
#   arm_6_joint:  0.2029659545141282
#   arm_7_joint: -0.004091382287336132
ARM_POSE_PICK = [
    0.8398282308364908,
    -0.2697552429314761,
    -1.7603665118592093,
    1.0485439793221247,
    -2.0677267392366407,
    0.2029659545141282,
    -0.004091382287336132,
]


# ---------------------------------------------------
#   Control sencillo del brazo y gripper
# ---------------------------------------------------

class ArmController(object):
    """
    Control directo del brazo y gripper usando:
      - /arm_controller/follow_joint_trajectory (brazo)
      - /gripper_controller/command (gripper)
      - /joint_states (lectura pose actual)
    """

    def __init__(self):
        # Cliente del brazo
        self._arm_client = actionlib.SimpleActionClient(
            "/arm_controller/follow_joint_trajectory",
            FollowJointTrajectoryAction,
        )
        rospy.loginfo("[PickPaper][Arm] Esperando servidor /arm_controller/follow_joint_trajectory...")
        if not self._arm_client.wait_for_server(rospy.Duration(10.0)):
            rospy.logerr("[PickPaper][Arm] No se encontró el servidor del brazo.")
            raise RuntimeError("Sin servidor de brazo")

        # Publicador del gripper
        self._gripper_pub = rospy.Publisher(
            "/gripper_controller/command",
            JointTrajectory,
            queue_size=1,
        )
        rospy.sleep(0.5)
        rospy.loginfo("[PickPaper][Arm] Control de brazo y gripper listo.")

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
            rospy.logerr(f"[PickPaper][Arm] No se encontró la articulación {e} en /joint_states.")
            raise

        return positions

    # ---- Movimiento del brazo ----

    def move_arm(self, target_positions, duration=3.0):
        """
        Envía una trayectoria simple al brazo (un solo punto en 'duration' segundos).
        """
        if len(target_positions) != len(ARM_JOINTS):
            rospy.logerr("[PickPaper][Arm] Número de joints no coincide con ARM_JOINTS.")
            return False

        jt = JointTrajectory()
        jt.joint_names = ARM_JOINTS

        point = JointTrajectoryPoint()
        point.positions = list(target_positions)
        point.velocities = [0.0] * len(ARM_JOINTS)
        point.time_from_start = rospy.Duration(duration)

        jt.points = [point]

        goal = FollowJointTrajectoryGoal()
        goal.trajectory = jt
        goal.goal_time_tolerance = rospy.Duration(1.0)

        rospy.loginfo(f"[PickPaper][Arm] Moviendo brazo a {target_positions} en {duration:.1f}s.")
        self._arm_client.send_goal(goal)
        finished = self._arm_client.wait_for_result(rospy.Duration(duration + 3.0))

        if not finished:
            rospy.logwarn("[PickPaper][Arm] Timeout esperando resultado del movimiento.")
            return False

        state = self._arm_client.get_state()
        ok = (state == 3)  # 3 == SUCCEEDED
        if ok:
            rospy.loginfo("[PickPaper][Arm] Movimiento completado.")
        else:
            rospy.logerr(f"[PickPaper][Arm] Movimiento fallido. Estado actionlib = {state}")
        return ok

    # ---- Gripper ----

    def send_gripper_position(self, position, duration=2.0):
        """
        Envía comando sencillo al gripper con los DOS dedos.
        Equivalente a:

          rostopic pub -1 /gripper_controller/command trajectory_msgs/JointTrajectory ...

        """
        traj = JointTrajectory()
        traj.joint_names = GRIPPER_JOINTS[:]  # ['gripper_right_finger_joint', 'gripper_left_finger_joint']

        point = JointTrajectoryPoint()
        point.positions = [position, position]
        point.velocities = [0.0, 0.0]
        point.time_from_start = rospy.Duration(duration)

        traj.points = [point]

        rospy.loginfo(f"[PickPaper][Arm] Enviando gripper a posición [{position:.3f}, {position:.3f}].")
        self._gripper_pub.publish(traj)
        rospy.sleep(duration + 0.5)

    def close_gripper(self):
        """Cierra el gripper para coger el cuaderno."""
        self.send_gripper_position(GRIPPER_CLOSED_POS, duration=2.0)

    def open_gripper(self):
        """Abre el gripper para soltar (por si lo necesitas en algún momento)."""
        self.send_gripper_position(GRIPPER_OPEN_POS, duration=2.0)

    # ---- Parada de emergencia ----

    def stop(self):
        """
        Cancela todas las goals del brazo.
        No lo teletransporta a ningún sitio, simplemente detiene el movimiento actual.
        """
        try:
            rospy.logwarn("[PickPaper][Arm] Cancelando todas las goals del brazo.")
            self._arm_client.cancel_all_goals()
        except Exception as e:
            rospy.logerr(f"[PickPaper][Arm] Error al cancelar goals del brazo: {e}")


# ---------------------------------------------------
#   Secuencia coger papel
# ---------------------------------------------------

class PickPaperSequence(object):
    def __init__(self):
        # Nodo ROS
        rospy.init_node("coger_papel", anonymous=True)

        # Follower para base
        rospy.loginfo("[PickPaper] Inicializando CheckpointFollower...")
        self._follower = CheckpointFollower()
        rospy.loginfo("[PickPaper] CheckpointFollower listo.")

        # Control brazo
        self._arm = ArmController()

        # Publisher para parada de emergencia de la base
        self._cmd_vel_pub = rospy.Publisher(
            "/mobile_base_controller/cmd_vel",
            Twist,
            queue_size=1,
        )
        rospy.sleep(0.5)

        rospy.loginfo("[PickPaper] Nodo listo. Comenzando secuencia...")

    # ---- Utilidades ----

    def _stop_base(self):
        """
        Envia cmd_vel = 0 varias veces para asegurarse de que la base se detiene.
        """
        rospy.logwarn("[PickPaper] Enviando cmd_vel = 0 para parar la base.")
        twist = Twist()
        for _ in range(10):
            self._cmd_vel_pub.publish(twist)
            rospy.sleep(0.05)

    def emergency_stop(self):
        """
        Parada de emergencia: detener base y brazo.
        """
        rospy.logwarn("[PickPaper] *** PARADA DE EMERGENCIA ***")
        try:
            self._stop_base()
        except Exception as e:
            rospy.logerr(f"[PickPaper] Error parando base: {e}")

        try:
            self._arm.stop()
        except Exception as e:
            rospy.logerr(f"[PickPaper] Error parando brazo: {e}")

        rospy.logwarn("[PickPaper] Secuencia detenida por emergencia.")

    # ---- Movimiento de base con Follower ----

    def _move_base_to(self, punto, nombre):
        """
        Mueve la base a un punto [x, y, oz, ow] usando CheckpointFollower.
        """
        try:
            rospy.loginfo(f"[PickPaper] Moviendo base a {nombre}: {punto}")
            ok = self._follower.enviar_puntos([punto])
            if not ok:
                rospy.logwarn(f"[PickPaper] Movimiento a {nombre} no confirmado (ok=False).")
            else:
                rospy.loginfo(f"[PickPaper] Llegado a {nombre}.")
            return ok
        except Exception as e:
            rospy.logerr(f"[PickPaper] ERROR moviendo base a {nombre}: {e}")
            return False

    # ---- Secuencia principal ----

    def run(self):
        """
        Ejecuta la secuencia "coger papel" completa.
        """
        try:

            if rospy.is_shutdown():
                return
            rospy.loginfo("[PickPaper] Abriendo gripper al inicio de la secuencia.")
            self._arm.open_gripper()
            rospy.sleep(1.0)

            # 1) Mover base a posición PRE-PICK LEJOS
            
            if rospy.is_shutdown():
                return
            self._move_base_to(PUNTO_PRE_PICK_LEJOS, "pre-pick-lejos")

            # 2) Llevar el brazo a la pose de coger papel
            if rospy.is_shutdown():
                return
            rospy.loginfo("[PickPaper] Moviendo brazo a pose de coger cuaderno.")
            if not self._arm.move_arm(ARM_POSE_PICK, duration=4.0):
                rospy.logwarn("[PickPaper] No se pudo alcanzar la pose de pick. Revisar valores.")
                # Si quieres abortar aquí, descomenta:
                # return

            # 3) Aproximar base a posición pre-pick cercana (offset seguro)
            rospy.loginfo("[PickPaper] Aproximando base a posición pre-pick cercana.")
            self._move_base_to(PUNTO_PRE_PICK_CERCA, "pre-pick-cerca")

            if rospy.is_shutdown():
                return

            # 4) Aproximar base al punto exacto de la mesa (donde está el papel)
            rospy.loginfo("[PickPaper] Aproximando base a posición FINAL sobre la mesa (pick-mesa).")
            self._move_base_to(PUNTO_PICK_FINAL, "pick-mesa")

            if rospy.is_shutdown():
                return

            # 5) Cerrar gripper en la posición de la mesa
            rospy.loginfo("[PickPaper] Cerrando gripper para agarrar el cuaderno.")
            self._arm.close_gripper()
            rospy.sleep(1.0)

            if rospy.is_shutdown():
                return

            # 6) Retroceder a una posición segura (misma que pre-pick-cerca)
            rospy.loginfo("[PickPaper] Retrocediendo a posición segura para no chocar con la mesa.")
            self._move_base_to(PUNTO_PRE_PICK_CERCA, "retroceso-seguro")

            if rospy.is_shutdown():
                return

            # 7) Mover base a posición cómoda final (PUNTO_SALIDA, con cierta rotación)
            rospy.loginfo("[PickPaper] Moviendo base a posición cómoda final (PUNTO_SALIDA).")
            self._move_base_to(PUNTO_SALIDA, "salida")


            rospy.loginfo("[PickPaper] Secuencia coger papel COMPLETADA con éxito.")

        except (KeyboardInterrupt, rospy.ROSInterruptException):
            # Ctrl+C o cierre del nodo → parada de emergencia
            self.emergency_stop()
        except Exception as e:
            rospy.logerr("[PickPaper] Excepción inesperada en la secuencia:")
            rospy.logerr(str(e))
            traceback.print_exc()
            self.emergency_stop()


# ---------------------------------------------------
#   main
# ---------------------------------------------------

if __name__ == "__main__":
    seq = PickPaperSequence()
    seq.run()
    rospy.loginfo("[PickPaper] Nodo finalizado.")
