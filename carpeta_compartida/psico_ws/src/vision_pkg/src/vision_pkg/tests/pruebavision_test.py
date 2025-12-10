#!/usr/bin/env python3
from moverbrazotiago import main
import rospy
import actionlib
import time


def evaluarvision(cadena):

   
    CARTELDELTIAGO = "qwerty"  # cadena de referencia (8 caracteres)

    print(f"\nℹ️  Cadena de referencia: '{CARTELDELTIAGO}'")
    print("-" * 50)

    # Leer entrada del usuario
    puntuacion = 0

    # ✅ Tomar SOLO los primeros 8 caracteres
    input4carac = cadena[:6]

    # Si tiene menos de 8, puedes decidir qué hacer:
    if len(input4carac) < 6:
        
        # Opción: rellenar con espacios hasta 8
        input4carac = input4carac.ljust(6, '-')

    print(f"✅ Cadena procesada: '{input4carac}'")

    # Comparar letra por letra
    print("\n🔍 Comparando letra por letra...")
    match = True
    for i, (ref_char, user_char) in enumerate(zip(CARTELDELTIAGO, input4carac)):
        if ref_char == user_char:
            puntuacion += 1
            print(f"  Posición {i}: '{user_char}' ✅")
        else:
            print(f"  Posición {i}: esperado '{ref_char}', recibido '{user_char}' ❌")
            match = False
     
    
    CARTELDELTIAGO = "abcdef"  # cadena de referencia (8 caracteres)
    input4carac = cadena[6:12]

    # Si tiene menos de 8, puedes decidir qué hacer:
    if len(input4carac) < 6:
        
        # Opción: rellenar con espacios hasta 8
        input4carac = input4carac.ljust(6, '-')

    print(f"✅ Cadena procesada: '{input4carac}'")

    # Comparar letra por letra
    print("\n🔍 Comparando letra por letra...")
    match = True
    for i, (ref_char, user_char) in enumerate(zip(CARTELDELTIAGO, input4carac)):
        if ref_char == user_char:
            puntuacion += 1
            print(f"  Posición {i}: '{user_char}' ✅")
        else:
            print(f"  Posición {i}: esperado '{ref_char}', recibido '{user_char}' ❌")
            match = False
    return puntuacion
      
    
   
if __name__ == '__main__':
    puntuacion = evaluarvision("qwertyabcdef")
    print("Puntuacion",puntuacion/12*10)
    