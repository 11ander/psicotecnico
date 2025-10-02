from gpiozero import LED, Button, PWMOutputDevice
from random import choice
from time import sleep

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
        print(f"¡Presiona el botón asociado con el LED {idx_correcto + 1}!")

        boton_presionado = False

        while not boton_presionado:
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
                sleep(0.1) 
            elif boton2.is_pressed and boton2 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 0.05  
                sleep(0.1)  
                zumbador.value = 0  
                sleep(0.1)  
            elif boton3.is_pressed and boton3 != boton_correcto:
                print("¡Error! Botón incorrecto.")
                zumbador.value = 0.05  
                sleep(0.1)  
                zumbador.value = 0  
                sleep(0.1)  
        sleep(0.3)  # Pausa entre rondas

except KeyboardInterrupt:
    print("\nPrueba terminada.")
    for led in leds:
        led.off()
    zumbador.value = 0
