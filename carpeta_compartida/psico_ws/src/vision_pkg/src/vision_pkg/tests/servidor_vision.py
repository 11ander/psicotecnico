#!/usr/bin/env python3
import rospy
import actionlib
from vision_pkg.msg import VisionAction, VisionResult, VisionGoal
from pruebavision import evaluar_vision
from chekfollow import Follower
from moverbrazotiago import main

class ServidorVision(object):
    def __init__(self):
        self._server = actionlib.SimpleActionServer(
            'vision',
            VisionAction,
            execute_cb=self.execute_cb,
            auto_start=False
            
        )
        self._server.start()
        rospy.loginfo("Action server 'vision' listo.")

    def execute_cb(self, goal: VisionGoal):
        if self._server.is_preempt_requested():
            rospy.logwarn("Preempt solicitado.")
            self._server.set_preempted()
            return

        # Aquí recibimos la cadena del cliente
        user_string = getattr(goal, 'input_str', "")
        if not user_string:
            rospy.logwarn("Cadena vacía recibida. Puntuación = 0.")
            self._server.set_succeeded(VisionResult(result=0.0))
            return

        try:

            follower = Follower()
            main()
            follower.enviar_puntos([follower.punto_vision2])
            rospy.sleep(5)
            follower.enviar_puntos([follower.punto_vision3])
            rospy.sleep(5)
            follower.enviar_puntos([follower.punto_mesa])
            rospy.sleep(5)

            nota = evaluar_vision(user_string)
            nota = float(nota)
            
            rospy.loginfo(f"✅ Evaluación completada. Nota: {nota:.2f}/10")
            self._server.set_succeeded(VisionResult(result=nota))

        except Exception as e:
            rospy.logerr("Error en evaluación: %s", e)
            self._server.set_aborted(VisionResult(result=-1.0))

if __name__ == '__main__':
    rospy.init_node('servidor_vision')
    servidor = ServidorVision()
    rospy.spin()