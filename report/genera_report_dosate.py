# -*- coding: utf-8 -*-
"""
Genera un report + grafico per ogni singola dosata contenuta in Dosate0.csv.

Logica di segmentazione (come da specifica utente):
  - La pesata INIZIA con la riga in cui il bit Bil21_Wrk_DosaggioInCorso vale 0
    e TERMINA con la riga successiva a quella riga del bit.
  - Nel CSV il bit viene registrato solo nelle sue transizioni a 0 (7 occorrenze).
    Ogni occorrenza del bit apre quindi una dosata che parte dalla riga col bit=0;
    se la riga col bit=0 successivo arriva piu' tardi (perche' nel mezzo non ci
    sono campioni del bit), la dosata si estende fino alla riga precedente, in
    modo da includere l'intera fase attiva della pesata. L'ultima dosata termina
    sulla riga successiva all'ultimo bit=0 disponibile nei dati.
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV = "/workspace/Dosate0.csv"
OUT = "/workspace/report"
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
setpoint = None
if SET in piv and piv[SET].notna().any():
    setpoint = float(piv[SET].dropna().iloc[-1])

# ---------- rilevazione dosate dal bit DosaggioInCorso ----------
bit_series = piv[BIT]
zero_idx = [i for i, t in enumerate(keys)
            if pd.notna(bit_series.get(t)) and bit_series.loc[t] < 0.5]

bil_all = piv[BIL]
segs = []
for j, i in enumerate(zero_idx):
    start_i = i                                # riga con bit = 0 -> inizio
    if j + 1 < len(zero_idx):
        nxt = zero_idx[j + 1]
        end_i = max(i + 1, nxt - 1)            # riga prima del prossimo bit=0
    else:
        end_i = min(i + 1, len(keys) - 1)      # ultima: riga successiva al bit
    # CAUSA DEI "TEMPI MORTI" INIZIALI NEI GRAFICI:
    # il data-logger registra il bit DosaggioInCorso solo quando scende a 0
    # (fine dosata). Dopo quella riga, pero', la registrazione della pesa si
    # INTERROMPE per un tempo variabile (svuotamento/scarico del contenitore:
    # ~76 s dopo il bit #1, ~22 s dopo il bit #2, poi 36-159 s...). La dosata
    # successiva riprende quindi dal primo campione REALE di pesa dopo il buco
    # (valore ~0 g = tara raggiunta). Allineando qui l'inizio, i tratti vuoti
    # iniziali spariscono dai grafici.
    while start_i <= end_i and pd.isna(bil_all.get(keys[start_i])):
        start_i += 1
    if start_i > end_i:
        continue
    segs.append((keys[start_i], keys[end_i]))

mode = ("bit DosaggioInCorso: la pesata inizia con la riga a 0 e termina con "
        "la riga successiva (estesa alla riga precedente il bit=0 seguente "
        "quando la fase attiva cade tra due eventi registrati)")

rows = []
for n, (t0, t1) in enumerate(segs, 1):
    w = piv.loc[(piv.index >= t0) & (piv.index <= t1)]
    bil = w[BIL].dropna()
    dos = w[DOS].dropna()
    # allinea anche la fine all'ultima riga con un valore di pesa
    t1 = bil.index[-1]
    w = piv.loc[(piv.index >= t0) & (piv.index <= t1)]
    dos = w[DOS].dropna()
    durata = (t1 - t0).total_seconds()
    if len(bil) == 0:
        continue
    # baseline: la pesata parte da zero dopo lo svuotamento; il valore della
    # riga di bit puo' essere ancora quello della pesata precedente (residuo),
    # quindi come base assumiamo min(prima riga, minimo del segmento)
    start_bil = float(bil.iloc[0])
    end_bil = float(bil.iloc[-1])
    max_bil = float(bil.max())
    base = min(start_bil, float(bil.min()))
    if base < 50:          # c'e' stato azzeramento/svuotamento nel segmento
        start_bil_eff = base
    else:
        start_bil_eff = start_bil
    dosato = max(0.0, max_bil - start_bil_eff)
    delta_dos8 = float(dos.iloc[0] - dos.iloc[-1]) if len(dos) > 1 else 0.0
    vel = dosato / durata if durata > 0 else 0.0
    rows.append(dict(n=n, t0=t0, t1=t1, durata=durata, start_bil=start_bil,
                     max_bil=max_bil, end_bil=end_bil, dosato=dosato,
                     delta_dos8=delta_dos8, vel=vel, npunti=len(w)))

    # ---- grafico singola dosata ----
    fig, ax1 = plt.subplots(figsize=(11, 6))
    ax1.plot(bil.index, bil.values, "o-", color="tab:blue", lw=1.5, ms=3,
             label="Pesa $Tlm\\_Bil21\\_Eu$ [g]")
    ax2 = ax1.twinx()
    if len(dos):
        ax2.plot(dos.index, dos.values, "s--", color="tab:red", lw=1.2, ms=3,
                 label="Contatore $Tlm\\_Dos8\\_Eu$ [g]")
    if setpoint:
        ax1.axhline(start_bil + setpoint, color="green", ls=":",
                    label=f"Setpoint HMI (+{setpoint:g} g)")
    ax1.axvline(t0, color="orange", ls="--", lw=1.2,
                label="Inizio (riga bit=0)")
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
    png = os.path.join(OUT, f"dosata_{n:02d}.png")
    fig.savefig(png, dpi=110)
    plt.close(fig)

# ---------- report HTML ----------
html = ["<!DOCTYPE html><html lang='it'><head><meta charset='utf-8'>",
        "<title>Report Dosate — Dosate0</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}",
        "table{border-collapse:collapse;margin:16px 0}",
        "th,td{border:1px solid #bbb;padding:6px 12px;text-align:right}",
        "th{background:#2c3e50;color:#fff}", "td:first-child,th:first-child{text-align:center}",
        "img{max-width:100%;border:1px solid #ddd;border-radius:6px;margin:8px 0 24px}",
        ".card h2{margin-bottom:4px}</style></head><body>",
        "<h1>Report Dosate — file <code>Dosate0.csv</code></h1>",
        f"<p><b>Segmentazione:</b> {mode}</p>",
        f"<p><b>Intervallo dati:</b> {piv.index.min():%d/%m/%Y %H:%M:%S} → {piv.index.max():%d/%m/%Y %H:%M:%S}</p>",
        f"<p><b>Numero dosate rilevate:</b> {len(rows)}</p>",
        "<table><tr><th>#</th><th>Inizio (riga bit=0)</th><th>Fine (riga succ.)</th>"
        "<th>Durata [s]</th>"
        "<th>Pesa inizio [g]</th><th>Pesa max [g]</th><th>Dosato [g]</th>"
        "<th>&Delta; Tlm_Dos8 [g]</th><th>Velocità media [g/s]</th><th>Punti</th></tr>"]
for r in rows:
    html.append(f"<tr><td>{r['n']}</td><td>{r['t0']:%H:%M:%S}</td><td>{r['t1']:%H:%M:%S}</td>"
                f"<td>{r['durata']:.0f}</td><td>{r['start_bil']:.1f}</td><td>{r['max_bil']:.1f}</td>"
                f"<td>{r['dosato']:.1f}</td><td>{r['delta_dos8']:.1f}</td>"
                f"<td>{r['vel']:.1f}</td><td>{r['npunti']}</td></tr>")
html.append("</table>")
for r in rows:
    html.append("<div class='card'>")
    html.append(f"<h2>Dosata #{r['n']}</h2>")
    html.append(f"<p>Inizio (riga con DosaggioInCorso=0): <b>{r['t0']:%d/%m/%Y %H:%M:%S}</b> — "
                f"Fine (riga successiva): <b>{r['t1']:%d/%m/%Y %H:%M:%S}</b> — "
                f"Durata: <b>{r['durata']:.0f} s</b><br>"
                f"Pesa a inizio dosata: <b>{r['start_bil']:.1f} g</b> — Pesa massima: <b>{r['max_bil']:.1f} g</b> — "
                f"Dosato: <b>{r['dosato']:.1f} g</b><br>"
                f"Variazione contatore Tlm_Dos8_Eu: <b>{r['delta_dos8']:.1f} g</b> — "
                f"Velocità media di dosaggio: <b>{r['vel']:.1f} g/s</b></p>")
    html.append(f"<img src='dosata_{r['n']:02d}.png' alt='Grafico dosata {r['n']}'>")
    html.append("</div>")
html.append("</body></html>")

with open(os.path.join(OUT, "report_dosate.html"), "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print(f"Dosate rilevate: {len(rows)} (modalita': {mode})")
for r in rows:
    print(f"  #{r['n']}: {r['t0']:%H:%M:%S} -> {r['t1']:%H:%M:%S} | "
          f"dosato {r['dosato']:.1f} g | punti {r['npunti']}")
