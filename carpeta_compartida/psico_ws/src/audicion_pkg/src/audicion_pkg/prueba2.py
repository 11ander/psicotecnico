#!/usr/bin/env python

import random, rospy
from std_msgs.msg import Bool
from audicion_pkg.speaker import TiagoSpeaker

SILENCIO, VENTANA = 0, 1

class Prueba2:
    def __init__(self, tiago=TiagoSpeaker):
        # Inicializar Clase TiagoSpeaker para hablar con el TIAGo
        self.tiago = tiago

        # Parámetros de la prueba
        self.num_beeps = random.randint(2, 8)
        # Tiempo máximo que tiene el usuario para pulsar al oír el beep
        self.max_t_resp = rospy.Duration.from_sec(1.0)

        # Estado para lectura del pulsador
        self.ultima_lectura_pulsador = False
        # Para no contar dos veces el mismo flanco dentro del modo
        self.pulso = False

        # Suscriptor al botón (hará que el LED se encienda mientras dure la prueba)
        self.sub_boton = rospy.Subscriber(
            'rpi/button6/pressed',
            Bool,
            self.callback_boton
        )

        # Preparar modo --- x segundos para pulsar al escuchar | y segundos para comprobar errores
        self.modo = SILENCIO
        self.tiempo_salida = rospy.Time.now() + rospy.Duration.from_sec(random.uniform(0.6, 5.0))
        self.beep_actual = 1

        # Resultados de la prueba
        self.aciertos = 0
        self.fallos = 0

    def callback_boton(self, msg):
        pulsador = bool(msg.data)
        # Flanco de subida del pulsador
        if pulsador and not self.ultima_lectura_pulsador:
            self.pulso = True
        self.ultima_lectura_pulsador = pulsador

    def ejecucion(self):
        # Ejecuta la prueba P2 (botón al oír beep)
        rate = rospy.Rate(50)  # Ejecuta este bucle a 50 Hz
        while not rospy.is_shutdown() and self.beep_actual <= self.num_beeps:
            now = rospy.Time.now()

            if self.modo == SILENCIO:
                # Pulsación durante silencio = fallo
                if self.pulso:
                    self.fallos += 1
                    self.pulso = False

                # Fin del modo de silencio -> decir beep y pasar a modo ventana
                if now >= self.tiempo_salida:
                    self.tiago.speak("beep")
                    self.modo = VENTANA
                    # Para cuándo se deberá salir del modo ventana
                    self.tiempo_salida = now + self.max_t_resp

            elif self.modo == VENTANA:
                # Pulsación durante ventana = acierto
                if self.pulso:
                    self.aciertos += 1
                    if self.tiempo_salida > now:
                        rospy.sleep(self.tiempo_salida - now)

                # Fin del modo ventana -> volver a silencio y preparar siguiente beep
                if now >= self.tiempo_salida or self.pulso:
                    self.pulso = False
                    self.beep_actual += 1
                    self.modo = SILENCIO
                    # Beep siguiente en un tiempo aleatorio
                    self.tiempo_salida = rospy.Time.now() + rospy.Duration.from_sec(
                        random.uniform(0.6, 5.0)
                    )

            rate.sleep()

        # Al terminar la prueba, nos desuscribimos del botón
        # -> el nodo del botón verá 0 conexiones y apagará el LED
        try:
            self.sub_boton.unregister()
        except Exception:
            pass

        return self.num_beeps, self.aciertos, self.fallos

if __name__ == '__main__':
    tiago = TiagoSpeaker()
    prueba = Prueba2(tiago)
    num_beeps, aciertos, fallos = prueba.ejecucion()
    print(f"Numero total de beeps: {num_beeps}\nNumero de aciertos: {aciertos}\nNumero de fallos: {fallos}")
