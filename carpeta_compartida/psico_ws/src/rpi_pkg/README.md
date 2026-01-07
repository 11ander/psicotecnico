# rpi_pkg

Paquete ROS 1 Noetic que se ejecuta en la **Raspberry Pi 3B** del proyecto **PSICOTÉCNICO**.

Este paquete se encarga de **interactuar con el hardware físico** (LEDs, pulsadores, zumbador y LCD) para ejecutar:

1) **Prueba de reflejos** (tablero de 6 LEDs + 6 pulsadores).  
2) **Prueba de memoria** (secuencia de LEDs a recordar y reproducir).  
3) Publicación del **estado de un pulsador** (usado por `audicion_pkg` en la subprueba de reacción auditiva).

Incluye **Action Servers** para reflejos y memoria (consumidos por el nodo central, `web_server_pkg`) y un nodo publisher para el pulsador.

---

## Resumen de las pruebas

### Prueba de reflejos

- Se enciende un LED aleatorio del tablero (6 posibles).
- El usuario debe pulsar el **botón asociado** dentro de un **tiempo límite**.
- La dificultad aumenta reduciendo el tiempo límite por nivel.
- La prueba finaliza si:
  - Se pulsa un botón incorrecto, o
  - Se agota el tiempo sin pulsar.

**Puntuación:** suma puntos por nivel superado.

---

### Prueba de memoria

- Se muestra una secuencia de LEDs (aleatoria) de longitud creciente.
- El usuario debe repetir la secuencia pulsando los botones en el mismo orden.
- La dificultad aumenta incrementando el número de pasos de la secuencia.

**Puntuación:** suma puntos por nivel superado y se detiene al fallar.

---

### Publicación del estado de un pulsador (para audición)

- Publica continuamente si un pulsador está presionado (`True/False`) en un topic ROS.
Esto permite que `audicion_pkg` use el **pulsador físico** de la Raspberry Pi en su subprueba de **reacción a estímulos auditivos**.

---

## Estructura del paquete

```text
rpi_pkg/
├── action/
│   ├── Memoria.action
│   └── Reflejos.action
├── include/
│   └── rpi_pkg/
        └── .gitkeep
├── launch/
│   └── .gitkeep
├── scripts/
│   └── iniciar_rpi.sh
├── src/
│   └── rpi_pkg/
│       ├── .gitkeep
│       ├── estado_pulsador.py
│       ├── grove_rgb_lcd.py
│       ├── memoria.py
│       ├── reflejos.py
│       ├── servidor_memoria.py
│       └── servidor_reflejos.py
├── CMakeLists.txt
├── package.xml
└── setup.py
```
---

## Requisitos y dependencias

### Software

- ROS 1 Noetic.
- Workspace catkin configurado (`psico_ws`) también en la Raspberry Pi.
- Python 3.

### Librerías Python (hardware)

- `gpiozero` (lectura de pulsadores y control de LEDs).
- Soporte I2C para el LCD Grove (driver incluido en `grove_rgb_lcd.py`).

Tener I2C habilitado en la Raspberry Pi y el cableado correcto.

### Hardware
- **Raspberry Pi** (En este caso se ha usado la Raspberry Pi 3B)
- **LEDs (GPIO):** 5, 16, 18, 22, 24, 26  
- **Pulsadores (GPIO):** 6, 17, 19, 23, 25, 27  
- **Zumbador PWM (GPIO):** 12  
- **LCD Grove I2C:** usado para mostrar instrucciones y feedback.

Además, para `estado_pulsador.py`:

- Pulsador por defecto en GPIO **6** (parametrizable)

---

## Compilación

Desde el workspace (en la Raspberry Pi):

```bash
cd ~/psicotecnico/carpeta_compartida/psico_ws
catkin build
source devel/setup.bash
```

---

## Ejecución

### 0) Red y ROS Master

Antes de lanzar el paquete, hay que asegurarse de que la Raspberry Pi está conectada al **mismo ROS Master (TIAGo)** y con las variables de entorno correctamente configuradas:

- `ROS_MASTER_URI`
- `ROS_IP` --> Cambiar para tener la IP del dispositivo

Para facilitar esta configuración, se ha creado un archivo `setup_env.sh` que debe ejecutarse antes de lanzar cualquier nodo ROS:

```bash
cd ~/psicotecnico/carpeta_compartida
source setup_env.sh
```

Comprobación rápida (en terminal) de que está correctamente ejecutado:

```bash
echo $ROS_IP
echo $ROS_MASTER_URI
```
Debería aparecer la IP del dispositivo donde se está ejecutando

