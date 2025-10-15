import rospy
import actionlib
from rpi_pkg.msg import ReflejosAction, ReflejosResult, ReflejosFeedback, ReflejosGoal

try:
    from rpi_pkg.reflejos import test_reflejos
except Exception as e:
    rospy.logerr("No se pudo importar test_reflejos: %s", e)
    test_reflejos = None

class ServidorReflejos(object):
    def __init__(self):
        self._server = actionlib.SimpleActionServer(
            'reflejos',
            ReflejosAction,              
            execute_cb=self.execute_cb,
            auto_start=False
        )
        self._server.start()
        rospy.loginfo("Action server 'reflejos' listo.")

    def execute_cb(self, goal: ReflejosGoal):
        if self._server.is_preempt_requested():
            rospy.logwarn("Preempt solicitado antes de iniciar.")
            self._server.set_preempted()
            return

        if test_reflejos is None:
            rospy.logerr("test_reflejos no disponible.")
            self._server.set_aborted(ReflejosResult(result=-1.0))  
            return

        if not getattr(goal, 'input', False):
            rospy.loginfo("input=False: no ejecuto prueba.")
            self._server.set_succeeded(ReflejosResult(result=0.0))
            return

        try:
            rospy.loginfo("Iniciando prueba de reflejos...")
            self._server.publish_feedback(ReflejosFeedback())  

            puntuacion = float(test_reflejos()) 
            rospy.loginfo("Prueba finalizada. Puntuación=%.2f", puntuacion)

            self._server.set_succeeded(ReflejosResult(result=puntuacion))

        except KeyboardInterrupt:
            rospy.logwarn("Interrumpido por teclado.")
            self._server.set_preempted()
        except Exception as e:
            rospy.logerr("Error ejecutando la prueba: %s", e)
            self._server.set_aborted(ReflejosResult(result=-1.0))

if __name__ == '__main__':
    rospy.init_node('servidor_reflejos')
    ServidorReflejos()
    rospy.spin()