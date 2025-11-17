import rospy
import actionlib
from rpi_pkg.msg import MemoriaAction, MemoriaResult, MemoriaFeedback, MemoriaGoal

try:
    from rpi_pkg.memoria import test_memoria
except Exception as e:
    rospy.logerr("No se pudo importar test_memoria: %s", e)
    test_memoria = None

class ServidorMemoria(object):
    def __init__(self):
        self._server = actionlib.SimpleActionServer(
            'memoria',
            MemoriaAction,              
            execute_cb=self.execute_cb,
            auto_start=False
        )
        self._server.start()
        rospy.loginfo("Action server 'memoria' listo.")

    def execute_cb(self, goal: MemoriaGoal):
        if self._server.is_preempt_requested():
            rospy.logwarn("Preempt solicitado antes de iniciar.")
            self._server.set_preempted()
            return

        if test_memoria is None:
            rospy.logerr("test_memoria no disponible.")
            self._server.set_aborted(MemoriaResult(result=-1.0))  
            return

        if not getattr(goal, 'input', False):
            rospy.loginfo("input=False: no ejecuto prueba.")
            self._server.set_succeeded(MemoriaResult(result=0.0))
            return

        try:
            rospy.loginfo("Iniciando prueba de memoria...")
            self._server.publish_feedback(MemoriaFeedback())  

            puntuacion = float(test_memoria()) 
            rospy.loginfo("Prueba finalizada. Puntuación=%.2f", puntuacion)

            self._server.set_succeeded(MemoriaResult(result=puntuacion))

        except KeyboardInterrupt:
            rospy.logwarn("Interrumpido por teclado.")
            self._server.set_preempted()
        except Exception as e:
            rospy.logerr("Error ejecutando la prueba: %s", e)
            self._server.set_aborted(MemoriaResult(result=-1.0))

if __name__ == '__main__':
    rospy.init_node('servidor_memoria')
    ServidorMemoria()
    rospy.spin()