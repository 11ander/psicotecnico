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

try:
    while True:
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

            # Si el usuario presiona un botón incorrecto
            elif boton1.is_pressed and boton1 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 0.05 
                sleep(0.1) 
                zumbador.value = 0 
                prueba_terminada = True  # Termino la prueba por error

            elif boton2.is_pressed and boton2 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 0.05 
                sleep(0.1)  
                zumbador.value = 0  
                prueba_terminada = True  

            elif boton3.is_pressed and boton3 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 0.05  
                sleep(0.1)  
                zumbador.value = 0  
                prueba_terminada = True  

            # Si pasan más de 2 segundos sin presionar nada
            if tiempo_transcurrido > 2:
                print("¡Tiempo agotado! No presionaste el botón a tiempo.")
                zumbador.value = 0.05  
                sleep(0.1) 
                zumbador.value = 0  
                prueba_terminada = True  # Termina la prueba por tiempo agotado

        if prueba_terminada:
            print("Fin de la prueba.")
            break  # Sale del bucle principal y termina el juego

        sleep(0.3)  # Pausa entre rondas

except KeyboardInterrupt:
    print("\nJuego terminado.")
    for led in leds:
        led.off()
    zumbador.value = 0