### 1) Arranque completo (recomendado): `iniciar_rpi.sh`

El paquete incluye un script para lanzar **todos los procesos necesarios** de la Raspberry Pi con un único comando:

- Action Server de **reflejos**
- Action Server de **memoria**
- Publisher del **estado del pulsador** (para la subprueba de audición)

Uso:

```bash
./src/rpi_pkg/scripts/iniciar_rpi.sh
```
Contenido de `src/rpi_pkg/scripts/iniciar_rpi.sh`:

```bash
#!/usr/bin/env bash
cd /home/pi/psicotecnico/carpeta_compartida || exit 1
source setup_env.sh
source /opt/ros/noetic/setup.bash
source psico_ws/devel/setup.bash
rosrun rpi_pkg servidor_reflejos.py &
rosrun rpi_pkg servidor_memoria.py &
rosrun rpi_pkg estado_pulsador.py &
wait
```
Nota: este script deja los nodos en primer plano (con wait). Para detenerlos, usa Ctrl+C.

## Acciones ROS
Este paquete expone dos acciones ROS para integrar las pruebas de reflejos y memoria dentro del sistema completo.

El uso de acciones ROS permite:
* Lanzar cada prueba de forma asíncrona desde un cliente.
* Evitar bloqueos en el cliente mientras la prueba está en ejecución.
* Recuperar la puntuación objetiva una vez finalizada.

### Acción ROS: `Reflejos.action`
La prueba de reflejos se expone mediante una acción ROS servida por `servidor_reflejos.py`.

* **Goal**
    * `input` (bool): Indica cuándo debe iniciarse la prueba de reflejos.
* **Result**
    * `result` (float): Devuelve la puntuación obtenida en la prueba.
    * *En caso de error interno, devuelve -1.0.*

### Acción ROS: `Memoria.action`
La prueba de memoria se expone mediante una acción ROS servida por `servidor_memoria.py`.

* **Goal**
    * `input` (bool): Indica cuándo debe iniciarse la prueba de memoria.
* **Result**
    * `result` (float): Devuelve la puntuación obtenida en la prueba.
    * *En caso de error interno, devuelve -1.0.*

---

## Topic ROS (pulsador para audición)
* **Topic:** `/rpi/button6/pressed` (por defecto)
* **Publicado por:** `estado_pulsador.py`
* **Tipo:** `std_msgs/Bool`

**Funcionamiento:**
* `True` → pulsador presionado.
* `False` → pulsador no presionado.

Este topic se usa en `audicion_pkg` (subprueba de reacción auditiva).
---

## Descripción de scripts

### `servidor_reflejos.py`
Action Server ROS (reflejos) que:
* Espera un goal (`input=True`).
* Ejecuta la prueba de reflejos con hardware real (`test_reflejos()`).
* Devuelve la puntuación final como `result`.

### `reflejos.py`
Implementación de la lógica de la prueba de reflejos:
* Selección aleatoria de LED.
* Detección de botón correcto/incorrecto.
* Gestión del tiempo límite por nivel.
* Mensajes por LCD (`setText`) y feedback por zumbador.

### `servidor_memoria.py`
Action Server ROS (memoria) que:
* Espera un goal (`input=True`).
* Ejecuta la prueba de memoria con hardware real (`test_memoria()`).
* Devuelve la puntuación final como `result`.

### `memoria.py`
Implementación de la prueba de memoria:
* Generación de secuencia aleatoria de LEDs.
* Presentación de secuencia (LEDs) y captura de respuesta (botones).
* Mensajes en LCD y señal acústica con zumbador.

### `estado_pulsador.py`
Nodo ROS publisher del estado del pulsador:
* Publica `std_msgs/Bool` con el estado (pressed / not pressed).
* Se usa por `audicion_pkg` en la subprueba de reacción auditiva.

### `grove_rgb_lcd.py`
Driver auxiliar para el LCD Grove I2C. Se usa desde `memoria.py` y `reflejos.py` para mostrar instrucciones y feedback al usuario.

---

## Notas de integración con el sistema PSICOTÉCNICO
* Este paquete se ejecuta en la **Raspberry Pi**, pero normalmente **TIAGo** actúa como ROS master en el sistema completo.
* `web_server_pkg` llama a las acciones `reflejos` y `memoria` para obtener la puntuación.
* `audicion_pkg` se suscribe al topic del pulsador para su subprueba de reacción auditiva (`/rpi/button6/pressed` por defecto).
