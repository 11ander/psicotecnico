#!/usr/bin/env python

import sys, select, termios, tty, time
import rospy
from std_msgs.msg import Bool

def main():
    rospy.init_node('pulsador_teclado', anonymous=True)
    pub = rospy.Publisher('/usuario/pulsador', Bool, queue_size=10)
    old_settings = termios.tcgetattr(sys.stdin)
    print("\n[Pulsador teclado] Pulsa ESPACIO o ENTER cuando oigas un beep. Ctrl+C para salir.\n")

    try:
        tty.setcbreak(sys.stdin.fileno())
        while not rospy.is_shutdown():
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist:
                ch = sys.stdin.read(1)
                if ch in (' ', '\n', '\r'):
                    pub.publish(Bool(data=True))
                    time.sleep(0.03)
                    pub.publish(Bool(data=False))
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
