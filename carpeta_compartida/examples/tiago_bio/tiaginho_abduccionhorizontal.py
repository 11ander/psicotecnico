from control_tiago import ControladorTiago
from math import pi
from time import sleep
from copy import deepcopy

controlador = ControladorTiago()
controlador.set_velocity_and_acceleration_arm(0.05, 0.05)

# Obtener configuración inicial
config_inicial = controlador.get_current_joints()

# Configuración con brazo abajo al frente del cuerpo
config_brazo_abajo = deepcopy(config_inicial)
config_brazo_abajo[1] = 1.3    # sin desplazamiento lateral
config_brazo_abajo[2] = 1   # brazo abajo
config_brazo_abajo[4] = 0.0     # codo extendido

# Configuración con brazo al frente (elevación frontal máxima)
config_brazo_frente = deepcopy(config_inicial)
config_brazo_frente[1] = 1.3   # mantener frontalidad
config_brazo_frente[2] = -pi/3 # elevar brazo al frente hasta 60°
config_brazo_frente[4] = 0.0    # codo extendido

# Bucle: subir y bajar brazo al frente (como elevación frontal)
while True:
    controlador.move_joints(config_brazo_frente)
    sleep(1)
    controlador.move_joints(config_brazo_abajo)
    sleep(1)
