#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import JointState

def callback(msg):
    arm_joints = ['arm_1_joint', 'arm_2_joint', 'arm_3_joint',
                  'arm_4_joint', 'arm_5_joint', 'arm_6_joint', 'arm_7_joint']
    positions = {}
    for name, pos in zip(msg.name, msg.position):
        if name in arm_joints:
            positions[name] = pos
    # Mostrar en orden
    if len(positions) == 7:
        print("Posición actual del brazo (radianes):")
        for j in arm_joints:
            print(f"  {j}: {positions[j]:.3f}")
        rospy.signal_shutdown("Posición obtenida")

def main():
    rospy.init_node('get_arm_position', anonymous=True)
    rospy.Subscriber('/joint_states', JointState, callback)
    rospy.spin()

if __name__ == '__main__':
    main()

    