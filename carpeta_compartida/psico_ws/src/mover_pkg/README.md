# mover_pkg
Paquete de ROS1 Noetic para la **navegación de la base del robot TIAGo** en el proyecto.

Su objetivo es proporcionar utilidades para:
- Cargar el **mapa estático** del laboratorio.
- Visualizar navegación en **rviz** con una configuración predefinida.
- Enviar al robot a **checkpoints (waypoints)** mediante un nodo Python (`checkpoint_follower.py`).
- Levantar un bringup mínimo de navegación mediante scripts/launch.
- Levantar RViz para integrarlo con el panel de administración del `web_server_pkg` (`run_rviz_web.sh`).

---

## Estructura del paquete

```text
mover_pkg/
├── configs/
│   └── rviz_configs.rviz
├── include/
│   └── mover_pkg/
├── launch/
│   ├── checkpoint_bringup.launch
│   └── rviz.launch
├── maps/
│   ├── Mapa_aula_mod_1.0.pgm
│   ├── Mapa_aula_mod_1.0.yaml
│   ├── mapa1.pgm
│   └── mapa1.yaml
├── scripts/
│   ├── README.md
│   ├── run_all.sh
│   └── run_rviz_web.sh
├── src/
│   └── mover_pkg/
│       ├── README.md
│       ├── checkpoint_follower.py
│       └── set_initial_pose.py
├── CMakeLists.txt
├── package.xml
└── README.md
```

---

## Requisitos y dependencias
Software
- ROS Noetic.
- Stack de navegación de TIAGo.
- map_server para publicar el mapa.
- move_base_msgs para mensajes de move base.

En caso de no tener estos dos últimos, para instalarlos manualmente ejecutar en terminal:
```bash
sudo apt install ros-noetic-map-server
sudo apt install ros-noetic-move-base-msgs
```

Otro paquete util para mover la base del robot de forma manual, aunque no obligatorio, sería:
- teleop-twist-keyboard
Para instalarlo:
```bash
sudo apt install ros-noetic-teleop-twist-keyboard
```
Para ejecutarlo y poder mover el TIAGo manualmente
```bash
source /opt/ros/noetic/setup.bash
rosrun teleop_twist_keyboard teleop_twist_keyboard.py cmd_vel:=mobile_base_controller/cmd_vel
```

---

## Mapas incluidos
En maps/ hay dos versiones del mismo mapa:
- `mapa1.*`: mapa original.
- `Mapa_aula_mod_1.0.*`: versión editada y lista para usar en el laboratorio (recomendada).

---

## Compilación
Desde el workspace:
```bash
cd ~/psicotecnico/carpeta_compartida/psico_ws
catkin build
source devel/setup.bash
```

---

## Uso
### 1. Bringup mínimo de navegación (sin RViz)
El paquete incluye un launch que levanta un bringup mínimo equivalente al script de pruebas, pero en formato .launch y sin RViz.
```bash
roslaunch mover_pkg checkpoint_bringup.launch
```

Este bringup se usa cuando:
- Se quiere cargar el mapa y dejar listo el entorno de navegación.
- No se necesita visualización en RViz.

### 2. RViz (visualización local)
Para abrir RViz con la configuración del paquete:
```bash
roslaunch mover_pkg rviz.launch
```

Este launch carga configs/rviz_configs.rviz, donde están preconfigurados el mapa y capas típicas de navegación para verlas desde el visualizador, como por ejemplo el propio robot.

### 3. Checkpoints (waypoints) con el nodo Python
El nodo checkpoint_follower.py envía objetivos a navegación y recorre una lista de checkpoints.

Documentación detallada en:
- [`src/mover_pkg/README.md`](src/mover_pkg/README.md)

### 4. Establecer la pose inicial del robot (`set_initial_pose.py`)
El script `set_initial_pose.py` es un nodo auxiliar que permite **establecer automáticamente la pose inicial del robot** en el mapa.

Su función principal es:
- Publicar una pose inicial aproximada para el robot y girarlo durante unos pocos segundos para que se localice mejor.
- Facilitar que el sistema de localización (amcl) converja correctamente sin necesidad de introducir la pose manualmente desde RViz.

Este script se utiliza típicamente:
- Al iniciar una sesión de navegación.
- Tras reiniciar el robot o el stack de localización.
- Antes de ejecutar movimientos por checkpoints o navegación autónoma.

El uso de este script reduce errores de localización inicial y simplifica el flujo de arranque del sistema en un entorno controlado como el laboratorio.

### 5. Script de validación rápida (RViz + mapa + follower)
Para pruebas internas y validación rápida del entorno, se incluye un script que automatiza:
- RViz
- map_server
- set_initial_pose.py
- checkpoint_follower.py

Documentación detallada:
- [`scripts/README.md`](scripts/README.md)

### 6. RViz para el panel admin del `web_server_pkg` (opcional)
El script `run_rviz_web.sh` se utiliza para lanzar una instancia de **RViz** configurada específicamente para su uso junto al **panel de administración del `web_server_pkg`**.

Su objetivo es proporcionar **visualización en tiempo real del estado del robot** mientras el sistema web está en ejecución, permitiendo:
- Ver la posición y orientación actual del robot sobre el mapa.
- Facilitar la localización del robot dentro del entorno.
- Apoyar el envío manual del robot a una pose objetivo desde el panel de administración (según la integración del proyecto).

Este script **no lanza la lógica de navegación ni el checkpoint follower**, únicamente la visualización necesaria para la supervisión y control manual desde la interfaz web.

Uso típico:
- El `web_server_pkg` se lanza de forma independiente.
- En paralelo, se ejecuta `run_rviz_web.sh` para disponer de RViz como herramienta de apoyo visual para el administrador.

---

## Notas finales
Este paquete no reemplaza el stack de navegación de TIAGo: se apoya en move_base y en la localización (amcl).

Si el robot no navega correctamente, normalmente el fallo está en:
- localización/pose inicial
- mapa no publicado correctamente
- move_base no levantado o sin transforms correctas
