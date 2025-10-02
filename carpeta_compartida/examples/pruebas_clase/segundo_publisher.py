#!/usr/bin/env python

import rospy
from std_msgs.msg import Int32
from random import randint
from sensor_msgs.msg import Image


class PublicadorImagenes():
    def __init__(self):
        rospy.init_node('primer_publicador', anonymous=True)
        self.pub = rospy.Publisher('topic_entero', Int32, queue_size=10)
        self.rate = rospy.Rate(50)  # 50 Hz
        rospy.wait_for_message('/camera/rgb/image_raw', Image, timeout=rospy.Duration(secs=10, nsecs=0))

    def publicar(self):
        msg = Int32()
        while not rospy.is_shutdown():
            msg.data = randint(1, 100)
            self.pub.publish(msg)
            self.rate.sleep()