# `web_server_pkg` — Orquestador + UI Web del psicotécnico (ROS1)

Paquete ROS (Noetic) que actúa como **“cerebro” del proyecto**: levanta un **webserver Flask** con interfaz gráfica (HTML/JS/CSS) y coordina la ejecución de las pruebas mediante **Action Servers ROS**.

Este nodo:
- Gestiona **login** (por reconocimiento facial o modo sin login).
- Permite **seleccionar el orden de pruebas** desde la web.
- Envía **goals** a los distintos action servers y **recibe resultados**.
- En pruebas que lo requieren, **bloquea la secuencia** hasta que el examinador introduzca datos en la UI (ej. Audición P2 y Visión).
- Genera **informe PDF** de la última sesión y guarda un **CSV** con notas.
- Incluye utilidades de movilidad (checkpoints con `move_base`) y TTS (`/tts` de TIAGo).

---

## Vista rápida

- **Web UI (usuario):** selección y ejecución de pruebas + resultados + descarga de PDF.
- **Web UI (admin):** histórico, movilidad por presets/coordenadas, stream de cámara y RViz remoto (si están disponibles).
- **Backend:** Flask + actionlib (ROS) + hilos para no bloquear peticiones.
- **Persistencia:** `src/web_server_pkg/data/history.csv` (solo notas) + memoria en runtime (`HISTORICO`, `SESION`).

---

## Estructura del paquete

```
web_server_pkg/
├─ launch/
│  └─ web_server.launch
├─ src/web_server_pkg/
│  ├─ app.py                    # Flask + orquestación ROS (principal)
│  ├─ pruebas_client.py          # Clientes ActionLib para cada prueba
│  ├─ speak_api.py               # Wrapper TTS (/tts) para TIAGo
│  ├─ checkpoint_follower_api.py # Publica goals a /move_base/goal y espera llegada
│  ├─ set_initial_pose.py        # Publica /initialpose y hace un pequeño “spin”
│  ├─ report.py                  # Generación de PDF (ReportLab)
│  ├─ templates/
│  │  ├─ login.html
│  │  ├─ index.html              # Panel usuario
│  │  └─ admin_index.html        # Panel admin
│  └─ static/
│     ├─ css/ (app.css, index.css)
│     ├─ js/  (login.js, index.js, admin.js)
│     └─ img/ (logo-deusto.png)
└─ package.xml, CMakeLists.txt, setup.py
```

---

## Requisitos

### Software
- ROS1 **Noetic**
- Python 3 (entorno de Noetic)
- `flask`
- `reportlab` (para PDF)

### ROS (topics/actions esperados)
Este paquete **no implementa las pruebas**: solo las orquesta. Deben estar lanzados los action servers correspondientes:

**Login por cara**
- Action: `face_recognition_pkg/FaceRecognitionAction`
- Server name: `face_recognition_action`

**Pruebas**
- Memoria:
  - Action: `rpi_pkg/MemoriaAction`
  - Server name: `memoria`
- Reflejos:
  - Action: `rpi_pkg/ReflejosAction`
  - Server name: `reflejos`
- Audición:
  - Action: `audicion_pkg/AudicionAction`
  - Server name: `audicion_action`
- Coordinación / Movilidad:
  - Action: `coordinacion_pkg/MobilityExamAction`
  - Server name: `mobility_exam_action`
- Visión:
  - Action: `vision_pkg/VisionAction`
  - Server name: `vision_action`

**Movilidad TIAGo (opcional, para auto-movimiento y panel admin)**
- Publica a: `/move_base/goal` (`move_base_msgs/MoveBaseActionGoal`)
- Lee pose en: `/robot_pose` (`geometry_msgs/PoseWithCovarianceStamped`)

**TTS (opcional)**
- Action: `/tts` (`pal_interaction_msgs/TtsAction`)

> Si alguna dependencia no está lanzada, el webserver seguirá levantando, pero la prueba correspondiente puede devolver `-1`, `None` o un error controlado según el cliente.

---

## Lanzar el webserver

### Opción recomendada: `roslaunch`
```bash
roslaunch web_server_pkg web_server.launch
```

El servidor escucha por defecto en:
- `http://0.0.0.0:5000` (accesible desde la red, según firewall)

### Flags disponibles (roslaunch)
En `launch/web_server.launch`:

- `no_login` (default `false`): omite reconocimiento facial y entra como “Prueba”.
- `mute` (default `false`): silencia TTS (también se puede por entorno).
- `no_test` (default `false`): activa “modo demo” con resultados ficticios (seed) si no hay histórico.

Ejemplos:
```bash
# 1) Desarrollo rápido sin login
roslaunch web_server_pkg web_server.launch no_login:=true

# 2) Modo silencioso
roslaunch web_server_pkg web_server.launch mute:=true

# 3) Demo con resultados pre-cargados
roslaunch web_server_pkg web_server.launch no_login:=true no_test:=true
```

### Variables de entorno
- `FLASK_SECRET_KEY`: clave de sesión de Flask (recomendado cambiarla en despliegue).
- `PSICO_MUTE=1|true`: alternativa a `--mute`.

---

## Flujo funcional

### 1) Arranque
Al arrancar, `app.py`:
- Inicializa ROS (`rospy.init_node(..., disable_signals=True)`).
- Inicializa `TiagoSpeaker()` (si `/tts` está disponible, salvo mute).
- Lanza en background un movimiento a **“puerta”** para que el robot quede listo para el login:
  - `mover_robot_a_puerta_inicio()` (usa `Follower.punto_puerta` o `PREPROGRAMMED_POINTS['puerta']`).

