#!/bin/bash

# Script para preparar el entorno para RViz en un contenedor Docker

# Paso 1: Iniciar Xvfb en el display :2
echo "Iniciando Xvfb en display :2"
Xvfb :2 -screen 0 1280x800x24 &
export DISPLAY=:2

# Paso 2: Iniciar fluxbox (gestor de ventanas)
echo "Iniciando fluxbox en display :2"
fluxbox &

# Paso 3: Iniciar x11vnc para compartir el display
echo "Iniciando x11vnc para compartir el display :2"
x11vnc -display :2 -rfbport 5901 -forever -shared -nopw &

# Paso 4: Iniciar websockify para habilitar el acceso web
echo "Iniciando websockify en puerto 6080"
websockify --web=/usr/share/novnc/ 6080 localhost:5901 &

# Paso 5: Instrucción para lanzar RViz manualmente
echo "El entorno está listo. Ahora puedes lanzar RViz manualmente."
echo "Ejecuta 'rviz -d /ruta/a/tu/configuracion.rviz &' en una nueva terminal."

# Fin del script