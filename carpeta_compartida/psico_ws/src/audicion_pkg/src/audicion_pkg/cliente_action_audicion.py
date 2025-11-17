#!/usr/bin/env python

import rospy
import actionlib
from audicion_pkg.msg import AudicionAction, AudicionGoal

def done_cb(state, result):
    rospy.loginfo(f"Resultado recibido: {result.resultados}")

def active_cb():
    rospy.loginfo("La acción ha comenzado.")

if __name__ == '__main__':
    rospy.init_node('audicion_action_client', anonymous=True)

    client = actionlib.SimpleActionClient('audicion_action', AudicionAction)
    rospy.loginfo("Esperando al servidor de acción 'audicion_action'...")
    client.wait_for_server()
    rospy.loginfo("Servidor de acción disponible.")

    goal = AudicionGoal()
    goal.ejecutar = True

    rospy.loginfo("Enviando goal al servidor de acción...")
    client.send_goal(goal, done_cb=done_cb, active_cb=active_cb)
    rospy.loginfo("Esperando resultado...")
    client.wait_for_result()
    rospy.loginfo("Cliente finalizado.")
    result = client.get_result()
    rospy.loginfo(f"Resultado final: {result.resultados}")