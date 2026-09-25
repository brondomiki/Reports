# -*- coding: utf-8 -*-
"""
Genera il report PDF delle dosate a partire da Dosate0.csv, riusando la
logica di segmentazione e i grafici già prodotti da genera_report_dosate.py.

Output: /workspace/report/report_dosate.pdf
  - Pagina 1: riepilogo (info file, modalità segmentazione, tabella dosate)
  - Una pagina per ogni dosata con il suo grafico e i dettagli
"""
import os
import importlib.util

# --- carico il modulo del report esistente senza eseguire print finali ---
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(HERE, "genera_report_dosate.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

rows = gen.rows
piv = gen.piv
mode = gen.mode
OUT = gen.OUT

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak)
from reportlab.lib.enums import TA_CENTER

A4L = landscape(A4)  # 297 x 210 mm — meglio per i grafici larghi

styles = getSampleStyleSheet()
h1 = ParagraphStyle("h1it", parent=styles["Heading1"], fontSize=16, leading=20)
h2 = ParagraphStyle("h2it", parent=styles["Heading2"], fontSize=13, leading=16)
body = ParagraphStyle("bodyit", parent=styles["Normal"], fontSize=9.5, leading=13)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(15 * mm, 8 * mm,
                      "Report Dosate — generato da Dosate0.csv")
    canvas.drawRightString(A4L[0] - 15 * mm, 8 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


pdf_path = os.path.join(OUT, "report_dosate.pdf")
doc = SimpleDocTemplate(pdf_path, pagesize=A4L,
                        leftMargin=15 * mm, rightMargin=15 * mm,
                        topMargin=14 * mm, bottomMargin=14 * mm,
                        title="Report Dosate", author="Analisi Dosate0")

story = []
story.append(h1 and Paragraph("Report Dosate — file <b>Dosate0.csv</b>", h1))
story.append(Spacer(1, 4 * mm))
story.append(Paragraph(f"<b>Segmentazione dosate:</b> {mode}", body))
story.append(Paragraph(
    f"<b>Intervallo dati:</b> {piv.index.min():%d/%m/%Y %H:%M:%S} → "
    f"{piv.index.max():%d/%m/%Y %H:%M:%S}", body))
story.append(Paragraph(f"<b>Numero dosate rilevate:</b> {len(rows)}", body))
story.append(Spacer(1, 5 * mm))

# ---------- tabella riepilogativa ----------
head = ["#", "Inizio (riga bit=0)", "Fine (riga succ.)", "Durata [s]", "Pesa inizio [g]",
        "Pesa fine dosata [g]", "Dosato [g]", "Δ Tlm_Dos8 [g]",
        "Velocità media [g/s]", "Punti"]
data = [head]
for r in rows:
    data.append([
        str(r["n"]), f"{r['t0']:%H:%M:%S}", f"{r['t1']:%H:%M:%S}",
        f"{r['durata']:.0f}", f"{r['start_bil']:.1f}", f"{r['max_bil']:.1f}",
        f"{r['dosato']:.1f}", f"{r['delta_dos8']:.1f}",
        f"{r['vel']:.1f}", str(r["npunti"])])

tbl = Table(data, colWidths=[10*mm, 22*mm, 22*mm, 20*mm, 26*mm, 28*mm,
                             22*mm, 26*mm, 30*mm, 16*mm], repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
     [colors.white, colors.HexColor("#eef2f6")]),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(tbl)

# ---------- una pagina per dosata ----------
max_w = A4L[0] - 30 * mm
for r in rows:
    story.append(PageBreak())
    story.append(Paragraph(
        f"Dosata #{r['n']} — dal {r['t0']:%d/%m/%Y %H:%M:%S} "
        f"al {r['t1']:%d/%m/%Y %H:%M:%S}", h2))
    story.append(Paragraph(
        f"Durata: <b>{r['durata']:.0f} s</b> &nbsp;|&nbsp; "
        f"Pesa a inizio dosata: <b>{r['start_bil']:.1f} g</b> &nbsp;|&nbsp; "
        f"Pesa massima: <b>{r['max_bil']:.1f} g</b> &nbsp;|&nbsp; "
        f"Dosato: <b>{r['dosato']:.1f} g</b> &nbsp;|&nbsp; "
        f"Variazione contatore Tlm_Dos8_Eu: <b>{r['delta_dos8']:.1f} g</b> "
        f"&nbsp;|&nbsp; Velocità media: <b>{r['vel']:.1f} g/s</b> "
        f"&nbsp;|&nbsp; Punti: <b>{r['npunti']}</b>", body))
    story.append(Spacer(1, 3 * mm))
    png = os.path.join(OUT, f"dosata_{r['n']:02d}.png")
    from PIL import Image as PILImage
    iw, ih = PILImage.open(png).size
    w = max_w
    h = w * ih / iw
    max_h = A4L[1] - 60 * mm
    if h > max_h:
        h = max_h
        w = h * iw / ih
    story.append(Image(png, width=w, height=h))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(f"PDF generato: {pdf_path}  ({os.path.getsize(pdf_path)/1024:.0f} kB, "
      f"{len(rows)+1} pagine)")
