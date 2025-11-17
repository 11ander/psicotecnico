#!/bin/bash

# Cargar mi ws
source /home/robotica_tiago/carpeta_compartida/psico_ws/devel/setup.bash

# Lanzar rviz
roslaunch mover_pkg rviz.launch &
RVIZ_PID=$!
echo "[INFO] Lanzado rviz con PID $RVIZ_PID"

# Esperar un momento para que se abra rviz y le de tiempo antes de cargar el mapa
sleep 4

# Cargar entorno de ROS
source /opt/ros/noetic/setup.bash

# Lanzar el map_server
rosrun map_server map_server /home/robotica_tiago/carpeta_compartida/psico_ws/src/mover_pkg/maps/Mapa_aula_mod_1.0.yaml &
MAP_PID=$!
echo "[INFO] Lanzado map_server con PID $MAP_PID"

# Esperar un momento para asegurarse de que el mapa esta bien lanzado
sleep 5

# Cargar mi ws
source /home/robotica_tiago/carpeta_compartida/psico_ws/devel/setup.bash

# Lanzar los demas nodos
rosrun mover_pkg checkpoint_follower.py &
CHECKPOINT_PID=$!
echo "[INFO] Lanzado checkpoint_follower con PID $CHECKPOINT_PID"

# Esperar a que terminen todos los procesos lanzados
wait