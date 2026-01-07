# `coordinacion_pkg` — Evaluación de coordinación de la marcha (ROS)

Paquete ROS para **evaluar coordinación y estabilidad de la marcha** en tiempo real usando **MediaPipe Pose** sobre el stream de cámara frontal del TIAGo (por defecto la **Xtion**).  
En el proyecto global *psicotecnico*, este paquete se usa como una **prueba de coordinación/movilidad**: bajo demanda (goal ROS), analiza **30 segundos válidos** y devuelve una **nota 0–100**, un **informe textual** y un **CSV** con métricas.

---

## ¿Qué hace este paquete?

✅ Detecta pose corporal (*landmarks*) con **MediaPipe Pose**.  
✅ Controla la calidad del encuadre (persona demasiado lejos/cerca/parcial) y **solo puntúa cuando el encuadre es válido**.  
✅ Calcula métricas **explicables** (no “caja negra”) sobre tronco, trayectoria y simetría de marcha.  
✅ Devuelve el resultado vía **Action Server** (ROS) y genera ficheros:
- `..._metrics.csv` (métricas por segundo)
- `..._report.txt` (informe legible)

---

## Arquitectura (alto nivel)

### Fuente de vídeo (ROS1)
- Se suscribe a un topic de imagen (por defecto):
  - `/xtion/rgb/image_raw/compressed`
- Decodifica JPEG con OpenCV.
- Mantiene **solo el último frame** (baja latencia y evita colas largas).

### Action Server (actionlib)
- Nodo: `mobility_exam_action_server.py`
- Action name: `mobility_exam_action`
- Se queda a la espera hasta recibir `goal.ejecutar=True`.

### Percepción (MediaPipe Pose)
- Extrae landmarks principales: nariz, hombros, caderas, tobillos.
- Exige visibilidad mínima por landmark (`MIN_VIS`).

### Control de calidad del encuadre
- Calcula el tamaño relativo de la persona en pantalla:
  - `person_frac = alto_bbox / alto_imagen`
- Solo acumula “tiempo válido” si:
  - `MIN_PERSON_FRAC <= person_frac <= MAX_PERSON_FRAC`
- Si no se cumple: **pausa el cómputo** y pide reencuadre (“acércate / aléjate”).

### Ventanas deslizantes y métricas
- Ventanas temporales para suavizar ruido y estimar tendencias:
  - métricas típicamente en ventanas de `WIN_SECS`
- Resultado final:
  - media de métricas durante el tiempo válido
  - score ponderado (0–100)

---

## Métricas calculadas

> Todas son heurísticas interpretables; lo único “model-based” es el detector de pose (MediaPipe).

### 1) Inclinación lateral del tronco (`tronco_lat_deg`)
Ángulo 2D del vector caderas→hombros respecto a la vertical (valor absoluto).

- Bueno ≤ 4°
- Malo  ≥ 20°

### 2) Flexión anterior / pitch del tronco (`tronco_pitch_deg`)
Aproximación de flexión usando componente Z relativa de MediaPipe.

- Bueno ≤ 4°
- Malo  ≥ 20°

### 3) Zigzag / serpenteo (`zigzag_std`)
Desviación típica de la trayectoria lateral del centro de caderas, normalizada en su bbox.

Para no mezclar efectos de distancia, el sistema segmenta por dirección:
- `acerca` / `aleja` / `estable` (según historial de `person_frac`)

- Bueno ≤ 0.01
- Malo  ≥ 0.08

### 4) Asimetría de paso — amplitud (`asim_amp`)
Detecta picos en la señal vertical de tobillos y compara amplitudes medias.

Índice: `|A_L − A_R| / mean(A_L, A_R)`

- Bueno ≤ 0.10
- Malo  ≥ 0.60

### 5) Asimetría temporal (`asim_t`)
Compara periodos medios entre picos de tobillo izquierdo y derecho.

Índice: `|T_L − T_R| / mean(T_L, T_R)`

- Bueno ≤ 0.10
- Malo  ≥ 0.60

---

## Score final (0–100)

Cada métrica se mapea a un score en `[0, 1]` con:

`score_from_range(valor, bueno, malo)`  
(1 si está en rango bueno, 0 si está en rango malo)

Ponderaciones actuales:
```text
total = 100 * (
   0.25 * s_tronco_lat   +
   0.15 * s_tronco_pitch +
   0.30 * s_zigzag       +
   0.15 * s_cojera_amp   +
   0.15 * s_cojera_time
)
```

> Nota: umbrales y pesos son **orientativos** y pueden calibrarse con datos reales.

---

## Qué devuelve / qué guarda

### Action Result (`MobilityExamResult`)
- `score` (float): nota final 0–100
- `informe` (list[str]): frases interpretables (alineación, zigzag, asimetrías + recomendaciones)
- `csv_path` (string): ruta al CSV de métricas
- `report_path` (string): ruta al informe TXT

### CSV por segundo (`..._metrics.csv`)
Cabecera:
```csv
timestamp,valid_elapsed_s,person_frac,dir,score_total,tronco_lat_deg,tronco_pitch_deg,zigzag_std,asim_amp,asim_t
```

