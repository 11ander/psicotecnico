from gpiozero import LED, Button, PWMOutputDevice
from random import choice
from time import sleep, time
from grove_rgb_lcd import setText

# Configuración de LEDs, botones y zumbador
led1 = LED(5)
led2 = LED(16)
led3 = LED(18)

boton1 = Button(6)
boton2 = Button(17)
boton3 = Button(19)

zumbador = PWMOutputDevice(12)

leds = [led1, led2, led3]
botones = [boton1, boton2, boton3]

LONGITUD_SECUENCIA = 4  # Por ahora 4 pasos, luego lo hare por niveles

def intro():
    setText("Pulsa un boton para empezar")
    while not (boton1.is_pressed or boton2.is_pressed or boton3.is_pressed):
        sleep(0.1)

    for i in range(3, 0, -1): 
        setText(f"{i}...") 
        zumbador.value = 1  
        sleep(0.5)  
        zumbador.value = 0  
        sleep(0.5) 
    
    setText("YA!")  
    zumbador.value = 1
    sleep(0.5)
    zumbador.value = 0

def mostrar_secuencia(secuencia):
    setText("Observa la\nsecuencia...")
    sleep(1)
    for i in secuencia:
        leds[i].on()
        sleep(0.6)
        leds[i].off()
        sleep(0.4)

def capturar_respuesta(n_pasos):
    setText("Tu turno:\nRepite secuencia")
    respuesta = []
    while len(respuesta) < n_pasos:
        pulsado = None
        while pulsado is None:  #Espero hasta que cualquier botón esté presionado
            for i, b in enumerate(botones):
                if b.is_pressed:
                    pulsado = i
                    leds[i].on()   
                    break
        while botones[pulsado].is_pressed:  #Mantengo LED encendido mientras esté pulsado
            sleep(0.01)

        leds[pulsado].off()
        respuesta.append(pulsado)

    return respuesta

def mostrar_resultado_lcd(secuencia, respuesta):
    a = ""
    for x in secuencia:
        a += str(x)

    b = ""
    for x in respuesta:
        b += str(x)

    linea1="Most:"+a
    linea2="Resp:"+b

    setText(linea1 + "\n" + linea2)

def prueba():
    try:
        secuencia = []
        for i in range(LONGITUD_SECUENCIA):
            secuencia.append(choice(range(len(leds)))) #Genero secuencia aleatoria
        
        mostrar_secuencia(secuencia)
        respuesta = capturar_respuesta(len(secuencia))

        if respuesta == secuencia:
            setText("Correcto!\nSecuencia OK")
            sleep(2)

        else:
            setText("Incorrecto!")
            zumbador.value = 1
            sleep(2)
            zumbador.value = 0   
            mostrar_resultado_lcd(secuencia, respuesta)   
            sleep(2)
      
        setText("Fin de la\nprueba")

    except KeyboardInterrupt:
        setText("Prueba\ninterrumpida")

intro()
prueba()
