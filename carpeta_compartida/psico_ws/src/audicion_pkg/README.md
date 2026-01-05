# audicion_pkg
Paquete ROS 1 noetic para ejecutar la **prueba de audición** del proyecto PSICOTECNICO con el robot **TIAGo** de PAL Robotics.

Este paquete implementa un **Action Server** que coordina:
1) **Emisión de pitidos** por el altavoz de TIAGo.  
2) **Registro de respuestas** del usuario mediante **un pulsador en la Raspberry Pi** (publicado por `rpi_pkg/estado_pulsador.py`).  
3) Envío de **datos de la prueba** al nodo central (`web_server_pkg`) para calcular la nota final.

También incluye un cliente de acciones que permite ejecutar la prueba por separado y sin depender del web server.

---

## Resumen de la prueba
La prueba de audición se divide en dos subpruebas:

### Subprueba 1 — Conteo de pitidos
- TIAGo emite una secuencia de pitidos con **número total e intervalos aleatorios**.
- El sistema **guarda cuántos pitidos reales** se han emitido.
- El usuario introduce en el **web_server** cuántos cree haber escuchado.
- El Action Server devuelve el número real para que el **web_server** calcule el resultado final.

### Subprueba 2 — Tiempo de reacción a estímulos auditivos
- TIAGo emite pitidos.
- El usuario debe **pulsar un botón (iluminado) en la Raspberry Pi** cuando oye el pitido.
- Se registran:
  - **Aciertos**: pulsación desde que suena el pitido hasta 1s después.
  - **Fallos**: pulsaciones sin pitido (falsos positivos).
- Se devuelve el resumen de aciertos/fallos y pitidos totales.

---

## Estructura del paquete
```text
audicion_pkg/
├── action/
│   └── Audicion.action
├── include/
│   └── audicion_pkg/
├── launch/
    └── audicion_action_server.launch
├── src/
│   └── audicion_pkg/
│       ├── __init__.py
│       ├── audicion_action.py
│       ├── cliente_action_audicion.py
│       ├── prueba2.py
│       ├── prueba_audicion.py
│       └── speaker.py
├── CMakeLists.txt
├── package.xml
└── setup.py
```

---

## Requisitos y dependencias

### Software
- ROS 1 Noetic.
- Workspace catkin configurado (`psico_ws`).

### Dependencia adicional (PAL Robotics): `pal_interaction_msgs`
El paquete `audicion_pkg` utiliza el módulo `speaker.py` para la generación de estímulos acústicos.
Este módulo ha sido implementado sobre el sistema de **Text-To-Speech de TIAGo** (`/tts`), por lo que requiere los mensajes definidos en `pal_interaction_msgs`.
Como el sistema de TIAGo usa TTS (`/tts`) y mensajes de PAL, se necesitan instalar los mensajes. Para ello habría que realizar lo siguiente:
```bash
cd ~/psicotecnico/carpeta_compartida/psico_ws/src
git clone https://github.com/pal-robotics/pal_msgs.git
rosdep install --from-paths . --ignore-src -r -y
cd ..
catkin build
source devel/setup.bash
```

### Dependencia externa (obligatoria para la subprueba de reacción)
Para que funcione la subprueba de **tiempo de reacción**, debe estar corriendo en la **Raspberry Pi** el nodo:
- `rpi_pkg/estado_pulsador.py`
Este nodo publica en ROS el estado de un pulsador (pulsado/no pulsado) y mantiene su LED asociado encendido durante la prueba.  
`audicion_pkg` se suscribe a ese topic para detectar la respuesta del usuario.

### Hardware
- TIAGo (altavoz operativo).
- Raspberry Pi 3B con pulsador/LED configurado.

---

## Compilación
Desde el workspace:
```bash
cd ~/psicotecnico/carpeta_compartida/psico_ws
catkin build
source devel/setup.bash
```

---

## Ejecución

### 0) Red y ROS Master
Antes de lanzar el paquete, hay que asegurarse de que el PC  y la Raspberry Pi están conectados al **mismo ROS Master (el TIAGo)** y con las variables de entorno correctamente configuradas:
- `ROS_MASTER_URI`
- `ROS_IP` --> Cambiar para tener la IP del dispositivo

Para facilitar esta configuración, se ha creado un archivo `setup_env.sh` que debe ejecutarse tanto en la **Raspberry Pi** como en el **PC** antes de lanzar cualquier nodo ROS:
```bash
cd ~/psicotecnico/carpeta_compartida
source setup_env.sh
```

Este script se encarga de establecer las variables necesarias para que ambos equipos se comuniquen correctamente con el ROS master del TIAGo.
Comprobación rápida (en terminal) de que está correctamente ejecutado:
```bash
echo $ROS_IP
echo $ROS_MASTER_URI
```
Debería aparecer la IP del dispositivo donde se está ejecutando, y después http://tiago-222c:11311.

---

### 1) Lanzar el nodo de la Raspberry Pi (obligatorio para la subprueba de reacción)
En la Raspberry Pi:
```bash
rosrun rpi_pkg estado_pulsador.py
```

Este nodo:
- Publica continuamente el estado de un pulsador (pulsado / no pulsado).
- Mantiene el LED asociado encendido durante la prueba de audición.

