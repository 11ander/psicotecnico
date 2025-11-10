# Hito 2 – Diseño Conceptual del Sistema Robótico  
**Asignatura:** Robótica Aplicada a Servicios Biomédicos  
**Curso:** 2025–2026  
**Equipo:** <PSICOTECNICO>  
**Integrantes:**  
- Jon Camiruaga
- Daniel Gutierrez
- Ander Perez
- Asier Burgos

---

## 1. Resumen del problema biomédico
El proyecto busca crear un sistema robótico, utilizando el robot TIAGo, capaz de realizar una evaluación psicotécnica automatizada. El objetivo principal es medir las capacidades motrices y sensoriales clave de un individuo, centrándose en:

-Vista 

-Oído 

-Movimiento y coordinación

-Velocidad de reflejos 

-Memoria 


El sistema está pensado para un entorno clínico o de evaluación , similar a las pruebas necesarias para obtener el carnet de conducir.

El robot TIAGo actuará como el facilitador principal , usando su cámara y micrófono integrados para las pruebas de vista, oído y evaluación psicomotora (postura, movimientos). Paralelamente, una Raspberry Pi gestionará sensores complementarios (como pulsadores y LEDs) para evaluar los reflejos y la memoria.

El sistema guiará al paciente de forma autónoma a través de las pruebas , recogiendo y procesando los datos automáticamente para generar un informe de resultados. Esto busca ofrecer una evaluación precisa y eficiente, reduciendo el tiempo y los errores asociados a las pruebas manuales. Una restricción clave es que las pruebas de reflejos dependen de los sensores conectados a la Raspberry Pi, ya que TIAGo carece de ellos.

Justificacion del problema:

Aunque la robótica está avanzada en rehabilitación y asistencia , su uso para evaluaciones psicotécnicas es un campo emergente. El valor de este proyecto radica en la innovación de usar a TIAGo para una evaluación completa, autónoma y estandarizada.
El uso de un robot ofrece ventajas significativas:


-Precisión y Estandarización: Las pruebas automatizadas con TIAGo y la Raspberry Pi pueden ofrecer resultados más precisos y estandarizados que las realizadas por humanos.

-Reducción de Carga de Trabajo: El sistema reduce la carga del personal sanitario , permitiéndoles centrarse en otras tareas mientras el robot administra las pruebas.

-Eliminación de Errores: Se elimina la posibilidad de error humano, ya que el robot sigue un protocolo estándar. El registro automático de datos mejora la precisión de los informes.

-Mejora de la Experiencia del Paciente: La interacción con un robot puede ser menos estresante o incómoda para el paciente que la interacción con un evaluador humano , lo cual es relevante para personas con ansiedad o fobias sociales.


Requisitos Funcionales:


-Test de Reacción: El paciente deberá pulsar botones que se iluminan con LEDs en una secuencia aleatoria y cronometrada. La velocidad aumentará en niveles subsiguientes.

-Test de Memoria a Corto Plazo: El sistema mostrará una secuencia de LEDs que el paciente debe repetir en el orden exacto. La longitud de la secuencia aumentará para incrementar la dificultad.

-Pruebas de Vista y Oído: Presentar señales visuales (letras, símbolos) y emitir señales auditivas (pitidos).

-Evaluación de Postura y Movimiento: La cámara de TIAGo monitorizará la marcha del usuario para detectar desviaciones o cambios bruscos de postura.

-Interfaz Gráfica: Permitirá al usuario elegir las pruebas y ver los resultados.


Capacidades Técnicas:


-Robot: Se utilizará el robot TIAGo móvil, equipado con cámara, micrófono, altavoz y un brazo robótico.

-Hardware Adicional: Una Raspberry Pi 3B gestionará pulsadores, LEDs y un buzzer externos para las pruebas de reflejos y memoria.

-Software: Se usará ROS1 para el control del robot y la comunicación , con scripts en Python para gestionar los sensores. Se contempla el uso de librerías como MediaPipe para el seguimiento de la postura.

-Entorno: Las pruebas deben realizarse en un laboratorio con suelo plano, silencioso, bien iluminado y libre de obstáculos.


## 2. Arquitectura del sistema

### 2.a) Diagrama general del sistema

