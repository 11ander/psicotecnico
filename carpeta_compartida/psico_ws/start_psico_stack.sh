#!/usr/bin/env bash
set -euo pipefail

export PINGGY_SSH_TARGET="fNnCriCVNH6@eu.pro.pinggy.io"
export PINGGY_ENABLE=true

########################################
#  CONFIG BÁSICA
########################################

# Directorio del workspace (asumimos que el script está en la raíz de psico_ws)
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${WS_DIR}/logs/bringup"
mkdir -p "${LOG_DIR}"

# Flags para el webserver (se pueden sobreescribir por entorno)
NO_LOGIN="${NO_LOGIN:-false}"
MUTE="${MUTE:-false}"
NO_TEST="${NO_TEST:-false}"

# DB de embeddings de caras
DB_PATH_DEFAULT="package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json"
DB_PATH="${DB_PATH:-$DB_PATH_DEFAULT}"

# Pinggy: objetivo SSH (NO metas el token en el script, expórtalo en el entorno)
# Ejemplo:
#   export PINGGY_SSH_TARGET="fNnCriCVNH6@eu.pro.pinggy.io"
PINGGY_SSH_TARGET="${PINGGY_SSH_TARGET:-}"
PINGGY_ENABLE="${PINGGY_ENABLE:-true}"

# Mapa (para map_server)
MAP_YAML="${WS_DIR}/src/mover_pkg/maps/Mapa_aula_mod_1.0.yaml"

########################################
#  COLORES / LOGGING
########################################
NC='\033[0m'
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()   { echo -e "${RED}[ERR ]${NC}  $*"; }

step() {
  # Línea tipo "[..] Texto..." que luego se sobreescribe con ✔/✖
  local msg="$1"
  printf "${BOLD}[..]${NC} %-60s" "${msg}"
}

step_ok() {
  local msg="$1"
  printf "\r${GREEN}[ ✔ ]${NC} %-60s\n" "${msg}"
}

step_fail() {
  local msg="$1"
  printf "\r${RED}[ ✖ ]${NC} %-60s\n" "${msg}"
}

########################################
#  BANNER
########################################
print_banner() {
  cat << 'EOF'
 ________  ________  ___  ________  ________  _________  _______   ________  ________   ___  ________  ________     
|\   __  \|\   ____\|\  \|\   ____\|\   __  \|\___   ___\\  ___ \ |\   ____\|\   ___  \|\  \|\   ____\|\   __  \    
\ \  \|\  \ \  \___|\ \  \ \  \___|\ \  \|\  \|___ \  \_\ \   __/|\ \  \___|\ \  \\ \  \ \  \ \  \___|\ \  \|\  \   
 \ \   ____\ \_____  \ \  \ \  \    \ \  \\\  \   \ \  \ \ \  \_|/_\ \  \    \ \  \\ \  \ \  \ \  \    \ \  \\\  \  
  \ \  \___|\|____|\  \ \  \ \  \____\ \  \\\  \   \ \  \ \ \  \_|\ \ \  \____\ \  \\ \  \ \  \ \  \____\ \  \\\  \ 
   \ \__\     ____\_\  \ \__\ \_______\ \_______\   \ \__\ \ \_______\ \_______\ \__\\ \__\ \__\ \_______\ \_______\
    \|__|    |\_________\|__|\|_______|\|_______|    \|__|  \|_______|\|_______|\|__| \|__|\|__|\|_______|\|_______|
             \|_________|                                                                                           

EOF
}

########################################
#  GESTIÓN DE PROCESOS
########################################
ROSLAUNCH_PIDS=()
BG_PIDS=()

