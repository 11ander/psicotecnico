#!/usr/bin/env python

import rospy
import actionlib
from audicion_pkg.msg import AudicionAction, AudicionResult
from audicion_pkg.prueba_audicion import prueba_audicion

class AudicionActionServer:
    def __init__(self):
        rospy.init_node('audicion_action_server', anonymous=True)
        self.server = actionlib.SimpleActionServer(
            'audicion_action',
            AudicionAction,
            execute_cb=self.ejecutar_cb,
            auto_start=False
        )
        self.server.start()
        rospy.loginfo("Servidor de acción 'audicion_action' listo y esperando objetivos.")

    def ejecutar_cb(self, goal):
        rospy.loginfo(f"Recibido goal: ejecutar={goal.ejecutar}")
        
        try:
            # Ejecutar tu función de prueba principal
            rospy.loginfo("Iniciando prueba de audición...")

            # Construir resultado (4 enteros)
            resultado = AudicionResult()
            [num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2] = prueba_audicion()
            resultado.resultados = [num_llamadas_p1, num_llamadas_p2, aciertos_p2, fallos_p2]

            rospy.loginfo(f"Prueba completada -> {resultado.resultados}")
            self.server.set_succeeded(resultado)

        except Exception as e:
            rospy.logerr(f"Error durante la prueba: {e}")
            self.server.set_aborted()

if __name__ == '__main__':
    try:
        servidor = AudicionActionServer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass