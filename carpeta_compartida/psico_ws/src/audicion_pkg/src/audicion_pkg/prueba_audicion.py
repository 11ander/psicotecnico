import rospy
from std_msgs.msg import Int32
import random
from speaker import TiagoSpeaker

def prueba_audicion():
    # Número aleatorio de llamadas a hablar al TIAGo
    num_llamadas = random.randint(2, 10)
    print(f"Número de llamadas a hablar al TIAGo: {num_llamadas}")

    tiago = TiagoSpeaker()

    # Crear publisher después de inicializar TiagoSpeaker
    pub = rospy.Publisher('tiago/veces_hablado', Int32, queue_size=10)
    rospy.sleep(1)  # Dar tiempo a que el publisher se conecte

    for _ in range(num_llamadas):
        tiempo_espera = random.uniform(0.3, 5.0)  # Tiempo aleatorio entre beeps
        tiago.speak("beep", duration=tiempo_espera)  # beep corto

    pub.publish(num_llamadas)
    print(f"Se publicaron {num_llamadas} intentos de beep.")

if __name__ == "__main__":
    try:
        prueba_audicion()
    except rospy.ROSInterruptException:
        pass
