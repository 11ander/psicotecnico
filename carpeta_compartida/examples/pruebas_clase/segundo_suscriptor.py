#!/usr/bin/env python

import rospy
from sensor_msgs.msg import Image
from copy import deepcopy


class ConsumidorImagenes():
    def __init__(self):
        rospy.init_node('primer_consumidor', anonymous=True)
        rospy.wait_for_message('/camera/rgb/image_raw', Image, timeout=rospy.Duration(5))
        self.sub = rospy.Subscriber('/camera/rgb/image_raw', Image, self.cb_imagen_rgb_tiago)
        self.imagen_tiago_rgb = None

    def cb_imagen_rgb_tiago(self, msg: Image) -> None: # Callback para la imagen RGB
        self.imagen_tiago_rgb = msg

    def rutina(self):
        while not rospy.is_shutdown():
            imagen = deepcopy(self.imagen_tiago_rgb) #Para evitar problemas de concurrencia y que no se cambie por el callback
            ...
            ...
            ...
            ...
            imagen
        
if __name__ == '__main__':
    consumidor = ConsumidorImagenes()
    consumidor.rutina()