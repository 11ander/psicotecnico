#!/usr/bin/env python

import rospy
from std_msgs.msg import Int32
import random
from speaker import TiagoSpeaker

def prueba_audicion():
    # Inicializar Clase TiagoSpeaker para hablar con el TIAGo
    tiago = TiagoSpeaker()
    
    ###### Prueba 1 de audicion === x pitidos del TIAGo y contar veces que las hace ######
    # Numero aleatorio de llamadas a hablar al TIAGo
    num_llamadas = random.randint(2, 10)
    print(f"Numero de llamadas a hablar al TIAGo: {num_llamadas}")

    for _ in range(num_llamadas):
        tiempo_espera = random.uniform(0.3, 5.0) # Tiempo aleatorio entre beeps
        tiago.speak("beep", duration=tiempo_espera) # beep corto

    ###### Prueba 2 de audicion === Decir beeps y que el usuario indique cuando ######
    
    # Crear publisher para mandar resultados de las pruebas
    pub = rospy.Publisher('tiago/veces_hablado', Int32, queue_size=10)
    rospy.sleep(1) # Dar tiempo a que el publisher se conecte
    pub.publish(num_llamadas)
    print(f"Se publicaron {num_llamadas} intentos de beep")


if __name__ == "__main__":
    try:
        prueba_audicion()
    except rospy.ROSInterruptException:
        pass
