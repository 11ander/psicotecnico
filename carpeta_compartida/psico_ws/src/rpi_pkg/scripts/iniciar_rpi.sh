#!/usr/bin/env bash
cd /home/pi/psicotecnico/carpeta_compartida || exit 1
source setup_env.sh
source /opt/ros/noetic/setup.bash
source psico_ws/devel/setup.bash
rosrun rpi_pkg servidor_reflejos.py &
rosrun rpi_pkg servidor_memoria.py &
rosrun rpi_pkg estado_pulsador.py &
wait
