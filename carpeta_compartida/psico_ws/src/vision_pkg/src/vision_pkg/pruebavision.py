#!/usr/bin/env python3



def evaluarvision(cadena):

    CARTELDELTIAGO = "qwertyui"  # cadena de referencia (8 caracteres)
    
    print(f"\nℹ️  Cadena de referencia: '{CARTELDELTIAGO}'")
    print("-" * 50)

    # Leer entrada del usuario
    puntuacion = 0
    
    if len(cadena) < 8:
        print(f"⚠️  Advertencia: se recibieron solo {len(cadena)} caracteres. " f"Se rellenarán con espacios o se compararán solo los disponibles.")
    if len(cadena) > 8:
        print(f"⚠️  Advertencia: se recibieron mas de 8 caracteres, se eliminarán los sobrantes.")

    # ✅ Tomar SOLO los primeros 8 caracteres
    input8carac = cadena[:8]

    # Si tiene menos de 8, puedes decidir qué hacer:
    if len(input8carac) < 8:
        
        # Opción: rellenar con espacios hasta 8
        input8carac = input8carac.ljust(8, '-')

    print(f"✅ Cadena procesada: '{input8carac}'")

    # Comparar letra por letra
    print("\n🔍 Comparando letra por letra...")
    match = True
    for i, (ref_char, user_char) in enumerate(zip(CARTELDELTIAGO, input8carac)):
        if ref_char == user_char:
            puntuacion += 1
            print(f"  Posición {i}: '{user_char}' ✅")
        else:
            print(f"  Posición {i}: esperado '{ref_char}', recibido '{user_char}' ❌")
            match = False
    return puntuacion        




if __name__ == '__main__':
    puntuacionnivel1 = evaluarvision()
    print(f"\nPrimer nivel, puntuación = {puntuacionnivel1}/8")

    puntuacionnivel2 = evaluarvision()
    print(f"\nSegundo nivel, puntuación = {puntuacionnivel2}/8")

    puntuacionniveltotal = puntuacionnivel1 + puntuacionnivel2 
    mediapond = puntuacionniveltotal * 10 / 16
    print(f"\nNota final = {mediapond}")
