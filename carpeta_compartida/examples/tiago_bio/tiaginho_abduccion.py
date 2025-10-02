from control_tiago import ControladorTiago
from math import pi
from time import sleep
from copy import deepcopy

controlador = ControladorTiago()
controlador.set_velocity_and_acceleration_arm(0.05, 0.05)

# Obtener configuración inicial
config_inicial = controlador.get_current_joints()

# Configuración con brazo abajo (inicio)
config_brazo_abajo = deepcopy(config_inicial)
config_brazo_abajo[1] = 0.07   # posición lateral fija
config_brazo_abajo[2] = 1.0    # brazo abajo
config_brazo_abajo[4] = 0.0    # codo extendido

# Configuración con brazo arriba (abducción máxima)
config_brazo_arriba = deepcopy(config_inicial)
config_brazo_arriba[1] = 0.07   # mantener misma lateralidad
config_brazo_arriba[2] = -pi/3  # levantar brazo al máximo
config_brazo_arriba[4] = 0.0    # mantener brazo extendido

# Bucle: levantar y bajar brazo extendido
while True:
    controlador.move_joints(config_brazo_arriba)
    sleep(1)
    controlador.move_joints(config_brazo_abajo)
    sleep(1)

