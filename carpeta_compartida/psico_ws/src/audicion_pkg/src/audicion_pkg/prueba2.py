#!/usr/bin/env python

import random
import rospy
from std_msgs.msg import Int32, Bool, String
from collections import deque
from speaker import TiagoSpeaker
import json

class PruebaAudicionUsuario(object):
    def __init__(self):
        # Inicializar Clase TiagoSpeaker para hablar con el TIAGo
        self.tiago = TiagoSpeaker()

        # Parametros de la prueba
        self.num_beeps = random.randint(3, 8)
        self.max_t_resp = 1.0 # Tiempo maximo que tiene el usuario para pulsar al oir el beep

        # Estado para lectura del pulsador
        self.press_queue = deque()
        self.ultimo_btn  = False
        rospy.Subscriber('/usuario/pulsador', Bool, self.cb_pulsador)

        rospy.loginfo("PRUEBA 2 lista: num_beeps=%d",self.num_beeps)

    def cb_pulsador(self, msg):
        val = bool(msg.data)
        if val and not self.ultimo_btn:  # flanco de subida
            self.press_queue.append(rospy.Time.now())
        self.ultimo_btn = val

    def esperar_pulsacion(self, t_inicio, ventana):
        """Espera hasta 'ventana' s por una pulsación >= t_inicio. Devuelve (ok, dt)."""
        rate = rospy.Rate(200)
        deadline = t_inicio + rospy.Duration.from_sec(ventana)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            # descarta pulsaciones previas al beep
            while self.press_queue and (self.press_queue[0] - t_inicio).to_sec() < 0:
                self.press_queue.popleft()
            if self.press_queue:
                t_press = self.press_queue.popleft()
                dt = (t_press - t_inicio).to_sec()
                if 0 <= dt <= ventana:
                    return True, dt
            rate.sleep()
        return False, None

    def run(self):
        aciertos, omisiones = 0, 0

        for i in range(1, self.num_beeps + 1):
            # 1) emitir beep
            t_beep = rospy.Time.now()
            try:
                self.tiago.speak("beep", timeout=5.0)   # si tu speak usa timeout
            except TypeError:
                self.tiago.speak("beep", duration=0.6)  # fallback si usa duration

            # 2) esperar respuesta del usuario
            ok, dt = self.esperar_pulsacion(t_beep, self.max_t_resp)
            if ok:
                aciertos += 1
                rospy.loginfo("Beep %d: Acierto (dt=%.3fs)", i, dt)
            else:
                omisiones += 1
                rospy.loginfo("Beep %d: Omisión", i)

            # 3) pausa entre beeps
            rospy.sleep(random.uniform(0.6, 5.0))

        # Devuelve (n_beeps, aciertos, fallos)
        return self.num_beeps, aciertos, omisiones

def main():
    # NO llames a rospy.init_node aquí (lo hace TiagoSpeaker al construirse)
    nodo = PruebaAudicionUsuario()
    n_beeps, aciertos, fallos = nodo.run()
    # imprimir también para verlo al ejecutar
    print("RESULTADO -> beeps: %d, aciertos: %d, fallos: %d" % (n_beeps, aciertos, fallos))
    return n_beeps, aciertos, fallos

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass