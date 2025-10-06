from gpiozero import LED, Button, PWMOutputDevice
from random import choice
from time import sleep, time

# Configuro los LEDs, pulsadores y zumbador
led1 = LED(5)
led2 = LED(16)
led3 = LED(18)

boton1 = Button(6)
boton2 = Button(17)
boton3 = Button(19)

zumbador = PWMOutputDevice(12)

leds = [led1, led2, led3]
botones = [boton1, boton2, boton3]
niveles = [2.5, 2, 1.5, 1.0, 0.8]  # Tiempos en segundos
dificultad = ["MUY FACIL", "FACIL", "INTERMEDIO", "DIFICIL", "MUY DIFICIL"]

def intro(nivel):
    print(f"PRESIONA PARA EMPEZAR NIVEL {nivel + 1}: {dificultad[nivel]}")
    while not (boton1.is_pressed or boton2.is_pressed or boton3.is_pressed):
        sleep(0.1)  # Espera mientras no se pulse ningún botón

    for i in range(3, 0, -1):  # Comienza la cuenta atrás con 3 pitidos
        print(f"{i}...") 
        zumbador.value = 1  
        sleep(0.5)  
        zumbador.value = 0  
        sleep(0.5) 

    print("¡YA!")  
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
        print(f"Presiona el botón asociado con el LED {idx_correcto + 1}!")

        tiempo_inicial = time()  # Marca el tiempo de inicio
        boton_presionado = False
        prueba_terminada = False  # Variable de control para terminar la prueba

        while not boton_presionado and not prueba_terminada:
            tiempo_transcurrido = time() - tiempo_inicial  
            # Si el usuario presiona el botón correcto
            if boton_correcto.is_pressed:
                print("¡Buen trabajo! Has presionado el botón correcto.")
                led_actual.off()
                boton_presionado = True  # Salgo del bucle para encender el siguiente LED
                intentos += 1  

            # Si el usuario presiona un botón incorrecto
            elif boton1.is_pressed and boton1 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 1
                sleep(2) 
                zumbador.value = 0 
                prueba_terminada = True  # Termino la prueba por error
                break  

            elif boton2.is_pressed and boton2 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 1
                sleep(2)  
                zumbador.value = 0  
                prueba_terminada = True  
                break  

            elif boton3.is_pressed and boton3 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 1
                sleep(2)  
                zumbador.value = 0  
                prueba_terminada = True  
                break 

            # Si pasa el tiempo limite sin haber pulsado nada -> eliminado
            if tiempo_transcurrido > tiempo:
                print("¡Tiempo agotado! No presionaste el botón a tiempo.")
                zumbador.value = 1
                sleep(2) 
                zumbador.value = 0  
                prueba_terminada = True  
                break  

        if prueba_terminada:
            print("Fin de la prueba.")
            return False  # Si falla en cualquier nivel, termina el juego

        sleep(0.3)  # Pausa entre rondas

    return True 

def test():
    try:
        for nivel in range(len(niveles)):
            intro(nivel)  # Repite la introducción antes de cada nivel para darle tiempo al usuario

            tiempo_limite = niveles[nivel]

            if not prueba(tiempo_limite):
                print(f"Has fallado en el nivel {nivel + 1}.")  
                break  
            print(f"¡Felicidades! Has superado el Nivel {nivel + 1}. \n")

        else:
            print("¡Felicidades! Has superado todos los niveles.")
            zumbador.value = 1  
            sleep(2)  
            zumbador.value = 0 
            print("FIN DE LA PRUEBA")  

    except KeyboardInterrupt:
        print("\nPrueba terminada.")
        for led in leds:
            led.off()
        zumbador.value = 0  

test()
