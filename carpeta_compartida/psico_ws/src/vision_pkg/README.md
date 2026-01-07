#  vision_pkg

---

##  Descripción

**vision_pkg** es un paquete de **ROS (Robot Operating System)** que implementa una **prueba psicotécnica automatizada de agudeza visual** para el robot **TIAGo**.  
El sistema integra **navegación autónoma**, **manipulación con el brazo**  y **evaluación lógica**, gestionando todo el ciclo de la prueba.

---

##  Flujo del sistema

El test de visión se ejecuta en varias fases claramente definidas:

* **Recogida de material**  
  * Localización y agarre de un cuaderno o papel desde una mesa, luego vuelve a donde esta el paciente para comenzar la prueba.

* **Navegación coordinada**  
  * Desplazamiento autónomo a puntos estratégicos:
    * `punto_vision2`
    * `punto_vision3`

* **Interacción con el usuario**
  * El usuario metera por teclado en el webserver las letras que ha visto en el papel que sostiene TIAGo.

* **Evaluación automática**
  * Comparación de las frases leídas con las frases de referencia para una nota final.

---

##  Estructura del paquete

```text
vision_pkg/
├── action/
│   └── Vision.action
├── include/
│   └── vision_pkg/
│       └── .gitkeep
├── launch/
│   └── .gitkeep
├── src/
│   └── vision_pkg/
│       ├── .gitkeep
│       ├── checkpoint_follower_api.py
│       ├── coger_papel.py
│       ├── pruebavision.py
│       ├── servidor_vision.py
│       └── test_vision_client.py
├── CMakeLists.txt
├── package.xml
└── setup.py
```

---

##  Descripción de archivos

* **checkpoint_follower_api.py**  
  * API para gestionar el movimiento de la base mediante `move_base`.
  * Monitoriza el estado de navegación del robot.
  * Este archivo define la clase Follower, que es un “mini-driver” para navegar sin usar un action client formal, publicando directamente goals en:
  * Publica: `/move_base/goal (MoveBaseActionGoal)`
  * Lee pose del robot: `/robot_pose (PoseWithCovarianceStamped)`

* **coger_papel.py**  
  * Este nodo ejecuta una secuencia completa estilo “Pick & Place” combinando:
    * Base: usando la clase de `CheckpointFollower` de `checkpoint_follower_api.py` para mover el robot.
    * Brazo: con `actionlib` a `/arm_controller/follow_joint_trajectory` para mover el brazo robotico.
    * Gripper: publicando `JointTrajectory` a `/gripper_controller/command` para abrir y cerra el gripper.
    * Seguridad: parada por Ctrl+C manda cmd_vel=0 y cancela goals del brazo.
  * Es el nodo que se encarga de agarrar el cuaderno agarrado y de volvcer a la posición donde se empezaara la prueba visual.

* **servidor_vision.py**  
  * Servidor de acción principal (`vision_action`).
  * Orquesta toda la secuencia de la prueba.

* **pruebavision.py**  
  * Motor de evaluación del test visual.
  * Compara los caracteres leídos por el paciente con los del papel que sostiene el robot:
    * `CARTEL_LINEA1`
    * `CARTEL_LINEA2`
  * Devuelve la nota final del paciente.

* **test_vision_client.py**  
  * Cliente de pruebas para lanzar la acción y recibir feedback del sistema.

---

##  Requisitos

* **ROS**
  * Noetic

* **Controladores activos**
  * `/arm_controller`
  * `/gripper_controller`
  * `/mobile_base_controller`

* **Navegación**
  * Nodo `move_base` configurado.
  * Mapa del entorno cargado.

---

##  Instalación

### 1. Compilación

```bash
cd ~/catkin_ws/src
git clone https://github.com/11ander/psicotecnico.git
cd ..
catkin_make
source devel/setup.bash
```

---

##  Uso

### *1. Recogida del cuaderno*

* Ejecuta la secuencia de manipulación para que TIAGo se acerque a la mesa y agarre el cuaderno/papel:
  * El robot navega por puntos de aproximación.
  * Coloca el brazo en la pose de pick.
  * Cierra el gripper para agarrar el cuaderno.
  * Retrocede a una posición segura.

```bash
rosrun vision_pkg coger_papel.py
```
### *2. Lanzar servidor de vision*
* Arranca el Action Server vision_action, que orquesta toda la prueba:
  * Navega a punto_vision2 (distancia intermedia) y punto_vision3 (distancia lejana).
  * Sube el brazo a la pose de mostrar el cuaderno.
  * Gira la muñeca 180º para enseñar la parte trasera.
  * Publica feedback con la fase actual y devuelve las frases originales como result.

```bash
rosrun vision_pkg servidor_vision.py
```

### *2. Lanzar cliente de prueba*

* Ejecuta un cliente simple para comprobar el funcionamiento del servidor:
  * Envía VisionGoal(ejecutar=True).
  * Muestra por consola el feedback de fases.
  * Espera y muestra el resultado final (ok).
```bash
  rosrun vision_pkg test_vision_client.py
```

---

## Configuración

* Frases de referencia definidas en `pruebavision.py.`
* Puntos de navegación:
  * Coordenadas definidas en `Follower.__init__.`:
    ```bash
    [x, y, z_orient, w_orient]
    ```

