#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import actionlib
from face_recognition_pkg.msg import FaceRecognitionAction, FaceRecognitionGoal

def done_cb(state, result):
    rospy.loginfo(f"Resultado recibido: nombre='{result.nombre}' (state={state})")

def active_cb():
    rospy.loginfo("La acción ha comenzado.")

if __name__ == '__main__':
    rospy.init_node('face_recognition_action_client', anonymous=True)

    client = actionlib.SimpleActionClient('face_recognition_action', FaceRecognitionAction)
    rospy.loginfo("Esperando al servidor de acción 'face_recognition_action'...")
    client.wait_for_server()
    rospy.loginfo("Servidor de acción disponible.")

    goal = FaceRecognitionGoal()
    goal.ejecutar = True

    rospy.loginfo("Enviando goal...")
    client.send_goal(goal, done_cb=done_cb, active_cb=active_cb)
    rospy.loginfo("Esperando resultado...")
    client.wait_for_result()
    rospy.loginfo("Cliente finalizado.")
