#!/usr/bin/env python3
import rospy
from std_msgs.msg import Bool
from gpiozero import Button

def main():
    rospy.init_node("estado_pulsador")
    pin = rospy.get_param("~gpio", 6)               
    pull_up = rospy.get_param("~pull_up", True)     
    debounce = rospy.get_param("~debounce_s", 0.02)  
    rate_hz = rospy.get_param("~rate", 20.0)         
    topic = rospy.get_param("~topic", "rpi/button6/pressed")

    btn = Button(pin, pull_up=pull_up, bounce_time=debounce)
    pub = rospy.Publisher(topic, Bool, queue_size=10)
    rate = rospy.Rate(rate_hz)

    rospy.loginfo("estado_pulsador publicando en /%s (GPIO=%d, pull_up=%s, debounce=%.3fs, rate=%.1fHz)",
                  topic, pin, pull_up, debounce, rate_hz)

    while not rospy.is_shutdown():
        pub.publish(btn.is_pressed) 
        rate.sleep()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        rospy.logerr("estado_pulsador error: %s", e)
