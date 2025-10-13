#!/usr/bin/env python

import rospy
from std_msgs.msg import Int32MultiArray
import random
from audicion_pkg.speaker import TiagoSpeaker
from prueba2 import Prueba2

def prueba_audicion():
    # Inicializar Clase TiagoSpeaker para hablar con el TIAGo
    tiago = TiagoSpeaker()
    
    ###### Prueba 1 de audicion === x pitidos del TIAGo y contar veces que las hace ######
    tiago.speak("Vamos a empezar la prueba uno.", duration=10.0)
    tiago.speak("Voy a emitir varios pitidos. Luego me diras cuantos has escuchado.", duration=10.0)
    tiago.speak("Comenzamos.", duration=10.0)
    
    # Numero aleatorio de llamadas a hablar al TIAGo
    num_llamadas_p1 = random.randint(2, 10)
    print(f"Numero de llamadas a hablar al TIAGo: {num_llamadas_p1}")

    for _ in range(num_llamadas_p1):
        tiempo_espera = random.uniform(0.3, 5.0) # Tiempo aleatorio entre beeps
        tiago.speak("beep", duration=tiempo_espera) # beep corto

    ###### Prueba 2 de audicion === Decir beeps y que el usuario indique cuando ######
    tiago.speak("Ahora empezaremos la prueba dos.", duration=10.0)
    tiago.speak("Cuando escuches un pitido, pulsa el boton.", duration=10.0)
    tiago.speak("No pulses durante los silencios.", duration=10.0)
    tiago.speak("Comenzamos.", duration=10.0)
    
    prueba2 = Prueba2(tiago)
    [num_llamadas_p2, aciertos_p2, fallos_p2] = prueba2.ejecucion()
    print(f"Numero total de beeps: {num_llamadas_p2}\nNumero de aciertos_p2: {aciertos_p2}\nNumero de fallos_p2: {fallos_p2}")
    
    return num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2
    
    ###### Crear publisher para mandar resultados de las pruebas ######
    # pub = rospy.Publisher('tiago/audicion/resultados', Int32MultiArray, queue_size=10)
    # rospy.sleep(1) # Dar tiempo a que el publisher se conecte
    # msg = Int32MultiArray() # Crear el mensaje a publicar
    # msg.data = [num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2]
    # pub.publish(msg)


if __name__ == "__main__":
    try:
        [num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2] = prueba_audicion()
    except rospy.ROSInterruptException:
        pass
