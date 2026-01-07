# checkpoint_follower.py

Nodo de **lógica de navegación** en Python.

Este script actúa como un "director de misión": contiene una lista predefinida de coordenadas (checkpoints) y se encarga de enviarlas una a una al sistema de navegación (`move_base`), verificando manualmente que el robot se mueva y llegue a su destino antes de enviar la siguiente.

---

## 1. Ubicación en el Paquete

Se encuentra en la carpeta `src/mover_pkg/` y debe tener permisos de ejecución.

```text
mover_pkg/
├── scripts/
│   ├── README.md
│   ├── run_all.sh               ← Script que lanza este nodo
│   └── run_rviz_web.sh
└── src/mover_pkg/
    ├── README.md
    ├── set_initial_pose.py      ← Script para que encuentre posicion inicial automaticamente
    └── checkpointfollower.py    ← ESTE ARCHIVO
```

---

## 2. Cómo funciona

A diferencia de un cliente de acción estándar, este nodo implementa su propia lógica de verificación basada en la posición real del robot:

  * Publica un objetivo (goal) en el topic de navegación.
  * Espera movimiento: Monitoriza la posición del robot (/robot_pose) hasta detectar que ha empezado a desplazarse.
  * Espera llegada: Sigue monitorizando hasta que el robot deja de moverse (velocidad cercana a 0 durante un tiempo), asumiendo que ha llegado al objetivo.
  * Siguiente punto: Repite el proceso con la siguiente coordenada de la lista.

---

## 3. Topics ROS
El nodo interactúa con la navegación a través de estos canales:
```
Tipo              Topic                    Mensaje                                              Descripción
Publica,    /move_base/goal    move_base_msgs/MoveBaseActionGoal           Envía la coordenada objetivo al planificador.
Suscribe      /robot_pose      geometry_msgs/PoseWithCovarianceStamped     Lee la posición actual para saber si el robot se mueve o está quieto.
```

---

## 4. Cómo editar los Puntos (Checkpoints)
Los checkpoints se definen como variables de la clase Follower, usando el formato: [Posición X, Posición Y, Orientación Z, Orientación W]. Ejemplo:
```Python
    # [   X,      Y,       oz,       ow   ]
    self.puerta = [1.80,  -0.72,   -0.17,    0.98]
    self.centro = [3.67,  -1.89,   -0.34,    0.93]
```
Para ejecutar el recorrido, al final del archivo (en el bloque if __name__ == "__main__":) se crea la lista de checkpoints y se envía al seguidor:
```Python
    follower = Follower()                      # Crea la clase
    checkpoints = [                            # Crea la lista de checkpoints
        follower.puerta,
        follower.centro
    ]
    follower.enviar_puntos(checkpoints)        # Envia los puntos para que se mueva a ellos
```
El robot recorrerá los puntos en el orden definido. 
