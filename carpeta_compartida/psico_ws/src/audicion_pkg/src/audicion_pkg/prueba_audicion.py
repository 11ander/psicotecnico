#!/usr/bin/env python

import rospy
import random
from audicion_pkg.prueba2 import Prueba2
from audicion_pkg.speaker import TiagoSpeaker
# from std_msgs.msg import Int32MultiArray  # <- opcional si reactivas el publisher

def prueba_audicion():
    tiago = TiagoSpeaker()

    ###### PRUEBA 2 primero: botón al oír beep ######
    tiago.speak("Empezaremos con la primera prueba", duration=10.0)
    tiago.speak("Cuando escuches un pitido, pulsa el boton.", duration=10.0)
    tiago.speak("No pulses durante los silencios.", duration=10.0)
    tiago.speak("Comenzamos.", duration=10.0)

    prueba2 = Prueba2(tiago)
    num_llamadas_p2, aciertos_p2, fallos_p2 = prueba2.ejecucion()
    print(f"[P2] total={num_llamadas_p2}  aciertos={aciertos_p2}  fallos={fallos_p2}")

    ###### PRUEBA 1 después: contar cuántos beeps ######
    tiago.speak("Ahora haremos la segunda prueba.", duration=10.0)
    tiago.speak("Voy a emitir varios pitidos. Luego me diras cuantos has escuchado.", duration=10.0)
    tiago.speak("Comenzamos.", duration=10.0)

    num_llamadas_p1 = random.randint(2, 10)
    print(f"[P1] Numero de beeps a emitir: {num_llamadas_p1}")

    for _ in range(num_llamadas_p1):
        pausa = random.uniform(0.3, 5.0)
        tiago.speak("beep", duration=pausa)

    # Al final devolvemos el mismo orden de valores que espera tu Action/Web:
    # (P1_total, P2_total, P2_aciertos, P2_fallos)
    return num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2

if __name__ == "__main__":
    try:
        p1, p2, a2, f2 = prueba_audicion()
        print(f"RESULT -> P1={p1}, P2={p2}, AciertosP2={a2}, FallosP2={f2}")
    except rospy.ROSInterruptException:
        pass
