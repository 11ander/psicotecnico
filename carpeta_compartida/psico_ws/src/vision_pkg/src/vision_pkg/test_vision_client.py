#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib
from vision_pkg.msg import VisionAction, VisionGoal, VisionFeedback


def feedback_cb(feedback: VisionFeedback):
    rospy.loginfo(f"[CLIENTE] Feedback recibido: fase = {feedback.fase}")


def main():
    rospy.init_node("vision_test_client")

    rospy.loginfo("[CLIENTE] Creando SimpleActionClient a 'vision_action'...")
    client = actionlib.SimpleActionClient("vision_action", VisionAction)

    rospy.loginfo("[CLIENTE] Esperando a que el servidor esté disponible...")
    client.wait_for_server()
    rospy.loginfo("[CLIENTE] Servidor encontrado.")

    goal = VisionGoal()
    goal.ejecutar = True

    rospy.loginfo("[CLIENTE] Enviando goal ejecutar=True...")
    client.send_goal(goal, feedback_cb=feedback_cb)

    rospy.loginfo("[CLIENTE] Esperando resultado...")
    client.wait_for_result()

    result = client.get_result()
    if result is not None:
        rospy.loginfo(f"[CLIENTE] Resultado recibido: ok = {result.ok}")
    else:
        rospy.logwarn("[CLIENTE] No se recibió resultado.")

    rospy.loginfo("[CLIENTE] Fin del test.")


if __name__ == "__main__":
    main()
