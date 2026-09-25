# -*- coding: utf-8 -*-
"""Report PDF delle dosate da Vecchia.csv (riusa la logica di genera_report_vecchia.py)."""
import os, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("gv", os.path.join(HERE, "genera_report_vecchia.py"))
gv = importlib.util.module_from_spec(spec); spec.loader.exec_module(gv)

rows, piv, OUT, TAG = gv.rows, gv.piv, gv.OUT, gv.TAG

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak)
from PIL import Image as PILImage

A4L = landscape(A4)
styles = getSampleStyleSheet()
h1 = ParagraphStyle("h1it", parent=styles["Heading1"], fontSize=16, leading=20)
h2 = ParagraphStyle("h2it", parent=styles["Heading2"], fontSize=13, leading=16)
body = ParagraphStyle("bodyit", parent=styles["Normal"], fontSize=9.5, leading=13)

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(15*mm, 8*mm, "Report Dosate — generato da Vecchia.csv")
    canvas.drawRightString(A4L[0]-15*mm, 8*mm, f"Pagina {doc.page}")
    canvas.restoreState()

pdf_path = os.path.join(OUT, "report_vecchia.pdf")
doc = SimpleDocTemplate(pdf_path, pagesize=A4L, leftMargin=15*mm, rightMargin=15*mm,
                        topMargin=14*mm, bottomMargin=14*mm,
                        title="Report Dosate Vecchia", author="Analisi Vecchia.csv")
story = [Paragraph("Report Dosate — file <b>Vecchia.csv</b>", h1), Spacer(1, 4*mm),
         Paragraph("<b>Segmentazione:</b> inizio dosata alla riga col bit DosaggioInCorso=0, "
                   "fine alla riga successiva; l'inizio dei grafici corrisponde al "
                   "<b>primo dato di pesa dopo il bit di start</b>.", body),
         Paragraph(f"<b>Intervallo dati:</b> {piv.index.min():%d/%m/%Y %H:%M:%S} → "
                   f"{piv.index.max():%d/%m/%Y %H:%M:%S}", body),
         Paragraph(f"<b>Numero dosate rilevate:</b> {len(rows)}", body), Spacer(1, 5*mm)]

head = ["#", "Riga bit=0", "Inizio grafico (1° dato)", "Fine", "Durata [s]",
        "Pesa inizio [g]", "Pesa max [g]", "Dosato [g]", "Δ Tlm_Dos8 [g]",
        "Vel. media [g/s]", "Punti"]
data = [head] + [[str(r["n"]), f"{r['tbit']:%H:%M:%S}", f"{r['t0']:%H:%M:%S}",
                  f"{r['t1']:%H:%M:%S}", f"{r['durata']:.0f}", f"{r['start_bil']:.1f}",
                  f"{r['max_bil']:.1f}", f"{r['dosato']:.1f}", f"{r['delta_dos8']:.1f}",
                  f"{r['vel']:.1f}", str(r["npunti"])] for r in rows]
tbl = Table(data, colWidths=[8*mm, 20*mm, 27*mm, 20*mm, 18*mm, 24*mm, 22*mm,
                             20*mm, 24*mm, 24*mm, 14*mm], repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2c3e50")),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 8.5),
    ("ALIGN", (1,1), (-1,-1), "RIGHT"), ("ALIGN", (0,0), (0,-1), "CENTER"),
    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#eef2f6")]),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
story.append(tbl)

max_w = A4L[0] - 30*mm
for r in rows:
    story.append(PageBreak())
    story.append(Paragraph(f"Dosata #{r['n']} — bit alle {r['tbit']:%H:%M:%S}, "
                           f"grafico dal {r['t0']:%H:%M:%S} al {r['t1']:%H:%M:%S}", h2))
    story.append(Paragraph(
        f"Durata: <b>{r['durata']:.0f} s</b> &nbsp;|&nbsp; Pesa inizio: <b>{r['start_bil']:.1f} g</b> "
        f"&nbsp;|&nbsp; Pesa max: <b>{r['max_bil']:.1f} g</b> &nbsp;|&nbsp; Dosato: <b>{r['dosato']:.1f} g</b> "
        f"&nbsp;|&nbsp; Δ Tlm_Dos8: <b>{r['delta_dos8']:.1f} g</b> &nbsp;|&nbsp; "
        f"Velocità media: <b>{r['vel']:.1f} g/s</b> &nbsp;|&nbsp; Punti: <b>{r['npunti']}</b>", body))
    story.append(Spacer(1, 3*mm))
    png = os.path.join(OUT, f"{TAG}_{r['n']:02d}.png")
    iw, ih = PILImage.open(png).size
    w = max_w; h = w*ih/iw; max_h = A4L[1] - 60*mm
    if h > max_h: h = max_h; w = h*iw/ih
    story.append(Image(png, width=w, height=h))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(f"PDF generato: {pdf_path} ({os.path.getsize(pdf_path)/1024:.0f} kB, {len(rows)+1} pagine)")