Comprobación rápida (en terminal) de que está correctamente ejecutado:
```bash
rostopic echo /rpi/button6/pressed
```

Debería verse True si se está pulsando el pulsador o False de lo contrario. 

### 2) Lanzar el Action Server de audición
En terminal del PC:
```bash
roslaunch audicion_pkg audicion_action_server.launch
```
o
```bash
rosrun audicion_pkg audicion_action.py
```

Este nodo queda a la espera de recibir un goal para ejecutar la prueba completa de audición (subprueba de conteo + subprueba de tiempo de reacción).

### 3) Probar la prueba sin el servidor web
Para ejecutar la prueba de audición sin pasar por web_server_pkg, se puede usar el cliente de acciones incluido:
```bash
rosrun audicion_pkg cliente_action_audicion.py
```

---

## Acción ROS: `Audicion.action`
La prueba de audición se expone mediante una **acción ROS**, lo que permite ejecutar la prueba de forma asíncrona e integrarla fácilmente con otros módulos del sistema, como el `web_server_pkg` o clientes de consola.

El uso de una acción ROS permite:
- Lanzar la prueba completa con una única orden y de forma asíncrona.
- Esperar una orden de empiece.
- Evitar bloqueos en el cliente mientras la prueba está en ejecución.
- Recuperar los resultados objetivos una vez finalizada la prueba.

### Goal
- **`ejecutar`** (`bool`)  
  Indica cuando debe iniciarse la prueba de audición.  

### Result
El Action Server devuelve un conjunto de valores numéricos con los resultados objetivos de la prueba de audición.  
Estos valores no constituyen la nota final, sino los datos necesarios para que el nodo central realice la evaluación cuando pregunte al usuario el número de pitidos que ha escuchado en la prueba de reflejos auditivos.

Los resultados se devuelven en un array de 4 enteros con el siguiente significado:
- **Número total de pitidos en la subprueba 1**.
- **Número total de pitidos en la subprueba 2**.
- **Número de aciertos en la subprueba de tiempo de reacción**.
- **Número de fallos (pulsaciones sin pitido) en la subprueba de tiempo de reacción**.

Estos datos son utilizados posteriormente por el `web_server_pkg` (o el cliente de action para las pruebas) para:
- Comparar el número real de pitidos con la respuesta introducida por el usuario.
- Calcular la puntuación final de la prueba de audición.

---

## Archivo launch
El paquete incluye un archivo launch para arrancar el **Action Server de la prueba de audición** de forma sencilla, sin necesidad de ejecutar el nodo manualmente.
Este launch es la forma recomendada de arrancar la prueba de audición en integración con el sistema completo.

### `audicion_action_server.launch`
Este launch:
- Arranca el Action Server audicion_action_server.
- Ejecuta el script audicion_action.py.
- Permite añadir fácilmente parámetros ROS en el futuro sin modificar el código.

Uso:
```bash
roslaunch audicion_pkg audicion_action_server.launch
```

---

## Descripción de Scripts

### `audicion_action.py`
Action Server principal del paquete. Coordina la ejecución completa de la prueba de audición:
- Recibe el *goal* desde el cliente de acciones (normalmente `web_server_pkg`).
- Ejecuta un script de ambas subpruebas a realizar.
- Recopila las métricas generadas durante ambas subpruebas.
- Devuelve los datos objetivos al cliente de la acción para su evaluación final indicándole que la prueba ha finalizado.

### `speaker.py`
Módulo auxiliar para la generación de estímulos acústicos mediante el altavoz de TIAGo:
- Centraliza la lógica de emisión de pitidos.
- Implementa los pitidos utilizando el Action Server `/tts` de TIAGo.
- Garantiza un comportamiento consistente en ambas subpruebas.
- Facilita la reutilización del código para otros estímulos sonoros del sistema como por ejemplo explicaciones de pruebas.

### `prueba_audicion.py`
Script principal que implementa **ambas subpruebas de audición**:
- **Subprueba 1 – Conteo de pitidos**:
  - Genera una secuencia de pitidos con número e intervalos aleatorios.
  - Registra el número real de pitidos emitidos.
- **Subprueba 2 – Tiempo de reacción ante estímulos auditivos**:
  - Llama a una clase creada para realizar dicha prueba.
- Devuelve al Action Server las métricas objetivas de ambas subpruebas

### `prueba2.py`
Script que implementa una clase para realizar la subprueba de tiempo de reacción ante estímulos auditivos:
- Emite pitidos utilizando el módulo `speaker.py`.
- Lee el estado del pulsador publicado por la Raspberry Pi.
- Registra aciertos y fallos en función del instante de la pulsación.
- Genera las métricas objetivas de esta parte de la prueba (aciertos, fallos=falsas_pulsaciones y número totales de pitidos).

Por ende, la evaluación de esta subprueba tiene en cuenta dos tipos de penalización:
- **Pulsaciones sin estímulo**: se contabilizan como fallos (falsos positivos).
- **Ausencia de pulsación tras un pitido**: reduce la puntuación al disminuir la relación aciertos / pitidos totales.

### `cliente_action_audicion.py`
Cliente de acciones ROS para pruebas y depuración:
- Envía un *goal* al Action Server de audición.
- Permite ejecutar la prueba completa desde consola.
- Muestra por pantalla el resultado devuelto por el servidor sin necesidad de usar la interfaz web.