### Informe TXT (`..._report.txt`)
Incluye:
- Nota y nivel (“ÓPTIMO/APTO/LIMITADO/NO APTO orientativo”)
- Interpretación por métrica
- Recomendaciones orientativas
- Aviso de no-diagnóstico médico

---

## Estructura del paquete

En `coordinacion_pkg/src/coordinacion_pkg/`:

- `mobility_exam_action_server.py` → action server (principal en el sistema)
- `cliente_action_mobility.py` → cliente simple de prueba
- `mobility_exam.py` / `mobility_exam_30s.py` → scripts de depuración/ejecución local
- `holistic_cam.py` / `holistic_ros_cam.py` → utilidades de cámara/ROS (debug)
- `speak_api.py` → utilidades TTS (si aplica en integración)
- `pruebas/` → pruebas internas
- Outputs de ejemplo (según ejecución):
  - `mobility_metrics_*.csv`
  - `mobility_report_*.txt`

---

## Requisitos

- ROS Noetic (ROS1) + `actionlib`
- Python 3 (según tu entorno ROS)
- Dependencias:
  - `opencv-python`
  - `numpy`
  - `mediapipe`

> Si tu entorno ROS usa Python 3.8 (típico en Noetic), instala dependencias en ese Python.

---

## Uso en el sistema completo (bringup)

En el proyecto *psicotecnico*, este paquete se lanza al inicio (script `.sh` de bringup + roslaunch).  
Luego, el webserver (u otro nodo) envía un **goal** para iniciar la prueba.

---

## Ejecución (ROS / TIAGo)

### 1) Lanzar el action server
Si tienes un `launch` (recomendado), ejecútalo así:

```bash
roslaunch coordinacion_pkg <tu_launch>.launch
```

> En este paquete, el servidor expone parámetros ROS (ver sección siguiente).  
> Si no tienes launch, puedes ejecutar directamente:

```bash
rosrun coordinacion_pkg mobility_exam_action_server.py
```

### 2) Probar con el cliente
```bash
rosrun coordinacion_pkg cliente_action_mobility.py
```

---

## Parámetros ROS importantes

Configurables vía `rosparam` o `roslaunch`:

- `~topic` (string): topic de imagen (default `/xtion/rgb/image_raw/compressed`)
- `~compressed` (bool): `True` si el topic es `sensor_msgs/CompressedImage`
- `~queue_size` (int): cola ROS (default 5)
- `~complexity` (int): complejidad de MediaPipe Pose (`0/1/2`)  
  - más alto = más preciso, más coste
- `~enable_ui` (bool): muestra ventana OpenCV de depuración
- `~mirror_view` (bool): espejo (útil para encuadre)
- `~out_dir` (string): carpeta destino para `CSV` y `TXT` (si está vacía, escribe en `./`)

Ejemplo de ejecución con parámetros:
```bash
rosrun coordinacion_pkg mobility_exam_action_server.py \
  _topic:=/xtion/rgb/image_raw/compressed \
  _compressed:=true \
  _complexity:=1 \
  _enable_ui:=true \
  _out_dir:=/tmp/mobility_results
```

---

## Cliente de ejemplo (Python)

```python
import rospy
import actionlib
from coordinacion_pkg.msg import MobilityExamAction, MobilityExamGoal

rospy.init_node("mobility_client_test")
client = actionlib.SimpleActionClient("mobility_exam_action", MobilityExamAction)
client.wait_for_server()

goal = MobilityExamGoal(ejecutar=True)
client.send_goal(goal)
client.wait_for_result()

res = client.get_result()
print("Score:", res.score)
print("Informe:", list(res.informe))
print("CSV:", res.csv_path)
print("TXT:", res.report_path)
```

---

## Qué verás durante la prueba (feedback/UI)

Durante la ejecución, el servidor publica `MobilityExamFeedback` con:
- `estado` (string): “Buscando persona…”, “Muy lejos/cerca (pausa)”, “Analizando (acerca/aleja/estable)”
- `valid_elapsed` (float): segundos válidos acumulados

Si `enable_ui=True`:
- Ventana OpenCV con:
  - “stickman” (pose)
  - estado actual
  - contador de tiempo válido: `xx.x / 30.0 s`

---

## Problemas comunes

**No detecta a la persona / landmarks inestables**
- Asegura buena iluminación y que la persona esté completa en encuadre.
- Ajusta `~complexity` a 1 o 2 si la detección falla.
- Comprueba que el topic de imagen existe:
  ```bash
  rostopic list | grep xtion
  ```

**No acumula tiempo válido**
- El sistema pausa si la persona está muy lejos o muy cerca (person_frac fuera de rango).
- Sigue los mensajes “acércate / aléjate” hasta entrar en rango.

**Va lento**
- Baja `~complexity` (0 o 1).
- Desactiva la UI (`~enable_ui:=false`) para headless.
- Reduce resolución del stream si tu pipeline lo permite.

---

## Decisiones de diseño (por qué así)

- **Último frame + cola pequeña:** minimiza latencia (se procesa siempre lo más reciente).
- **30 s válidos (no 30 s “reloj”):** evita penalizar por pérdidas de encuadre; la medición es más justa.
- **Heurísticas transparentes:** todas las métricas, umbrales y pesos son ajustables y explicables.

