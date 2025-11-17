#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib
from coordinacion_pkg.msg import MobilityExamAction, MobilityExamGoal, MobilityExamFeedback

def feedback_cb(fb: MobilityExamFeedback):
    rospy.loginfo_throttle(1.0, f"[FB] {fb.estado} | tiempo válido={fb.valid_elapsed:.1f}s")

def done_cb(state, result):
    rospy.loginfo("==== RESULTADO ====")
    rospy.loginfo("state=%s", str(state))
    rospy.loginfo("score=%.1f/100", result.score)
    rospy.loginfo("csv_path=%s", result.csv_path)
    rospy.loginfo("report_path=%s", result.report_path)
    for line in result.informe:
        rospy.loginfo(" - %s", line)

if __name__ == "__main__":
    rospy.init_node("mobility_exam_action_client", anonymous=True)
    client = actionlib.SimpleActionClient("mobility_exam_action", MobilityExamAction)
    rospy.loginfo("Esperando al servidor 'mobility_exam_action'...")
    client.wait_for_server()
    rospy.loginfo("Servidor disponible.")

    goal = MobilityExamGoal(ejecutar=True)
    rospy.loginfo("Enviando goal…")
    client.send_goal(goal, done_cb=done_cb, feedback_cb=feedback_cb)
    rospy.loginfo("Esperando resultado…")
    client.wait_for_result()
    rospy.loginfo("Cliente finalizado.")
