"""
Genera el reporte de ventas del mes en PDF con el logo de Píldoras de Programación.
El logo se toma de assets/logo_pildoras.png; si no existe, el PDF sale igual pero sin logo.
"""

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

LOGO = os.path.join("assets", "logo_pildoras.png")
VERDE = colors.HexColor("#00CC5F")
OSCURO = colors.HexColor("#0A0E1A")
GRIS = colors.HexColor("#64748B")


def generar_pdf(ventas: list[dict], ruta: str) -> None:
    """ventas: lista de dicts con fecha, cliente, curso, monto."""
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    doc = SimpleDocTemplate(ruta, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=estilos["Title"], textColor=OSCURO, fontSize=20,
                            alignment=0, spaceAfter=2)
    sub = ParagraphStyle("s", parent=estilos["Normal"], textColor=GRIS, fontSize=10)
    normal = ParagraphStyle("n", parent=estilos["Normal"], fontSize=11, leading=15)

    partes = []
    if os.path.exists(LOGO):
        partes.append(Image(LOGO, width=48 * mm, height=48 * mm, kind="proportional"))
        partes.append(Spacer(1, 4 * mm))
    partes.append(Paragraph("Reporte de ventas del mes", titulo))
    partes.append(Paragraph(f"Píldoras de Programación · generado el {date.today():%d/%m/%Y} por Pildorín", sub))
    partes.append(Spacer(1, 8 * mm))

    total = sum(v["monto"] for v in ventas)
    partes.append(Paragraph(f"Este mes se registraron <b>{len(ventas)} ventas</b> por un total de <b>{total:.0f} USD</b>.", normal))
    partes.append(Spacer(1, 6 * mm))

    datos = [["Fecha", "Cliente", "Curso", "Monto (USD)"]]
    for v in ventas:
        datos.append([v["fecha"], v["cliente"], v["curso"], f"{v['monto']:.0f}"])
    datos.append(["", "", "Total", f"{total:.0f}"])

    tabla = Table(datos, colWidths=[28 * mm, 40 * mm, 78 * mm, 28 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), OSCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F3F6F4")]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, VERDE),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, VERDE),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    partes.append(tabla)
    partes.append(Spacer(1, 10 * mm))
    partes.append(Paragraph("pildorasdeprogramacion.com", sub))
    doc.build(partes)
    print(f"    <- PDF listo: {ruta}")
