# Navegación y Uso de run_all.sh
Script orquestador en **bash** encargado de levantar el sistema mínimo de navegación del robot TIAGo para el proyecto.

Automatiza la carga secuencial de **RViz**, el **Servidor de Mapas**, la **Lógica de Autolocalización** (`set_initial_pose.py`) y el nodo de **Lógica de Navegación** (`checkpoint_follower.py`), gestionando los tiempos de espera necesarios entre procesos para asegurar una carga correcta y evitar conflictos.

Este script está pensado para pruebas y validación rápida del sistema de navegación en un entorno controlado.

---

## 1. Ubicación en el Paquete
Este script se encuentra dentro de la carpeta `scripts/` del paquete `mover_pkg`. Asume la siguiente estructura de archivos relativa:

```text
mover_pkg/
├── launch/
│   └── rviz.launch                     ← Configuración de visualización
├── maps/
│   ├── Mapa_aula_mod_1.0.yaml          ← Metadatos del mapa
│   └── Mapa_aula_mod_1.0.pgm           ← Imagen del mapa
├── scripts/
│   ├── README.md
│   ├── run_all.sh                      ← ESTE SCRIPT
│   └── run_rviz_web.sh
└── src/
    └── mover_pkg/
        ├── README.md
        ├── checkpoint_follower.py      ← Nodo de lógica de movimiento
        └── set_initial_pose.py         ← Nodo de lógica de autolocalización
```

---

## 2. Qué hace este script
El script ejecuta una secuencia lineal de arranque diseñada para evitar condiciones de carrera (race conditions):

1. Carga el Workspace: Hace source del entorno de trabajo local (devel/setup.bash).
2. Lanza RViz: Ejecuta roslaunch mover_pkg rviz.launch en segundo plano (background) y guarda su PID.
3. Espera (4s): Da tiempo a que la interfaz gráfica de RViz cargue completamente.
4. Carga el Mapa: Lanza el map_server apuntando al archivo .yaml definido.
5. Espera (5s): Asegura que el mapa esté publicado y disponible en el topic /map antes de continuar, este tiempo puede ser ajustado pero con menos tiempo no carga correctamente.
6. Lanza la Lógica de Autolocalización: Ejecuta el nodo de set_initial_pose.py, que  publica una estimación de la posición inicial del robot y lo gira un poco para que se localize bien.
7. Lanza la Lógica: Ejecuta el nodo de control checkpoint_follower.py para mandar al TIAGo a X puntos.
8. Gestión de Procesos: Mantiene el script vivo (wait) mientras los nodos hijos sigan corriendo.

---

## 3. Uso
```bash
    cd carpeta_compartida/psico_ws/src/mover_pkg/scripts/
    ./run_all.sh
```

---

## 4. Nodos gestionados
Este script es responsable de levantar los siguientes componentes:
   * RViz (rviz): Visualización del estado del robot, mapa y sensores.
   * Map Server (map_server): Publica el mapa estático del aula en /map.
   * Autolocalización (set_initial_pose.py): Nodo python para localizar al robot antes de moverlo.
   * Checkpoint Follower (checkpoint_follower.py): Cliente Python que envía al robot a las posiciones objetivo.


    
