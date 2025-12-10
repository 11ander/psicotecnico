#!/usr/bin/env bash
set -euo pipefail

# ===========================
#  CONFIG BÁSICA / COLORES
# ===========================
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${WS_DIR}/logs/launcher"
mkdir -p "${LOG_DIR}"

GREEN="\e[32m"
RED="\e[31m"
YELLOW="\e[33m"
BLUE="\e[34m"
BOLD="\e[1m"
RESET="\e[0m"

TICK="${GREEN}✔${RESET}"
CROSS="${RED}✖${RESET}"

# Flags de entorno para el webserver (se pasan como args a roslaunch)
NO_LOGIN_ENV="${NO_LOGIN:-false}"
MUTE_ENV="${MUTE:-false}"
NO_TEST_ENV="${NO_TEST:-false}"

echo -e "${BOLD}"
echo "============================================"
echo "   PSICOTÉCNICO – LAUNCHER COMPLETO TIAGo   "
echo "============================================"
echo -e "${RESET}"
echo "Workspace: ${WS_DIR}"
echo "Logs:      ${LOG_DIR}"
echo
echo -e "Webserver flags:"
echo -e "  NO_LOGIN = ${NO_LOGIN_ENV}"
echo -e "  MUTE     = ${MUTE_ENV}"
echo -e "  NO_TEST  = ${NO_TEST_ENV}"
echo

# ===========================
#  LIMPIEZA PREVIA
# ===========================
echo -e "${YELLOW}[*] Limpiando procesos gráficos previos (x11vnc, Xvfb, fluxbox, websockify)...${RESET}"
killall -q x11vnc Xvfb fluxbox websockify 2>/dev/null || true

# ===========================
#  ENTORNO ROS
# ===========================
if [[ -f "${WS_DIR}/devel/setup.bash" ]]; then
  source "${WS_DIR}/devel/setup.bash"
else
  echo -e "${RED}[ERROR]${RESET} No se encuentra ${WS_DIR}/devel/setup.bash"
  echo "        Ejecuta 'catkin build' antes de usar este script."
  exit 1
fi

export DISABLE_ROS1_EOL_WARNINGS=1
export DISPLAY=:2

# ===========================
#  DETECTAR IP PRIVADA
# ===========================
HOST_IP=$(hostname -I | tr ' ' '\n' | grep '^192\.168\.' | head -n1 || true)
if [[ -z "${HOST_IP}" ]]; then
  HOST_IP=$(hostname -I | awk '{print $1}')
fi

echo -e "${BLUE}[i]${RESET} IP detectada para VNC/noVNC: ${BOLD}${HOST_IP}${RESET}"
echo

# ===========================
#  GESTIÓN DE PROCESOS
# ===========================
BG_PIDS=()
ROS_PIDS=()

start_bg() {
  local key="$1"    # nombre corto para el log
  local label="$2"  # descripción bonita
  shift 2

  local log_file="${LOG_DIR}/${key}.log"

  echo -ne "  - ${label} ... "

  "$@" >"${log_file}" 2>&1 &
  local pid=$!

  sleep 2

  if kill -0 "${pid}" 2>/dev/null; then
    echo -e "${TICK}  (pid=${pid})"
    BG_PIDS+=("${pid}")
  else
    echo -e "${CROSS}  (falló al inicio, ver log: ${log_file})"
  fi
}

start_roslaunch() {
  local key="$1"
  local label="$2"
  local pkg="$3"
  local launch_file="$4"
  shift 4
  local extra_args=("$@")

  local log_file="${LOG_DIR}/${key}.log"

  echo -ne "  - ${label} (${pkg} ${launch_file}) ... "

  roslaunch "${pkg}" "${launch_file}" "${extra_args[@]}" >"${log_file}" 2>&1 &
  local pid=$!

  sleep 5

  if kill -0 "${pid}" 2>/dev/null; then
    echo -e "${TICK}  (pid=${pid})"
    ROS_PIDS+=("${pid}")
  else
    echo -e "${CROSS}  (falló al inicio, ver log: ${log_file})"
  fi
}

cleanup() {
  echo
  echo -e "${YELLOW}[CLEANUP] Terminando roslaunch y procesos gráficos...${RESET}"

  for pid in "${ROS_PIDS[@]:-}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      echo "  - kill roslaunch pid=${pid}"
      kill "${pid}" 2>/dev/null || true
    fi
  done

  for pid in "${BG_PIDS[@]:-}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      echo "  - kill bg pid=${pid}"
      kill "${pid}" 2>/dev/null || true
    fi
  done

  echo -e "${YELLOW}[CLEANUP] Hecho.${RESET}"
}
trap cleanup SIGINT SIGTERM

