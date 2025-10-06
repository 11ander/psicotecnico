#!/usr/bin/env python

import rospy
from pal_interaction_msgs.msg import TtsAction, TtsGoal
import actionlib
from random import choice

class TiagoSpeaker():
    def __init__(self):
        rospy.init_node('tiago_speaker', anonymous=True)
        # Cliente de Action para TTS
        self.tts_client = actionlib.SimpleActionClient('/tts', TtsAction)
        rospy.loginfo("Esperando TTS server...")
        self.tts_client.wait_for_server()
        rospy.loginfo("Conectado al TTS server")

    def speak(self, text, duration=3.0):
        """Envía un texto al TTS y espera la duración indicada"""
        goal = TtsGoal()
        goal.rawtext.text = text
        goal.rawtext.lang_id = "en_ES"
        self.tts_client.send_goal_and_wait(goal, rospy.Duration(duration), rospy.Duration(duration))
            
if __name__ == '__main__':
    speaker = TiagoSpeaker()
    speaker.speak("Hello, I am TIAGo, your personal robot assistant.")