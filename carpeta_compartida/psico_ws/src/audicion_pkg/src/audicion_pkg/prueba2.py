#!/usr/bin/env python

import random, rospy
from std_msgs.msg import Bool
from speaker import TiagoSpeaker

SILENCIO, VENTANA = 0, 1

class Prueba2:
    def __init__(self, tiago=TiagoSpeaker):
         # Inicializar Clase TiagoSpeaker para hablar con el TIAGo
        self.tiago = tiago

        # Parametros de la prueba
        self.num_beeps = random.randint(2, 8)
        self.max_t_resp = rospy.Duration.from_sec(1.0) # Tiempo maximo que tiene el usuario para pulsar al oir el beep

        # Estado para lectura del pulsador
        self.ultima_lectura_pulsador = False
        self.pulso = False # Para no contar dos veces el mismo flanco dentro del modo
        rospy.Subscriber('rpi/button6/pressed', Bool, self.callback_boton)

        # Preparar modo --- x segundos para pulsar al escuchas | y segundos para comprobar errores de pulsacion sin hablar
        self.modo = SILENCIO
        self.tiempo_salida = rospy.Time.now() + rospy.Duration.from_sec(random.uniform(0.6, 5.0))
        self.beep_actual = 1

        # Resultados de la prueba
        self.aciertos = 0
        self.fallos = 0

    def callback_boton(self, msg):
        pulsador = bool(msg.data)
        if pulsador and not self.ultima_lectura_pulsador: # Flanco de subida del pulsador
            self.pulso = True
        self.ultima_lectura_pulsador = pulsador

    def ejecucion(self):
        rate = rospy.Rate(50) # Para controlar la velocidad de ejecución del bucle, es decir, para decirle a ROS: Ejecuta este bucle a 50 veces por segundo
        while not rospy.is_shutdown() and self.beep_actual <= self.num_beeps:
            now = rospy.Time.now()

            if self.modo == SILENCIO:
                # Pulsacion durante silencio = fallo
                if self.pulso:
                    self.fallos += 1
                    self.pulso = False

                # Fin del modo de silencio. Decir beep y pasar al modo de ventana
                if now >= self.tiempo_salida:
                    self.tiago.speak("beep")
                    self.modo = VENTANA
                    self.tiempo_salida = now + self.max_t_resp # Para cuando se debera salir del modo ventana

            elif self.modo == VENTANA:  # VENTANA
                # Pulsacion durante ventana = acierto
                if self.pulso:
                    self.aciertos += 1
                    if self.tiempo_salida > now:
                        rospy.sleep(self.tiempo_salida-now)

                # Fin del modo de ventana. Pasar al modo de silencio
                if now >= self.tiempo_salida or self.pulso:
                    self.pulso = False
                    self.beep_actual += 1
                    self.modo = SILENCIO
                    self.tiempo_salida = rospy.Time.now() + rospy.Duration.from_sec(random.uniform(0.6, 5.0)) # Para cuando se debera salir del modo silencio (el beep suena cada x tiempo aleatoriamente)
            
            rate.sleep()

        return self.num_beeps, self.aciertos, self.fallos
    
if __name__ == '__main__':
    tiago = TiagoSpeaker()
    prueba = Prueba2(tiago)
    [num_beeps, aciertos, fallos] = prueba.ejecucion()
    print(f"Numero total de beeps: {num_beeps}\nNumero de aciertos: {aciertos}\nNumero de fallos: {fallos}")