cleanup() {
  echo
  log_info "Cerrando stack Psicotécnico…"

  # Intentar matar Pinggy / noVNC / Xvfb / fluxbox / x11vnc
  log_info "Matando Xvfb/x11vnc/fluxbox/websockify (si existen)…"
  killall -q x11vnc Xvfb fluxbox websockify 2>/dev/null || true

  # Matar roslaunches controlados
  if ((${#ROSLAUNCH_PIDS[@]})); then
    log_info "Matando roslaunch activos…"
    for pid in "${ROSLAUNCH_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
    done
  fi

  # Matar procesos auxiliares
  if ((${#BG_PIDS[@]})); then
    log_info "Matando procesos auxiliares…"
    for pid in "${BG_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
    done
  fi

  # Intentar matar el head_manager si sigue vivo
  if command -v rosnode >/dev/null 2>&1; then
    if rosnode list 2>/dev/null | grep -q "/pal_head_manager"; then
      log_info "Matando /pal_head_manager…"
      rosnode kill /pal_head_manager 2>/dev/null || true
    fi
  fi

  log_ok "Stack parado correctamente."
}

trap cleanup SIGINT SIGTERM EXIT

########################################
#  HELPERS
########################################

start_rviz_stack() {
  step "Arrancando RViz remoto (Xvfb + x11vnc + noVNC)…"

  # Limpiar restos de sesiones anteriores
  killall -q x11vnc Xvfb fluxbox websockify 2>/dev/null || true

  export DISABLE_ROS1_EOL_WARNINGS=1
  export DISPLAY=:2

  # 1) Lanzar RViz (usa mover_pkg/rviz.launch)
  roslaunch mover_pkg rviz.launch \
    > "${LOG_DIR}/rviz.launch.log" 2>&1 &
  local rviz_pid=$!
  BG_PIDS+=("$rviz_pid")

  # 2) Xvfb
  Xvfb :2 -screen 0 1920x1080x24 -ac \
    > "${LOG_DIR}/xvfb.log" 2>&1 &
  BG_PIDS+=("$!")

  sleep 2

  # 3) fluxbox
  fluxbox \
    > "${LOG_DIR}/fluxbox.log" 2>&1 &
  BG_PIDS+=("$!")

  # 4) x11vnc
  x11vnc -display :2 -nopw -forever -shared -rfbport 5901 -localhost \
    > "${LOG_DIR}/x11vnc.log" 2>&1 &
  BG_PIDS+=("$!")

  # 5) noVNC
  /usr/share/novnc/utils/launch.sh --vnc localhost:5901 --listen 6081 \
    > "${LOG_DIR}/novnc.log" 2>&1 &
  BG_PIDS+=("$!")

  sleep 3
  step_ok "RViz remoto (noVNC en puerto 6081). Logs en ${LOG_DIR}/rviz.launch.log"
}

start_map_server() {
  step "Lanzando map_server con ${MAP_YAML}…"

  if [[ ! -f "${MAP_YAML}" ]]; then
    step_fail "map_server (no existe ${MAP_YAML})"
    log_err "No se encuentra el mapa: ${MAP_YAML}"
    return 1
  fi

  rosrun map_server map_server "${MAP_YAML}" \
    > "${LOG_DIR}/map_server.log" 2>&1 &
  BG_PIDS+=("$!")

  sleep 2
  step_ok "map_server lanzado. Log: ${LOG_DIR}/map_server.log"
}

run_initial_pose() {
  step "Publicando pose inicial (set_initial_pose.py)…"

  # Ahora el script está en web_server_pkg
  if ! rosrun web_server_pkg set_initial_pose.py \
       > "${LOG_DIR}/set_initial_pose.log" 2>&1; then
    step_fail "set_initial_pose.py"
    log_err "Error al ejecutar set_initial_pose.py (ver ${LOG_DIR}/set_initial_pose.log)"
    return 1
  fi

  step_ok "Pose inicial publicada. Log: ${LOG_DIR}/set_initial_pose.log"
}

kill_head_manager() {
  step "Intentando matar /pal_head_manager…"

  if ! command -v rosnode >/dev/null 2>&1; then
    step_fail "rosnode no disponible"
    log_warn "rosnode no está en PATH, no puedo comprobar /pal_head_manager."
    return 1
  fi

  if rosnode list 2>/dev/null | grep -q "/pal_head_manager"; then
    if rosnode kill /pal_head_manager \
         > "${LOG_DIR}/pal_head_manager_kill.log" 2>&1; then
      step_ok "/pal_head_manager detenido."
    else
      step_fail "rosnode kill /pal_head_manager"
      log_err "Fallo al matar /pal_head_manager (ver ${LOG_DIR}/pal_head_manager_kill.log)"
      return 1
    fi
  else
    step_ok "/pal_head_manager no estaba en ejecución."
  fi
}

start_roslaunch() {
  local pkg="$1"
  local launch_file="$2"
  local label="$3"
  shift 3
  local extra_args=("$@")

  local log_file="${LOG_DIR}/${pkg}_${launch_file%.launch}.log"

  step "Lanzando ${label} (${pkg}/${launch_file})…"

  roslaunch "${pkg}" "${launch_file}" "${extra_args[@]}" \
    > "${log_file}" 2>&1 &
  local pid=$!
  ROSLAUNCH_PIDS+=("$pid")

  # Pequeña espera para ver si casca al arrancar
  sleep 5

  if kill -0 "$pid" 2>/dev/null; then
    step_ok "${label} en marcha (pid=${pid}). Log: ${log_file}"
    return 0
  else
    step_fail "${label} se ha detenido al inicio"
    log_err "${label} ha fallado al arrancar. Revisa ${log_file}"
    return 1
  fi
}

start_pinggy() {
  if [[ "${PINGGY_ENABLE,,}" != "true" ]]; then
    log_info "Pinggy desactivado (PINGGY_ENABLE=${PINGGY_ENABLE})."
    return 0
  fi

  if [[ -z "${PINGGY_SSH_TARGET}" ]]; then
    log_warn "PINGGY_SSH_TARGET no definido; no se lanza túnel Pinggy."
    log_warn "Ejemplo: export PINGGY_SSH_TARGET=\"fNnCriCVNH6@eu.pro.pinggy.io\""
    return 0
  fi

  step "Iniciando túnel Pinggy (HTTP → 5000)…"

  # IMPORTANTE:
  # -R0:localhost:5000  -> expone el webserver Flask
  # -L4300:localhost:4300 -> mantiene tu forward local 4300 (si lo usas)
  ssh -p 443 \
      -R0:localhost:5000 \
      -L4300:localhost:4300 \
      -o StrictHostKeyChecking=no \
      -o ServerAliveInterval=30 \
      "${PINGGY_SSH_TARGET}" \
      > "${LOG_DIR}/pinggy.log" 2>&1 &

  local pid=$!
  BG_PIDS+=("$pid")

  sleep 3
  if kill -0 "$pid" 2>/div/null 2>/dev/null; then
    step_ok "Pinggy activo. Log: ${LOG_DIR}/pinggy.log"
    log_info "Revisa la URL pública en el log de Pinggy cuando lo necesites."
  else
    step_fail "Pinggy no se ha mantenido en ejecución"
    log_err "El túnel Pinggy se ha caído al inicio. Ver ${LOG_DIR}/pinggy.log"
  fi
}

########################################
#  MAIN
########################################
main() {
  clear
  print_banner

  echo -e "${BOLD}Workspace:${NC} ${WS_DIR}"
  echo
  echo -e "${BOLD}CONFIG:${NC}"
  echo "  NO_LOGIN = ${NO_LOGIN}"
  echo "  MUTE     = ${MUTE}"
  echo "  NO_TEST  = ${NO_TEST}"
  echo "  DB_PATH  = ${DB_PATH}"
  echo "  LOG_DIR  = ${LOG_DIR}"
  echo

  # 1) Entorno ROS
  if [[ -f "/opt/ros/noetic/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source /opt/ros/noetic/setup.bash
  else
    log_err "/opt/ros/noetic/setup.bash no encontrado."
    exit 1
  fi

  if [[ -f "${WS_DIR}/devel/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "${WS_DIR}/devel/setup.bash"
  else
    log_err "${WS_DIR}/devel/setup.bash no encontrado. Ejecuta 'catkin build' primero."
    exit 1
  fi

  # 2) Comprobar que hay roscore
  if ! rosnode list >/dev/null 2>&1; then
    log_err "No se detecta roscore. Lanza 'roscore' en otra terminal antes de este script."
    exit 1
  fi

  echo
  log_info "Iniciando stack Psicotécnico…"

  ####################################
  # ORDEN:
  #   1) RViz remoto
  #   2) map_server
  #   3) set_initial_pose
  #   4) kill head_manager
  #   5) FaceRec + Audición + Coordinación + WebServer
  #   6) Pinggy
  ####################################

  # 1) RViz remoto
  start_rviz_stack || log_warn "RViz remoto ha reportado algún problema inicial."

  # 2) Mapa
  sleep 4
  start_map_server || log_warn "map_server ha reportado algún problema."

  # 3) Pose inicial
  sleep 1
  run_initial_pose || log_warn "set_initial_pose ha reportado algún problema."

  # 4) Matar cabeza
  kill_head_manager || log_warn "No se ha podido matar /pal_head_manager (puede no ser crítico)."

  # 5) Servidores de acciones y webserver
  echo
  log_info "Lanzando servidores ROS del Psicotécnico…"

  # Face recognition
  if ! start_roslaunch \
      "face_recognition_pkg" \
      "face_recognition_server.launch" \
      "Face Recognition" \
      db_path:="${DB_PATH}"
  then
    log_err "Face Recognition no está en marcha. El login por cara no funcionará."
  fi

  # Audición (AQUÍ nos aseguramos que lanzamos audicion_pkg)
  if ! start_roslaunch \
      "audicion_pkg" \
      "audicion_action_server.launch" \
      "Audición"
  then
    log_err "Servidor de Audición no está en marcha."
  fi

  # Coordinación / movilidad
  if ! start_roslaunch \
      "coordinacion_pkg" \
      "mobility_exam_server.launch" \
      "Coordinación / Movilidad"
  then
    log_err "Servidor de Coordinación no está en marcha."
  fi

  # Web server Flask + ROS
  if ! start_roslaunch \
      "web_server_pkg" \
      "web_server.launch" \
      "Web Server" \
      no_login:="${NO_LOGIN}" \
      mute:="${MUTE}" \
      no_test:="${NO_TEST}"
  then
    log_err "El Web Server no se ha podido lanzar. Revisa logs."
  fi

  # 6) Pinggy (túnel HTTP → 5000)
  echo
  start_pinggy

  echo
  log_ok "Todos los componentes configurados. Ctrl+C para detener el stack completo."
  echo "Los logs detallados están en: ${LOG_DIR}"
  echo

  # Bucle de vigilancia ligero (no imprescindible, pero útil)
  while true; do
    sleep 5
    for pid in "${ROSLAUNCH_PIDS[@]}"; do
      if ! kill -0 "$pid" 2>/dev/null; then
        log_warn "Un roslaunch (pid=${pid}) ha terminado. Revisa los logs correspondientes."
      fi
    done
  done
}

main
