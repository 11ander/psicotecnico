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
#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import JointState

# Articulaciones del brazo
ARM_JOINTS = [
    'arm_1_joint', 'arm_2_joint', 'arm_3_joint',
    'arm_4_joint', 'arm_5_joint', 'arm_6_joint', 'arm_7_joint'
]

# Articulación del gripper
GRIPPER_JOINT = 'gripper_left_finger_joint'

def callback(msg):
    positions = {}
    for name, pos in zip(msg.name, msg.position):
        if name in ARM_JOINTS or name == GRIPPER_JOINT:
            positions[name] = pos

    # Verificar que tenemos al menos el gripper y las articulaciones del brazo
    brazo_ok = all(j in positions for j in ARM_JOINTS)
    gripper_ok = GRIPPER_JOINT in positions

    if brazo_ok:
        print("\n🟢 Posición actual del BRAZO (radianes):")
        for j in ARM_JOINTS:
            print(f"  {j}: {positions[j]:.3f}")
    else:
        print("\n⚠️  No se recibieron todas las articulaciones del brazo.")

    if gripper_ok:
        gripper_pos = positions[GRIPPER_JOINT]
        estado = "	cerrado" if gripper_pos < 0.05 else "	abierto"
        print(f"\n🟢 Posición del GRIPPER: {gripper_pos:.3f} rad → {estado}")
    else:
        print(f"\n⚠️  No se encontró la articulación '{GRIPPER_JOINT}'.")

    # Finalizar el nodo después de imprimir (como en tu versión original)
    rospy.signal_shutdown("Posición obtenida")

def main():
    rospy.init_node('ver_posicion_brazo_gripper', anonymous=True)
    rospy.Subscriber('/joint_states', JointState, callback)
    rospy.spin()

if __name__ == '__main__':
    main()
if __name__ == '__main__':
    main()

    