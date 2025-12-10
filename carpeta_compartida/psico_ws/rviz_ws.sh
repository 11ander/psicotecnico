#!/usr/bin/env bash
set -e

killall -q x11vnc Xvfb fluxbox websockify 2>/dev/null || true

source /home/robotica_tiago/carpeta_compartida/psico_ws/devel/setup.bash
export DISABLE_ROS1_EOL_WARNINGS=1
export DISPLAY=:2
roslaunch mover_pkg rviz.launch &

sleep 4

source /opt/ros/noetic/setup.bash

# Lanzar el map_server
rosrun map_server map_server /home/robotica_tiago/carpeta_compartida/psico_ws/src/mover_pkg/maps/Mapa_aula_mod_1.0.yaml &


# Esperar un momento para asegurarse de que el mapa esta bien lanzado
sleep 1

# Cargar mi ws
source /home/robotica_tiago/carpeta_compartida/psico_ws/devel/setup.bash

# Localizarse en posicion inicial
rosrun mover_pkg set_initial_pose.py

set -euo pipefail

# ==== Detectar IP privada (192.168.x.x) ====
HOST_IP=$(hostname -I | tr ' ' '\n' | grep '^192\.168\.' | head -n1 || true)

# Fallback: si no encuentra 192.168.x.x coge la primera IP que haya
if [[ -z "${HOST_IP}" ]]; then
  HOST_IP=$(hostname -I | awk '{print $1}')
fi

echo "[vd] IP detectada para VNC/noVNC: ${HOST_IP}"

# ==== Xvfb ====
export DISPLAY=:2

echo "[vd] Xvfb :2..."
Xvfb :2 -screen 0 1920x1080x24 -ac &
sleep 2

# ==== Fluxbox (gestor de ventanas ligero) ====
echo "[vd] fluxbox..."
fluxbox > /tmp/fluxbox_rviz_web.log 2>&1 &

# ==== x11vnc (servidor VNC) ====
echo "[vd] x11vnc 5901 en ${HOST_IP}..."
# OJO: quitamos -localhost y, opcionalmente, fijamos la IP con -listen
x11vnc \
  -display :2 \
  -nopw \
  -forever \
  -shared \
  -rfbport 5901 \
  -listen "${HOST_IP}" \
  > /tmp/x11vnc_rviz_web.log 2>&1 &

# ==== noVNC (websocket + cliente VNC en el navegador) ====
echo "[vd] noVNC 6081 (VNC -> ${HOST_IP}:5901)..."
/usr/share/novnc/utils/launch.sh \
  --vnc "${HOST_IP}:5901" \
  --listen "${HOST_IP}:6081"

#Para que la camara se vea en el webserver
rosrun web_video_server web_video_server &