### 2) Login
En la UI (`/login`):
- El botón “Login” hace `POST /api/login`.
- Si `--no-login`: entra como `"Prueba"`.
- Si login real:
  - Lanza `face_login()` y espera hasta **20 min** por reconocimiento.
  - Cuando reconoce, guarda el nombre en sesión y saluda por TTS.
  - Después del login, intenta mover a **“mesa”** y pedir que el paciente se siente.

### 3) Selección y ejecución de pruebas
En el panel (`/`):
- El usuario define una cola (orden) de pruebas.
- “Empezar” hace `POST /start` con `{"order":[...]} `.
- El backend lanza un hilo `worker()` que:
  1. (Opcional) mueve el robot a un checkpoint según la prueba.
  2. Anuncia la prueba por TTS y da una explicación corta.
  3. Ejecuta el action client correspondiente.
  4. Guarda el resultado en `SESION["resultados"]`.

### 4) Pruebas con input del examinador
Hay pruebas que requieren que el examinador introduzca datos en la web:

- **Audición (P2)**:
  - El action devuelve métricas y pide input: `requiere_input=True`.
  - El backend se queda bloqueado (`threading.Event`) esperando `POST /answer`.
  - El front muestra un input numérico (“¿Cuántos pitidos escuchaste…?”).
  - Con eso se calcula `nota_p2` y la nota final (media con P1).

- **Visión (frases)**:
  - El action devuelve `frase_1` y `frase_2` y pide input.
  - El front muestra dos campos de texto.
  - El backend puntúa comparando texto normalizado (sin acentos, minúsculas) con `SequenceMatcher` y convierte a 0–10.

### 5) Fin y generación de informe
Al terminar la secuencia:
- Se guarda una sesión en memoria (`HISTORICO`) con fecha/hora/paciente/resultados.
- Se añade una fila a `data/history.csv` (solo **notas** por prueba).
- Se habilita el botón “Descargar PDF”:
  - `GET /report/pdf` o `GET /report/latest`.

---

## Endpoints HTTP (resumen)

### UI
- `GET /login` → pantalla de login
- `GET /` → panel usuario (requiere sesión)
- `GET /admin` → panel admin

### API
- `POST /api/login` → intenta login por cara (o modo `--no-login`)
- `POST /start` → inicia secuencia de pruebas (hilo background)
- `GET /status` → estado actual + registro (para polling del front)
- `POST /answer` → inyecta respuestas de Audición/Visión y desbloquea la secuencia
- `GET /report/pdf` → PDF de la última sesión
- `GET /report/latest` → alias de `/report/pdf`
- `POST /history/clear` → borra `history.csv` y `HISTORICO` (admin)
- `GET /admin/history` → tabla de sesiones (admin)
- `POST /admin/move` → mover TIAGo por preset o coordenadas (admin)
- `GET /whoami` → usuario en sesión
- `GET /logout` → cierra sesión
- `GET /ping` → healthcheck

---

## Panel admin (movilidad, cámara, RViz)

`templates/admin_index.html` incluye:
- **Histórico de sesiones** (en memoria) + botón “Limpiar”.
- **Movilidad**:
  - presets: `inicio`, `puerta`, `mesa`, `vision1`, `vision2`, `vision3`, `coordinacion`
  - coordenadas manuales `[x, y, oz, ow]`
- **Cámara frontal** (si existe `web_video_server`):
  - URL: `http(s)://<host>:8080/stream?topic=/xtion/rgb/image_raw...`
- **RViz remoto** (si existe noVNC en el host):
  - URL: `http(s)://<host>:6081/vnc.html?...`
- **Mapa 2D tipo RViz** (nav2djs) si existe `rosbridge_server`:
  - WebSocket por defecto: `ws://127.0.0.1:9090`
  - ⚠️ Si accedes desde otro PC, cambia esa IP en `static/js/admin.js`.

---

## Persistencia y datos

### CSV de notas (privado)
- Ruta: `src/web_server_pkg/data/history.csv`
- Se escribe al terminar una sesión.
- Columnas típicas:
  - `fecha`, `hora`, `paciente`
  - `memoria`, `reflejos`, `audicion`, `audicion_p1`, `audicion_p2`, `coordinacion`, `vision`

### Histórico en memoria
- `HISTORICO`: lista de sesiones completas (solo mientras el proceso corre).
- Por UI de usuario NO se expone `/history` (devuelve vacío a propósito).

---

## Notas importantes / “gotchas”

1) **Idioma del TTS**
- En el proyecto se usa `lang_id="es_ES"`, pero TIAGo puede tener solo inglés instalado.
- Comprueba idiomas con:
  ```bash
  rosparam get /tts/supported_languages
  ```
- Si no existe `es_ES`, o instalas el idioma o cambias `lang_id` en `app.py`.

2) **Movimiento post-login a mesa (fallback)**
- En `mover_robot_a_mesa_despues_login()` el fallback usa `PREPROGRAMMED_POINTS.get("medio")`.
- En el diccionario actual la clave correcta es `"mesa"` (no `"medio"`).
- Solución: cambiar `"medio"` → `"mesa"` para que el fallback funcione.

3) **Threading en Flask**
- La ejecución de pruebas corre en un hilo (`worker`) para no bloquear el servidor web.
- Las pruebas que requieren input usan `threading.Event` para pausar/reanudar la secuencia.

4) **Debug Flask**
- `app.py` arranca con `debug=True` y `use_reloader=False`.
- Para despliegue real, se recomienda un servidor WSGI (gunicorn) y `debug=False`.

---

## Uso típico en el bringup global

En el proyecto `psicotecnico`, este webserver suele lanzarse **el último** tras:
- roscore + navegación (map, move_base, /robot_pose)
- drivers cámara (Xtion) y `web_video_server` (si se usa stream)
- action servers de pruebas
- (opcional) rosbridge + noVNC (para panel admin)
