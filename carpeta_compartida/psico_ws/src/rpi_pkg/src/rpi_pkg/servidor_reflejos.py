#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib

# Importa tu acción (ajusta el paquete si no es rpi_pkg)
from rpi_pkg.msg import BoolToFloatAction, BoolToFloatResult

# Importa tu lógica de la prueba
# Asegúrate de que reflejos.py está en rpi_pkg/src/rpi_pkg/ o instalado como módulo
try:
    from rpi_pkg.reflejos import test_reflejos
except Exception as e:
    rospy.logerr("No se pudo importar test_reflejos desde rpi_pkg.reflejos: %s", e)
    test_reflejos = None

class ServidorReflejos(object):
    def __init__(self):
        # Nombre del servidor/action topic: 'reflejos'
        self._server = actionlib.SimpleActionServer(
            'reflejos',                    # topic del action server
            BoolToFloatAction,             # tipo de acción (.action)
            execute_cb=self.execute_cb,    # callback de ejecución
            auto_start=False
        )
        self._server.start()
        rospy.loginfo("Action server 'reflejos' listo.")

    def execute_cb(self, goal):
        """
        goal.input: bool -> si True, arranca la prueba de reflejos.
        Devuelve: result.result (float) = puntuación de test_reflejos().
        """
        # Si nos piden preempt justo al entrar
        if self._server.is_preempt_requested():
            rospy.logwarn("Preempt solicitado antes de iniciar la prueba.")
            self._server.set_preempted()
            return

        # Validaciones básicas
        if test_reflejos is None:
            rospy.logerr("test_reflejos no disponible. Abortando.")
            self._server.set_aborted(BoolToFloatResult(result=-1.0))
            return

        if not goal.input:
            rospy.loginfo("Goal con input=False recibido. Devolviendo 0.0 sin ejecutar prueba.")
            self._server.set_succeeded(BoolToFloatResult(result=0.0))
            return

        try:
            rospy.loginfo("Iniciando prueba de reflejos...")
            # OJO: test_reflejos() es bloqueante; mientras corre no podremos preempt.
            puntuacion = float(test_reflejos())
            rospy.loginfo("Prueba finalizada. Puntuación=%.2f", puntuacion)

            # Éxito
            self._server.set_succeeded(BoolToFloatResult(result=puntuacion))

        except KeyboardInterrupt:
            rospy.logwarn("Prueba interrumpida (KeyboardInterrupt).")
            self._server.set_preempted()
        except Exception as e:
            rospy.logerr("Error ejecutando la prueba: %s", e)
            self._server.set_aborted(BoolToFloatResult(result=-1.0))

if __name__ == '__main__':
    rospy.init_node('servidor_reflejos')
    ServidorReflejos()
    rospy.spin()
