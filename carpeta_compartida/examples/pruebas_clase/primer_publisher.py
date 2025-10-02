#!/usr/bin/env python

import rospy
from std_msgs.msg import Int32
from random import randint

rospy.init_node('primer_publicador', anonymous=True)
pub = rospy.Publisher('topic_entero', Int32, queue_size=10)
rate = rospy.Rate(50)  # 50 Hz

if __name__ == '__main__':
    msg = Int32()
    while not rospy.is_shutdown():
        msg.data = randint(1, 100)
        pub.publish(msg)
        rate.sleep()