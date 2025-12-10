#!/usr/bin/env bash
set -euo pipefail

# Directorio del workspace (donde está este script)
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cargar workspace (extiende /opt/ros/noetic)
source "$WS_DIR/devel/setup.bash"

export DISABLE_ROS1_EOL_WARNINGS=1

PIDS=()

cleanup() {
  echo "[MOVE] Limpiando procesos de navegación (rviz / map_server)..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "  - kill $pid"
      kill "$pid" 2>/dev/null || true
    fi
  done
  echo "[MOVE] Limpieza de navegación completa."
}

trap cleanup SIGINT SIGTERM

echo "[MOVE] Lanzando rviz..."
roslaunch mover_pkg rviz.launch &
RVIZ_PID=$!
PIDS+=("$RVIZ_PID")
echo "[MOVE] Lanzado rviz con PID $RVIZ_PID"
sleep 4

echo "[MOVE] Lanzando map_server..."
MAP_YAML="$WS_DIR/src/mover_pkg/maps/Mapa_aula_mod_1.0.yaml"
rosrun map_server map_server "$MAP_YAML" &
MAP_PID=$!
PIDS+=("$MAP_PID")
echo "[MOVE] Lanzado map_server con PID $MAP_PID"
sleep 1

echo "[MOVE] Publicando pose inicial..."
rosrun mover_pkg set_initial_pose.py

echo "[MOVE] Preparación de movimiento completada. rviz y map_server siguen activos."
echo "[MOVE] Este script se quedará en segundo plano para poder hacer cleanup correcto."

# Mantener el script vivo para que el trap funcione y el start_psicotecnico pueda matarlo
while true; do
  sleep 5
done
