#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import rospy
import actionlib
from geometry_msgs.msg import Quaternion, PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from tf.transformations import quaternion_from_euler

SUCCEEDED = 3  # actionlib goal state

def build_goal(x, y, yaw_rad):
    """Crea un MoveBaseGoal en frame 'map' para (x,y, yaw)."""
    qx, qy, qz, qw = quaternion_from_euler(0.0, 0.0, yaw_rad)

    goal = MoveBaseGoal()
    goal.target_pose.header.frame_id = "map"
    goal.target_pose.header.stamp = rospy.Time.now()
    goal.target_pose.pose.position.x = x
    goal.target_pose.pose.position.y = y
    goal.target_pose.pose.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
    return goal

def yaw_towards(p_from, p_to):
    """Ángulo yaw que mira desde p_from -> p_to."""
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    return math.atan2(dy, dx)

def follow_checkpoints(checkpoints):
    """Envía goals secuenciales a move_base siguiendo la lista de puntos [ [x,y], ... ]."""
    client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
    rospy.loginfo("Esperando a move_base...")
    client.wait_for_server()
    rospy.loginfo("Conectado a move_base.")

    for i in range(len(checkpoints) - 1):
        p_cur = checkpoints[i]
        p_nxt = checkpoints[i + 1]
        yaw = yaw_towards(p_cur, p_nxt)

        goal = build_goal(p_nxt[0], p_nxt[1], yaw)
        rospy.loginfo("Enviando goal %d/%d -> (%.3f, %.3f, yaw=%.2f°)",
                      i+1, len(checkpoints)-1, p_nxt[0], p_nxt[1], math.degrees(yaw))
        client.send_goal(goal)
        client.wait_for_result()

        state = client.get_state()
        if state != SUCCEEDED:
            rospy.logwarn("No se alcanzó el checkpoint %d (state=%d). Abortando.", i+1, state)
            return False

    rospy.loginfo("Ruta completada.")
    return True

if __name__ == '__main__':
    rospy.init_node('checkpoint_follower', anonymous=True)

    # Ejemplo de lista (usa tus puntos en 'map')
    checkpoints = [
        [0, 0]
    ]

    # Si quieres volver por el mismo camino:
    checkpoints = checkpoints + list(reversed(checkpoints[:-1]))

    ok = follow_checkpoints(checkpoints)
    rospy.loginfo("Resultado final: %s", "ÉXITO" if ok else "FALLO")