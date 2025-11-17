#!/usr/bin/env python3
import rospy
import actionlib
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

def main(pan=1.3, tilt=0.6, t=5.0):
    # Asegúrate de que el namespace y el action server sean correctos
    action = '/head_controller/follow_joint_trajectory'
    joint_names = ['head_1_joint', 'head_2_joint']  # ← ¡VERIFICA ESTE ORDEN!

    rospy.init_node('move_head_demo', anonymous=True)
    rospy.loginfo("Iniciando cliente de acción...")
    
    ac = actionlib.SimpleActionClient(action, FollowJointTrajectoryAction)
    
    if not ac.wait_for_server(rospy.Duration(5.0)):
        rospy.logerr(f"Servidor de acción no disponible: {action}")
        return False

    # Crear trayectoria
    jt = JointTrajectory()
    jt.joint_names = joint_names

    p = JointTrajectoryPoint()
    p.positions = [pan, tilt]
    p.velocities = [0.0, 0.0]  # ← ¡ES CLAVE EN TIAGO!
    p.time_from_start = rospy.Duration(t)
    jt.points = [p]

    goal = FollowJointTrajectoryGoal()
    goal.trajectory = jt
    goal.goal_time_tolerance = rospy.Duration(1.0)

    rospy.loginfo(f"Enviando meta: {dict(zip(joint_names, [pan, tilt]))}")
    ac.send_goal(goal)

    if not ac.wait_for_result(rospy.Duration(t + 3.0)):
        rospy.logwarn("Timeout: la acción no terminó a tiempo")
        return False

    state = ac.get_state()
    result = ac.get_result()

    rospy.loginfo(f"Estado final: {state} ({'SUCCEEDED' if state == 3 else 'NO SUCCEEDED'})")
    if result:
        rospy.loginfo(f"Resultado: {result}")

    if state == 3:
        rospy.loginfo("✅ Movimiento completado con éxito")
        return True
    else:
        rospy.logerr(f"❌ Meta rechazada o fallida. Estado: {state}")
        return False

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass