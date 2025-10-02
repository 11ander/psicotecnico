
from control_tiago import ControladorTiago
from math import pi
from time import sleep
from copy import deepcopy

controlador = ControladorTiago()

# Configurar velocidad lenta para observar el movimiento
controlador.set_velocity_and_acceleration_arm(0.05, 0.05)

# Obtener configuración actual
config_inicial = controlador.get_current_joints()

# Crear una configuración con el brazo bajado
config_brazo_abajo = deepcopy(config_inicial)
config_brazo_abajo[2] = 1  # brazo hacia abajo

# Crear configuración con el brazo levantado verticalmente
config_brazo_arriba = deepcopy(config_inicial)
config_brazo_arriba[2] = -pi / 3  # levantar brazo hacia adelante/arriba

# Bucle de movimiento hacia arriba y hacia abajo
while True:
    controlador.move_joints(config_brazo_arriba)
    sleep(1)
    controlador.move_joints(config_brazo_abajo)
    sleep(1)