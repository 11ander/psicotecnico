#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import JointState
import actionlib
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

# Definir las articulaciones del brazo (orden fijo)
ARM_JOINTS = [
    'arm_1_joint', 'arm_2_joint', 'arm_3_joint',
    'arm_4_joint', 'arm_5_joint', 'arm_6_joint', 'arm_7_joint'
]

def cogerPOSIsactual():
    """
    Obtiene la posición actual del brazo desde /joint_states.
    Devuelve una lista de 7 valores (radianes) o None si falla.
    """
    joint_state_msg = rospy.wait_for_message('/joint_states', JointState, timeout=5.0)
    
    # Crear un diccionario {nombre: posición}
    current = {}
    for name, pos in zip(joint_state_msg.name, joint_state_msg.position):
        if name in ARM_JOINTS:
            current[name] = pos

    # Asegurar el orden correcto
    try:
        positions = [current[joint] for joint in ARM_JOINTS]
        return positions
    except KeyError as e:
        rospy.logerr(f"Articulación no encontrada en /joint_states: {e}")
        return None

def move_arm(target_positions, duration=3.0):
    """
    Mueve el brazo a las posiciones dadas.
    """
    action_name = '/arm_controller/follow_joint_trajectory'
    client = actionlib.SimpleActionClient(action_name, FollowJointTrajectoryAction)
    
    rospy.loginfo("Esperando al controlador del brazo...")
    if not client.wait_for_server(rospy.Duration(5.0)):
        rospy.logerr("❌ Controlador del brazo no disponible.")
        return False

    # Crear trayectoria
    jt = JointTrajectory()
    jt.joint_names = ARM_JOINTS

    p = JointTrajectoryPoint()
    p.positions = target_positions
    p.velocities = [0.0] * 7  # obligatorio en TIAGo
    p.time_from_start = rospy.Duration(duration)
    jt.points = [p]

    goal = FollowJointTrajectoryGoal()
    goal.trajectory = jt
    goal.goal_time_tolerance = rospy.Duration(1.0)

    rospy.loginfo("Enviando meta al brazo...")
    client.send_goal(goal)

    if not client.wait_for_result(rospy.Duration(duration + 3.0)):
        rospy.logwarn("⚠️ Timeout en movimiento.")
        return False

    success = client.get_state() == 3
    if success:
        rospy.loginfo("✅ Movimiento completado.")
    else:
        rospy.logerr("❌ Movimiento fallido.")
    return success

def main():
    rospy.init_node('move_arm_with_feedback', anonymous=True)

    # 1. Leer posición inicial
    rospy.loginfo("Leyendo posición inicial del brazo...")
    initial_pos = cogerPOSIsactual()
    if initial_pos is None:
        rospy.logerr("No se pudo leer la posición inicial.")
        return

    rospy.loginfo(f"Posición inicial: {[round(p, 3) for p in initial_pos]}")

    # 2. DEFINIR POSICION A MOVER
    target_pos = [1.5, 1.0, 1.0, 2.0, 2.0, 0.5, 0.0]  # ejemplo RADIANES
    #Limites === [1.5, 1.0, 1.0, 2.0, 2.0, 1.3, 0.0]
    #home tiago= [0.070, -1.235, -0.134, 2.107, -1.768, -0.854, -0.996] 
  
    rospy.loginfo(f"Posición objetivo: {[round(p, 3) for p in target_pos]}")

    # 3. Mover el brazo
    if not move_arm(target_pos, duration=3.0):
        return

    # 4. (Opcional) Leer posición final para verificar
    rospy.loginfo("Leyendo posición final del brazo...")
    final_pos = cogerPOSIsactual()
    if final_pos is not None:
        rospy.loginfo(f"Posición final: {[round(p, 3) for p in final_pos]}")
        # Puedes calcular el error si quieres
        error = [abs(f - t) for f, t in zip(final_pos, target_pos)]
        rospy.loginfo(f"Error absoluto: {[round(e, 4) for e in error]}")

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr(f"Error: {e}")