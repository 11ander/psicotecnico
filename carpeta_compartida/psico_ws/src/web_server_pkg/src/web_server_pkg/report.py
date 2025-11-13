#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generación de informe PDF de la última sesión.
- Parche FIPS-safe para md5 de ReportLab (sin pasar 'usedforsecurity').
- Logo arriba a la derecha.
- Solo muestra NOTAS (Audición incluye Nota P1, Nota P2 y Nota final).
"""

import io
import os
import hashlib

# --- Parche robusto de compatibilidad md5 para ReportLab (FIPS / Py3.8) ---
#   * NUNCA pasamos 'usedforsecurity' a hashlib.md5
#   * Aceptamos 0/1 argumentos y cualquier **kwargs, ignorándolos.
try:
    from reportlab.pdfbase import pdfdoc as _rl_pdfdoc
    from reportlab.lib import utils as _rl_utils

    def _md5_no_fips(*args, **kwargs):
        # ReportLab puede llamar:
        #   md5()                              -> sin datos
        #   md5(data)                          -> con bytes/str
        #   md5(data, usedforsecurity=False)   -> con kw extra
        #   md5(usedforsecurity=False)         -> sin datos pero con kw
        data = b""
        if args:
            a0 = args[0]
            if isinstance(a0, (bytes, bytearray)):
                data = bytes(a0)
            else:
                # Convertimos a bytes por si llega str u otro tipo
                data = str(a0).encode("utf-8", errors="ignore")
        return hashlib.md5(data)

    # Parchamos los puntos que usa ReportLab internamente
    _rl_pdfdoc.md5 = _md5_no_fips
    # Algunas versiones también usan utils.md5
    try:
        _rl_utils.md5 = _md5_no_fips  # no falla si no existe
    except Exception:
        pass
except Exception:
    # Si no podemos parchear, seguimos: en la mayoría de entornos no hará falta
    pass


# --- ReportLab ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
)

STYLES = getSampleStyleSheet()
TITLE = ParagraphStyle(
    'TITLE', parent=STYLES['Heading1'], fontSize=16, leading=20, spaceAfter=8
)
H2 = ParagraphStyle(
    'H2', parent=STYLES['Heading2'], fontSize=12, leading=16, spaceBefore=10, spaceAfter=6
)
BODY = ParagraphStyle(
    'BODY', parent=STYLES['BodyText'], fontSize=10, leading=14, spaceAfter=4
)
SMALL = ParagraphStyle(
    'SMALL', parent=STYLES['BodyText'], fontSize=8, leading=11, textColor=colors.grey
)

def _nota_text(n):
    return "—" if n is None else str(n)

def _fila(k, v):
    return [Paragraph(f"<b>{k}</b>", BODY), Paragraph(v, BODY)]

def build_pdf_bytes(sesion: dict, logo_path: str = "") -> bytes:
    """
    sesion = {
      "fecha": "YYYY-MM-DD",
      "hora": "HH:MM:SS",
      "paciente": {"nombre": "..."},
      "pruebas": [
        {"prueba": "memoria", "puntuacion": 8.5, "hora": "12:34:56"},
        {"prueba": "audicion", "puntuacion": 7.2, "hora": "...",
         "detalles": {"nota_p1": 8.0, "nota_p2": 6.5} }
      ]
    }
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm
    )

    story = []

    # Cabecera con logo a la derecha
    left = Paragraph("<b>Informe de Pruebas Psicotécnicas</b>", TITLE)
    if logo_path and os.path.isfile(logo_path):
        img = Image(logo_path, width=28*mm, height=28*mm, hAlign='RIGHT')
        t = Table([[left, img]], colWidths=[None, 30*mm])
        t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(t)
    else:
        story.append(left)

    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#0b5ed7")))
    story.append(Spacer(1, 6))

    # Datos de sesión
    fecha = sesion.get("fecha", "")
    hora  = sesion.get("hora", "")
    paciente = sesion.get("paciente", {}) or {}
    nombre = paciente.get("nombre") or paciente.get("apellidos") or paciente.get("id") or "—"

    meta = Table([
        _fila("Fecha", fecha),
        _fila("Hora", hora),
        _fila("Paciente", nombre),
    ], colWidths=[35*mm, None])
    meta.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta)
    story.append(Spacer(1, 8))

    # Resultados por prueba (SOLO NOTAS)
    story.append(Paragraph("Resultados", H2))

    filas = []
    for p in sesion.get("pruebas", []):
        pkey = (p.get("prueba") or "").lower()
        pname = pkey.capitalize()
        pnota = p.get("puntuacion", None)

        if pkey == "audicion":
            d = p.get("detalles", {}) or {}
            nota_p1 = d.get("nota_p1", None)
            nota_p2 = d.get("nota_p2", None)
            filas.append([
                Paragraph(f"<b>{pname}</b>", BODY),
                Paragraph(
                    f"Nota P1: {_nota_text(nota_p1)} /10<br/>"
                    f"Nota P2: {_nota_text(nota_p2)} /10<br/>"
                    f"<b>Nota final:</b> {_nota_text(pnota)} /10",
                    BODY
                )
            ])
        else:
            filas.append([
                Paragraph(f"<b>{pname}</b>", BODY),
                Paragraph(f"<b>Nota:</b> {_nota_text(pnota)} /10", BODY)
            ])

    if not filas:
        filas = [[Paragraph("<i>Sin resultados</i>", BODY), Paragraph("", BODY)]]

    tbl = Table(filas, colWidths=[45*mm, None], hAlign='LEFT')
    tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.whitesmoke, colors.white]),
        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Este informe es informativo y no sustituye a la valoración final del profesional.",
        SMALL
    ))

    doc.build(story)
    return buf.getvalue()
