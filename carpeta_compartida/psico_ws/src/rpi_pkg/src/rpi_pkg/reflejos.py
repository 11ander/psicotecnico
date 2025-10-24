from .grove_rgb_lcd import setText
from gpiozero import LED, Button, PWMOutputDevice
from random import choice
from time import sleep, time

# Configuro los LEDs, pulsadores y zumbador
led1 = LED(5)
led2 = LED(16)
led3 = LED(18)
led4 = LED(22)  
led5 = LED(24)   
led6 = LED(26)  

boton1 = Button(6)
boton2 = Button(17)
boton3 = Button(19)
boton4 = Button(23)  
boton5 = Button(25) 
boton6 = Button(27)  

zumbador = PWMOutputDevice(12)

leds = [led1, led2, led3, led4, led5, led6]
botones = [boton1, boton2, boton3, boton4, boton5, boton6]
niveles = [2.5, 2, 1.5, 1.0, 0.5]  # Tiempos en segundos
dificultad = ["MUY FACIL", "FACIL", "INTERMEDIO", "DIFICIL", "MUY DIFICIL"]

def intro(nivel):
    setText(f"PULSA PARA NIVEL{nivel + 1}: {dificultad[nivel]}")
    while not (boton1.is_pressed or boton2.is_pressed or boton3.is_pressed or
               boton4.is_pressed or boton5.is_pressed or boton6.is_pressed):
        sleep(0.1)  # Espera mientras no se pulse ningún botón

    for i in range(3, 0, -1):  # Comienza la cuenta atrás con 3 pitidos
        setText(f"{i}...")
        zumbador.value = 1
        sleep(0.5)
        zumbador.value = 0
        sleep(0.5)

    setText("YA!")
    zumbador.value = 1
    sleep(0.5)
    zumbador.value = 0

def prueba(tiempo):
    intentos = 0  # Contador de intentos exitosos
    while intentos < 12:  # El jugador debe presionar 12 veces correctamente
        led_actual = choice(leds)
        idx_correcto = leds.index(led_actual)
        boton_correcto = botones[idx_correcto]

        led_actual.on()
        setText("PULSA EL LED    ENCENDIDO!")

        tiempo_inicial = time()  # Marca el tiempo de inicio
        boton_presionado = False
        prueba_terminada = False  # Control para terminar la prueba

        while not boton_presionado and not prueba_terminada:
            tiempo_transcurrido = time() - tiempo_inicial

            # Si el usuario presiona el botón correcto
            if boton_correcto.is_pressed:
                led_actual.off()
                boton_presionado = True  # Salgo del bucle para encender el siguiente LED
                intentos += 1

            # Si el usuario presiona un botón incorrecto (extensión a 6 botones)
            elif boton1.is_pressed and boton1 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            elif boton2.is_pressed and boton2 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            elif boton3.is_pressed and boton3 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            elif boton4.is_pressed and boton4 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            elif boton5.is_pressed and boton5 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            elif boton6.is_pressed and boton6 != boton_correcto:
                setText("ERROR! TE HAS   EQUIVOCADO")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

            # Si pasa el tiempo límite sin haber pulsado nada -> eliminado
            if tiempo_transcurrido > tiempo:
                setText("TIEMPO AGOTADO  SIN PULSAR NADA!")
                zumbador.value = 1
                sleep(2)
                zumbador.value = 0
                prueba_terminada = True
                break

        if prueba_terminada:
            return False  # Si falla en cualquier nivel, termina el juego

        sleep(0.3)  # Pausa entre rondas

    return True

def test_reflejos():
    puntuacion = 0

    try:
        setText("PSICOTECNICO:   PRUEBA REFLEJOS ")
        sleep(3)
        for nivel in range(len(niveles)):
            intro(nivel)

            tiempo_limite = niveles[nivel]

            if not prueba(tiempo_limite):
                setText(f"Has fallado en  el nivel {nivel + 1}.")
                sleep(2)
                setText("FIN DE LA PRUEBA DE REFLEJOS")
                return puntuacion
            else:
                setText(f"Bien hecho Nivel {nivel + 1} completado \n")
                sleep(2)
                puntuacion += 2

        else:
            setText("Superaste todos los niveles!")
            zumbador.value = 1
            sleep(2)
            zumbador.value = 0
            setText("FIN DE LA PRUEBA DE REFLEJOS")
            return puntuacion

    except KeyboardInterrupt:
        setText("\nPrueba terminada.")
        for led in leds:
            led.off()
        zumbador.value = 0
        return puntuacion

if __name__ == "__main__":
    nota = test_reflejos()
    print(nota)
