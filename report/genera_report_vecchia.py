# -*- coding: utf-8 -*-
"""
Report + grafico per ogni dosata contenuta in Vecchia.csv.

Regola di segmentazione (specifica utente):
  - Ogni riga con il bit Bil21_Wrk_DosaggioInCorso = 0 segna l'inizio di una
    dosata; la dosata termina alla riga successiva (fase attiva della pesata).
  - L'INIZIO DEL GRAFICO corrisponde al PRIMO DATO DI PESA successivo alla
    riga del bit (nessun tratto vuoto/morto all'inizio dei grafici).
Uso: python3 genera_report_vecchia.py [csv] [dir_output]
"""
import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV = sys.argv[1] if len(sys.argv) > 1 else "/workspace/Vecchia.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/workspace/report"
os.makedirs(OUT, exist_ok=True)
TAG = "vecchia"

BIT = "Bil21_Wrk_DosaggioInCorso"
BIL = "Tlm_Bil21_Eu"
DOS = "Tlm_Dos8_Eu"
SET = "HMI<->PLC_Real{0}"

df = pd.read_csv(CSV, sep=";", decimal=",")
df["TimeString"] = pd.to_datetime(df["TimeString"], dayfirst=True,
                                  format="%d/%m/%Y %H:%M:%S")
piv = df.pivot_table(index="TimeString", columns="VarName",
                     values="VarValue", aggfunc="last").sort_index()
keys = list(piv.index)
setpoint = float(piv[SET].dropna().iloc[-1]) if SET in piv and piv[SET].notna().any() else None

# ---------- eventi del bit DosaggioInCorso = 0 ----------
bit_series = piv[BIT]
zero_idx = [i for i, t in enumerate(keys)
            if pd.notna(bit_series.get(t)) and bit_series.loc[t] < 0.5]

bil_all = piv[BIL]
segs = []
for j, i in enumerate(zero_idx):
    # fine: riga successiva al bit, estesa fino alla riga prima del bit=0
    # seguente se nel mezzo c'e' la fase attiva della pesata
    if j + 1 < len(zero_idx):
        end_i = max(i + 1, zero_idx[j + 1] - 1)
    else:
        end_i = min(i + 1, len(keys) - 1)
    # INIZIO GRAFICO: il primo dato di pesa DOPO la riga del bit
    start_i = i + 1
    while start_i <= end_i and pd.isna(bil_all.get(keys[start_i])):
        start_i += 1
    if start_i > end_i:
        continue
    segs.append((keys[start_i], keys[end_i], keys[i]))

rows = []
for n, (t0, t1, tbit) in enumerate(segs, 1):
    w = piv.loc[(piv.index >= t0) & (piv.index <= t1)]
    bil = w[BIL].dropna()
    if len(bil) == 0:
        continue
    t1 = bil.index[-1]
    w = piv.loc[(piv.index >= t0) & (piv.index <= t1)]
    dos = w[DOS].dropna()
    durata = (t1 - t0).total_seconds()
    start_bil = float(bil.iloc[0])
    max_bil = float(bil.max())
    end_bil = float(bil.iloc[-1])
    base = min(start_bil, float(bil.min()))
    start_bil_eff = base if base < 50 else start_bil
    dosato = max(0.0, max_bil - start_bil_eff)
    delta_dos8 = float(dos.iloc[0] - dos.iloc[-1]) if len(dos) > 1 else 0.0
    vel = dosato / durata if durata > 0 else 0.0
    rows.append(dict(n=n, t0=t0, t1=t1, tbit=tbit, durata=durata,
                     start_bil=start_bil, max_bil=max_bil, end_bil=end_bil,
                     dosato=dosato, delta_dos8=delta_dos8, vel=vel,
                     npunti=len(w)))

    # ---- grafico singola dosata ----
    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax1.plot(bil.index, bil.values, "o-", color="tab:blue", lw=1.5, ms=3,
             label="Pesa $Tlm\\_Bil21\\_Eu$ [g]")
    ax2 = ax1.twinx()
    if len(dos):
        ax2.plot(dos.index, dos.values, "s--", color="tab:red", lw=1.2, ms=3,
                 label="Contatore $Tlm\\_Dos8\\_Eu$ [g]")
    if setpoint:
        ax1.axhline(start_bil_eff + setpoint, color="green", ls=":",
                    label=f"Setpoint HMI (+{setpoint:g} g)")
    ax1.axvline(t0, color="orange", ls="--", lw=1.2,
                label="Inizio grafico (1° dato dopo bit)")
    ax1.axvline(t1, color="purple", ls="--", lw=1.2,
                label="Fine (riga successiva)")
    ax1.set_ylabel("Pesa [g]", color="tab:blue")
    ax2.set_ylabel("Tlm_Dos8_Eu [g]", color="tab:red")
    ax1.set_xlabel("Tempo")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax1.grid(alpha=0.3)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="center right", fontsize=8)
    ax1.set_title(f"Dosata #{n}  |  {t0:%H:%M:%S} \u2192 {t1:%H:%M:%S}  "
                  f"(durata {durata:.0f} s, dosato \u2248 {dosato:.0f} g)",
                  fontsize=12)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"{TAG}_{n:02d}.png"), dpi=110)
    plt.close(fig)

# ---------- report HTML ----------
html = ["<!DOCTYPE html><html lang='it'><head><meta charset='utf-8'>",
        "<title>Report Dosate — Vecchia</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}",
        "table{border-collapse:collapse;margin:16px 0}",
        "th,td{border:1px solid #bbb;padding:6px 12px;text-align:right}",
        "th{background:#2c3e50;color:#fff}",
        "td:first-child,th:first-child{text-align:center}",
        "img{max-width:100%;border:1px solid #ddd;border-radius:6px;margin:8px 0 24px}",
        ".card h2{margin-bottom:4px}</style></head><body>",
        "<h1>Report Dosate — file <code>Vecchia.csv</code></h1>",
        "<p><b>Segmentazione:</b> inizio dosata alla riga col bit DosaggioInCorso=0, "
        "fine alla riga successiva (estesa alla riga precedente il bit=0 seguente); "
        "<b>l'inizio dei grafici corrisponde al primo dato di pesa dopo il bit di start</b>.</p>",
        f"<p><b>Intervallo dati:</b> {piv.index.min():%d/%m/%Y %H:%M:%S} → {piv.index.max():%d/%m/%Y %H:%M:%S}</p>",
        f"<p><b>Numero dosate rilevate:</b> {len(rows)}</p>",
        "<table><tr><th>#</th><th>Riga bit=0</th><th>Inizio grafico (1° dato)</th>"
        "<th>Fine</th><th>Durata [s]</th><th>Pesa inizio [g]</th><th>Pesa max [g]</th>"
        "<th>Dosato [g]</th><th>&Delta; Tlm_Dos8 [g]</th><th>Velocità media [g/s]</th><th>Punti</th></tr>"]
for r in rows:
    html.append(f"<tr><td>{r['n']}</td><td>{r['tbit']:%H:%M:%S}</td>"
                f"<td>{r['t0']:%H:%M:%S}</td><td>{r['t1']:%H:%M:%S}</td>"
                f"<td>{r['durata']:.0f}</td><td>{r['start_bil']:.1f}</td>"
                f"<td>{r['max_bil']:.1f}</td><td>{r['dosato']:.1f}</td>"
                f"<td>{r['delta_dos8']:.1f}</td><td>{r['vel']:.1f}</td>"
                f"<td>{r['npunti']}</td></tr>")
html.append("</table>")
for r in rows:
    html.append("<div class='card'>")
    html.append(f"<h2>Dosata #{r['n']}</h2>")
    html.append(f"<p>Riga bit DosaggioInCorso=0: <b>{r['tbit']:%d/%m/%Y %H:%M:%S}</b> — "
                f"Inizio grafico (primo dato dopo il bit): <b>{r['t0']:%d/%m/%Y %H:%M:%S}</b> — "
                f"Fine: <b>{r['t1']:%d/%m/%Y %H:%M:%S}</b> — Durata: <b>{r['durata']:.0f} s</b><br>"
                f"Pesa a inizio dosata: <b>{r['start_bil']:.1f} g</b> — Pesa massima: <b>{r['max_bil']:.1f} g</b> — "
                f"Dosato: <b>{r['dosato']:.1f} g</b><br>"
                f"Variazione contatore Tlm_Dos8_Eu: <b>{r['delta_dos8']:.1f} g</b> — "
                f"Velocità media di dosaggio: <b>{r['vel']:.1f} g/s</b></p>")
    html.append(f"<img src='{TAG}_{r['n']:02d}.png' alt='Grafico dosata {r['n']}'>")
    html.append("</div>")
html.append("</body></html>")
with open(os.path.join(OUT, "report_vecchia.html"), "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print(f"Dosate rilevate: {len(rows)}")
for r in rows:
    print(f"  #{r['n']}: bit {r['tbit']:%H:%M:%S} | grafico {r['t0']:%H:%M:%S} -> {r['t1']:%H:%M:%S} | "
          f"dosato {r['dosato']:.1f} g | punti {r['npunti']}")
