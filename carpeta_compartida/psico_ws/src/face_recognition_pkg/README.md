# `face_recognition_pkg` — Login por reconocimiento facial (ROS)

Paquete ROS para **reconocimiento facial en tiempo real** usando **DeepFace (ArcFace)** y una base de datos ligera de **embeddings** (JSON).  
En el proyecto global *psicotecnico*, este paquete se utiliza como **módulo de login**: el *webserver* lanza un **goal** al action server, este reconoce al paciente y devuelve su **nombre** al backend.

---

## ¿Qué hace este paquete?

✅ **Reconoce a una persona** a partir del stream de cámara del TIAGo (ROS topic) o webcam (modo standalone).  
✅ Usa un flujo clásico: **detección → embedding → comparación por coseno → umbral → estabilización temporal**.  
✅ Devuelve el resultado vía **Action Server** (ROS): `Result.nombre` cuando la predicción es estable.

---

## Componentes principales

### 1) Action Server (ROS)
- **Archivo:** `recognize_action_server.py`
- **Action name:** `face_recognition_action`
- **Entrada (Goal):** `ejecutar: bool`
- **Salida (Result):** `nombre: string`
- **Feedback:** `estado: string` (mensajes de estado y votación)

**Optimización de rendimiento incluida:**
- *Worker thread* dedicado a inferencia DeepFace.
- *Buffer* de frame tamaño 1 (siempre procesa el frame más reciente).
- Inferencia limitada por tiempo (`DEEPFACE_INTERVAL_MS`) para evitar saturar CPU.
- Redimensionado para inferencia (`PROC_RESIZE_W`) manteniendo la vista previa fluida.
- Estabilización por mayoría en ventana deslizante (`STABILITY_FRAMES`).

### 2) Alta de usuarios (Enrollment)
- **Archivo:** `enroll_user.py`
- Guía al usuario por **4 poses** (frontal/izquierda/derecha/arriba).
- Captura varios frames por pose y elige el **más nítido** (varianza del Laplaciano).
- Calcula embeddings ArcFace por pose, hace la **media** y **normaliza**.
- Guarda/actualiza el usuario en `embeddings_db.json`.

### 3) Base de datos de embeddings
- **Archivo:** `embeddings_db.json`
- Formato:
  ```json
  {
    "users": [
      { "name": "Asier", "embedding": [0.12, -0.07, ...], "created_at": "..." }
    ]
  }
  ```

---

## Estructura del paquete

Dentro de `face_recognition_pkg/src/face_recognition_pkg/`:

- `recognize_action_server.py` → action server (principal en el sistema)
- `cliente_action_face.py` → cliente simple de prueba (envía goal y lee result)
- `enroll_user.py` → alta de usuarios (crea/actualiza `embeddings_db.json`)
- `recognize.py` / `recognize_ros.py` → scripts standalone de depuración
- `embeddings_db.json` → base de embeddings
- `requirements*.txt` → dependencias Python

Y en el paquete ROS:
- `launch/face_recognition_server.launch` → lanza el action server con `db_path`

---

## Requisitos

### ROS
- ROS Noetic (u otro ROS 1 compatible con `actionlib`) en el robot/PC.

### Python (DeepFace)
- `deepface`, `opencv-python`, `numpy`, y dependencias de backend (TensorFlow/Keras según entorno).
- En este repo se incluyen:
  - `requirements.txt`
  - `requirements_noetic_py38.txt` (recomendado si tu Python en ROS Noetic es 3.8)

> ⚠️ Nota: DeepFace puede tardar en “arrancar” la primera vez (carga de pesos).  
> El action server hace un **pre-warm** con un dummy frame para reducir el primer lag.

---

## Uso en el sistema completo (bringup)

En el proyecto global, el paquete se lanza al inicio (script `.sh` de bringup).  
Cuando llega un paciente y hace login, el **webserver** envía un goal al action server:

- Goal: `ejecutar=True`
- El server reconoce y responde con `Result.nombre`

---

## Ejecución (modo ROS / TIAGo)

### 1) Lanzar el action server
```bash
roslaunch face_recognition_pkg face_recognition_server.launch
```

El launch permite configurar el path de la base de datos:

```bash
roslaunch face_recognition_pkg face_recognition_server.launch \
  db_path:=package://face_recognition_pkg/src/face_recognition_pkg/embeddings_db.json
```

### 2) Probar con el cliente
```bash
rosrun face_recognition_pkg cliente_action_face.py
```

---

## Configuración rápida

En `recognize_action_server.py` (cabecera del archivo):

- `ROS_TOPIC = "/xtion/rgb/image_raw/compressed"`
- `ROS_COMPRESSED = True` (usa `sensor_msgs/CompressedImage`)
- `MODEL_NAME = "ArcFace"`
- `DETECTOR_BACKEND = "opencv"` (rápido) o `"mediapipe"` (más robusto con caras pequeñas)
- `COSINE_THRESHOLD = 0.35` (más bajo = más estricto)
- `STABILITY_FRAMES = 5` (ventana de votación por mayoría)
- `DEEPFACE_INTERVAL_MS = 120` (frecuencia de inferencia; sube si la CPU va justa)
- `PROC_RESIZE_W = 640` (ancho usado en inferencia)

> 🧠 Regla práctica:
> - Si hay **falsos positivos**, baja `COSINE_THRESHOLD` (p. ej. 0.30).
> - Si reconoce “a veces sí, a veces no”, sube `STABILITY_FRAMES` o mejora iluminación/alta.

---

## Alta de usuarios (Enrollment)

Ejecuta el script desde el directorio donde quieras que se cree/actualice el JSON:

```bash
python3 enroll_user.py
```

Recomendaciones:
- Buena **luz frontal** (evitar contraluz).
- Sin gafas de sol/mascarilla en el alta.
- Mantener la cara dentro del recuadro.

El script:
1. Pide el nombre
2. Captura 4 poses
3. Calcula la media normalizada del embedding
4. Guarda en `embeddings_db.json`

---

## Qué verás cuando funciona

- Ventana con overlay:
  - `Nombre` / `Desconocido`
  - `dist` (distancia coseno al mejor candidato)
  - `FPS` de visualización
- Logs ROS:
  - Cuando se estabiliza una predicción: feedback `"Votación estable: <nombre>"`
  - Cuando reconoce: `Result.nombre=<nombre>`

---

## Problemas comunes

**No detecta cara / reconoce “Desconocido” siempre**
- Revisa que el topic existe y publica imágenes:
  ```bash
  rostopic echo -n1 /xtion/rgb/image_raw/compressed
  ```
- Cambia `DETECTOR_BACKEND` a `mediapipe` si la cara es pequeña/lejana.
- Mejora iluminación y encuadre.
- Repite el enrollment con más nitidez.

**Va lento / CPU alta**
- Sube `DEEPFACE_INTERVAL_MS` (p. ej. 180–250 ms).
- Baja `PROC_RESIZE_W` (p. ej. 480).
- Desactiva UI (`ENABLE_UI = False`) si corres headless/Docker.

**Falsos positivos**
- Baja `COSINE_THRESHOLD`.
- Asegura que el alta se hizo en condiciones similares (luz/ángulo).

