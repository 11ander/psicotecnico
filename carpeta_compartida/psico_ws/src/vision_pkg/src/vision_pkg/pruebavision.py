#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lógica de evaluación de la prueba de visión.

Compara dos líneas leídas por el paciente con las líneas reales del cartel
y devuelve una nota de 0 a 10.
"""

CARTEL_LINEA1 = "qwerty"   # primera línea (posición intermedia)
CARTEL_LINEA2 = "abcdef"   # segunda línea (posición lejana)


def _normalizar(texto: str) -> str:
    """
    Normaliza el texto: minúsculas y sin espacios iniciales/finales.
    Si quieres, aquí puedes quitar tildes, espacios internos, etc.
    """
    if texto is None:
        return ""
    return texto.strip().lower()


def _puntuacion_linea(ref: str, leida: str) -> int:
    """
    Devuelve el número de caracteres correctos en la línea.
    Compara carácter a carácter hasta la longitud de la referencia.
    """
    ref = _normalizar(ref)
    leida = _normalizar(leida)

    # Recortamos o rellenamos la cadena leída a la longitud de ref
    if len(leida) < len(ref):
        leida = leida.ljust(len(ref), "-")
    else:
        leida = leida[:len(ref)]

    aciertos = 0
    for r, u in zip(ref, leida):
        if r == u:
            aciertos += 1
    return aciertos


def evaluar_vision(linea1: str, linea2: str) -> float:
    """
    Evalúa la prueba completa.

    :param linea1: texto que el examinador introduce como frase leída en la posición intermedia
    :param linea2: texto que el examinador introduce como frase leída en la posición lejana
    :return: nota de 0.0 a 10.0
    """
    aciertos1 = _puntuacion_linea(CARTEL_LINEA1, linea1)
    aciertos2 = _puntuacion_linea(CARTEL_LINEA2, linea2)

    total_caracteres = len(CARTEL_LINEA1) + len(CARTEL_LINEA2)
    total_aciertos = aciertos1 + aciertos2

    if total_caracteres == 0:
        return 0.0

    nota = 10.0 * (total_aciertos / float(total_caracteres))
    return round(nota, 2)


if __name__ == "__main__":
    # Pequeña prueba rápida
    l1 = "qwerty"
    l2 = "abcdef"
    print("Nota perfecta:", evaluar_vision(l1, l2))