# ===========================
#  [1/3] ENTORNO GRÁFICO
# ===========================
echo -e "${BOLD}[1/3] Entorno gráfico y VNC/noVNC${RESET}"

start_bg "xvfb" "Xvfb (display :2)" \
  Xvfb :2 -screen 0 1920x1080x24 -ac

start_bg "fluxbox" "Fluxbox (gestor de ventanas)" \
  fluxbox

start_bg "x11vnc" "x11vnc (servidor VNC :5901)" \
  x11vnc \
    -display :2 \
    -nopw \
    -forever \
    -shared \
    -rfbport 5901 \
    -listen "${HOST_IP}"

start_bg "novnc" "noVNC (websocket VNC :6081)" \
  /usr/share/novnc/utils/launch.sh \
    --vnc "${HOST_IP}:5901" \
    --listen "${HOST_IP}:6081"

echo
echo -e "${GREEN}Entorno VNC/noVNC listo.${RESET}"
echo -e "  • Visor RViz/noVNC:  ${BOLD}http://${HOST_IP}:6081${RESET}"
echo

# ===========================
#  [2/3] RVIZ + MAPA + INITIAL POSE + CÁMARA
# ===========================
echo -e "${BOLD}[2/3] Navegación: RViz, mapa, pose inicial y cámara${RESET}"

# 1) RViz
start_bg "rviz" "RViz (mover_pkg/rviz.launch)" \
  roslaunch mover_pkg rviz.launch

# Respeta tu sleep original
sleep 4

# 2) map_server
start_bg "map_server" "map_server (Mapa_aula_mod_1.0.yaml)" \
  rosrun map_server map_server \
    "${WS_DIR}/src/mover_pkg/maps/Mapa_aula_mod_1.0.yaml"

# Sleep antes de initial pose
sleep 1

# Re-source del ws
source "${WS_DIR}/devel/setup.bash"

# 3) set_initial_pose.py AHORA EN web_server_pkg
echo -ne "  - Posición inicial del robot (web_server_pkg/set_initial_pose.py) ... "
if rosrun web_server_pkg set_initial_pose.py >"${LOG_DIR}/set_initial_pose.log" 2>&1; then
  echo -e "${TICK}"
else
  echo -e "${CROSS}  (ver log: ${LOG_DIR}/set_initial_pose.log)"
fi

# 4) web_video_server para la cámara
start_bg "web_video_server" "web_video_server (/xtion/rgb/image_raw)" \
  rosrun web_video_server web_video_server

echo
echo -e "${GREEN}Navegación lista.${RESET}"
echo -e "  • Cámara web_video_server: ${BOLD}http://${HOST_IP}:8080${RESET}"
echo

# ===========================
#  [3/3] STACK PSICOTÉCNICO
# ===========================
echo -e "${BOLD}[3/3] Lanzando stack de pruebas psicotécnicas${RESET}"

# Intentar matar la cabeza, pero sin romper el script si no existe
echo -ne "  - Matando nodo /pal_head_manager (si existe) ... "
if rosnode kill /pal_head_manager >"${LOG_DIR}/kill_head.log" 2>&1; then
  echo -e "${TICK}"
else
  echo -e "${YELLOW}no estaba activo${RESET}"
fi

# 1) Face recognition
start_roslaunch "face_recognition" "Face Recognition" \
  "face_recognition_pkg" "face_recognition_server.launch" \
  db_path:="package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json"

# 2) Audición
start_roslaunch "audicion" "Audición" \
  "audicion_pkg" "audicion_action_server.launch"

# 3) Coordinación / movilidad
start_roslaunch "coordinacion" "Coordinación / Movilidad" \
  "coordinacion_pkg" "mobility_exam_server.launch"

# 4) Webserver
start_roslaunch "web_server" "Web Server" \
  "web_server_pkg" "web_server.launch" \
  no_login:="${NO_LOGIN_ENV}" \
  mute:="${MUTE_ENV}" \
  no_test:="${NO_TEST_ENV}"

echo
echo -e "${GREEN}[OK] Todos los componentes principales están lanzados.${RESET}"
echo -e "${BLUE}[i]${RESET} Panel usuario/admin:"
echo -e "    ${BOLD}http://${HOST_IP}:5000${RESET}"
echo
echo -e "${BLUE}[i]${RESET} Pulsa Ctrl+C en esta terminal para detener TODO el sistema."
echo

# Mantener vivo el launcher
while true; do
  sleep 3
done
