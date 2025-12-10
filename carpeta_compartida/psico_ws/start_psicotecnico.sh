#!/usr/bin/env bash
set -euo pipefail

# === Configuración básica ===
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Si quieres ser explícito con la distro:
# source /opt/ros/noetic/setup.bash
if [[ -f "$WS_DIR/devel/setup.bash" ]]; then
  source "$WS_DIR/devel/setup.bash"
else
  echo "[ERROR] No se encuentra $WS_DIR/devel/setup.bash"
  echo "        Ejecuta 'catkin build' antes de usar este script."
  exit 1
fi

# Flags para el webserver (se pueden sobreescribir por entorno)
NO_LOGIN="${NO_LOGIN:-false}"
MUTE="${MUTE:-false}"
NO_TEST="${NO_TEST:-false}"

# DB para face_recognition (por si algún día quieres cambiarla)
DB_PATH_DEFAULT="package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json"
DB_PATH="${DB_PATH:-$DB_PATH_DEFAULT}"

echo "===[ PSICOTECNICO BRINGUP ]==="
echo "Workspace: $WS_DIR"
echo
echo "[CONFIG]"
echo "  NO_LOGIN = $NO_LOGIN"
echo "  MUTE     = $MUTE"
echo "  NO_TEST  = $NO_TEST"
echo "  DB_PATH  = $DB_PATH"
echo

# Array para guardar PIDs de todos los roslaunch
PIDS=()

cleanup() {
  echo
  echo "[CLEANUP] Terminando todos los roslaunch..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "  - kill $pid"
      kill "$pid" 2>/dev/null || true
    fi
  done
  echo "[CLEANUP] Hecho."
}

trap cleanup SIGINT SIGTERM

start_launch() {
  local pkg="$1"
  local launch_file="$2"
  local label="$3"
  shift 3
  local extra_args=("$@")

  echo
  echo ">>> Iniciando ${label}..."
  echo "    roslaunch ${pkg} ${launch_file} ${extra_args[*]:-}"
  roslaunch "$pkg" "$launch_file" "${extra_args[@]}" &
  local pid=$!
  PIDS+=("$pid")

  # Espera corta para ver si casca nada más arrancar
  sleep 5

  if kill -0 "$pid" 2>/dev/null; then
    echo "[OK] ${label} en marcha (pid=${pid})."
  else
    echo "[ERROR] ${label} se ha detenido al inicio. Abortando bringup."
    exit 1
  fi
}

# === Lanzamos cada componente, de forma secuencial y controlada ===

#Matamos la cabeza

#Hay que poner esto con try except. 
#rosnode kill /pal_head_manager

# 1) Face recognition
start_launch \
  "face_recognition_pkg" \
  "face_recognition_server.launch" \
  "Face Recognition" \
  db_path:="$DB_PATH"

# 2) Audición
start_launch \
  "audicion_pkg" \
  "audicion_action_server.launch" \
  "Audición"

# 3) Coordinación / movilidad
start_launch \
  "coordinacion_pkg" \
  "mobility_exam_server.launch" \
  "Coordinación"

# 4) Webserver
start_launch \
  "web_server_pkg" \
  "web_server.launch" \
  "Web Server" \
  no_login:="$NO_LOGIN" \
  mute:="$MUTE" \
  no_test:="$NO_TEST"

echo
echo "[INFO] Todos los componentes están lanzados."
echo "[INFO] Pulsa Ctrl+C para detener el stack completo."

# Mantener el script vivo mientras los roslaunch siguen
while true; do
  sleep 2
  # Si alguno muere, avisamos (opcionalmente podrías abortar)
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[WARN] Un roslaunch (pid=$pid) ha terminado. Revisa los logs."
    fi
  done
done
