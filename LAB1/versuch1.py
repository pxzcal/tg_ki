"""
Versuch 1 – Kalibrierung und Einsatz eines Infrarot-Entfernungsmessers
(Sharp GP2Y0A21YK0F), Praktikum Technische Grundlagen der KI, HTWG Konstanz.

Aufbau der Datenablage (relativ zu dieser Datei):

    daten/
      kennlinie/           eine PicoScope-CSV pro Abstand, Abstand in cm im Dateinamen,
                           z.B. "10cm.csv", "12.5cm.csv", "d_40.csv"
      protokoll.csv        (optional) Werte aus dem handschriftlichen Protokoll:
                           Abstand_cm;U_V   (eine Zeile pro Messung)
      a4_laenge.csv        Einzelmessung: Platte im Abstand der langen A4-Seite (29,7 cm)
      a4_breite.csv        Einzelmessung: Platte im Abstand der kurzen A4-Seite (21,0 cm)
    plots/                 wird automatisch angelegt

Aufruf:  python versuch1.py            (oder: python versuch1.py --daten <ordner>)
"""

import argparse
import re
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------------
# Einstellungen
# ----------------------------------------------------------------------------
SKIP = 1000          # erste Werte verwerfen (Einschwingvorgang)
N_WERTE = None       # Anzahl Werte nach SKIP für Mittelwert/Std (None = alle restlichen)
KANAL = 1            # Spalte des Sensorsignals in der CSV (0 = Zeit, 1 = Kanal A)
D_MAX_FIT = 50.0     # nur Abstände <= D_MAX_FIT [cm] in die Regression (darüber knickt die log-log-Gerade ab)
D_MIN_FIT = 10.0     # ... und >= D_MIN_FIT [cm]
A4_LAENGE_CM = 29.7  # Sollwerte DIN A4 (nur zum Vergleich)
A4_BREITE_CM = 21.0

# Korrekturfaktoren t (Vorlesung 3, Folie 10) für P = 68,26 % und P = 95 %
T_TABELLE = {
    2: (1.84, 12.71), 3: (1.32, 4.30), 4: (1.20, 3.18), 5: (1.15, 2.78),
    6: (1.11, 2.57), 7: (1.09, 2.45), 8: (1.08, 2.37), 9: (1.07, 2.31),
    10: (1.06, 2.26), 15: (1.04, 2.15), 20: (1.03, 2.09), 30: (1.02, 2.05),
    50: (1.01, 2.01), 80: (1.00, 1.99), 100: (1.00, 1.98), np.inf: (1.00, 1.96),
}


# ----------------------------------------------------------------------------
# Einlesen
# ----------------------------------------------------------------------------
def _komma_zu_float(s):
    """Converter für genfromtxt: '1,234' -> 1.234; '∞' / leer -> nan."""
    if isinstance(s, bytes):
        s = s.decode("utf-8", errors="replace")
    s = s.strip().strip('"').replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan  # z.B. '∞' bei Übersteuerung


def lade_oszi_csv(pfad, kanal=KANAL):
    """Liest eine PicoScope-CSV (Dezimalkomma) mit np.genfromtxt ein.

    Gibt das Spannungssignal des gewählten Kanals als 1D-Array zurück.
    """
    pfad = Path(pfad)
    roh = pfad.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = roh.decode(enc)
            if "\x00" not in text:
                break
        except UnicodeDecodeError:
            continue
    zeilen = text.splitlines()

    # Kopfzeilen überspringen: erste Zeile, die mit einer Zahl beginnt
    start = next(i for i, z in enumerate(zeilen)
                 if re.match(r'^\s*"?[-+]?\d', z))
    erste = zeilen[start]
    if ";" in erste:
        delim = ";"
    elif "\t" in erste:
        delim = "\t"
    else:
        delim = ","
        if erste.count(",") > 1 and "." not in erste:
            raise ValueError(f"{pfad.name}: Trennzeichen und Dezimalzeichen sind beide ',' "
                             "- bitte in PicoScope mit ';' als Trennzeichen exportieren.")
    n_spalten = len(erste.split(delim))

    daten = np.genfromtxt(
        zeilen[start:],
        delimiter=delim,
        converters={i: _komma_zu_float for i in range(n_spalten)},
        encoding="utf-8",
    )
    daten = np.array(daten.tolist(), dtype=float)  # strukturierte Arrays -> 2D
    if daten.ndim == 1:
        daten = daten[:, None]
    return daten[:, min(kanal, daten.shape[1] - 1)]


def mittelwert_std(pfad, skip=SKIP, n=N_WERTE):
    """Aufgabe 1: überspringt die ersten `skip` Werte und liefert
    (Mittelwert, empirische Standardabweichung s, Anzahl n)."""
    u = lade_oszi_csv(pfad)[skip:]
    if n is not None:
        u = u[:n]
    u = u[np.isfinite(u)]
    if len(u) < 2:
        raise ValueError(f"{pfad}: zu wenige gültige Werte nach dem Überspringen")
    return u.mean(), u.std(ddof=1), len(u)


def abstand_aus_dateiname(pfad):
    m = re.search(r"(\d+(?:[.,]\d+)?)", Path(pfad).stem)
    if not m:
        raise ValueError(f"Kein Abstand im Dateinamen: {pfad}")
    return float(m.group(1).replace(",", "."))


# ----------------------------------------------------------------------------
# Statistik / Regression
# ----------------------------------------------------------------------------
def t_faktor(n):
    """Korrekturfaktoren (t68, t95) aus der Vorlesungstabelle.
    Konservativ: nächstkleinerer tabellierter Wert von n."""
    schluessel = [k for k in T_TABELLE if k <= n]
    return T_TABELLE[max(schluessel)]


def lineare_regression(x, y):
    """Ausgleichsgerade y = a*x + b nach Vorlesung 3, Folie 27."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    xm, ym = x.mean(), y.mean()
    a = np.sum((x - xm) * (y - ym)) / np.sum((x - xm) ** 2)
    b = ym - a * xm
    return a, b


def kennlinie(u, a, b):
    """Abstand d [cm] aus Spannung U [V]:  d = e^b * U^a"""
    return np.exp(b) * np.power(u, a)


def kennlinie_ableitung(u, a, b):
    """dd/dU = a * e^b * U^(a-1)"""
    return a * np.exp(b) * np.power(u, a - 1)


# ----------------------------------------------------------------------------
# Aufgaben
# ----------------------------------------------------------------------------
def aufgabe1(daten_dir, plot_dir, log):
    log("=" * 70)
    log("AUFGABE 1: Kennlinie des Abstandssensors")
    log("=" * 70)
    dateien = sorted((daten_dir / "kennlinie").glob("*.csv"), key=abstand_aus_dateiname)
    if not dateien:
        raise FileNotFoundError(f"Keine CSV-Dateien in {daten_dir / 'kennlinie'}")

    d, u, s, n = [], [], [], []
    for f in dateien:
        m, sd, k = mittelwert_std(f)
        d.append(abstand_aus_dateiname(f)); u.append(m); s.append(sd); n.append(k)
    d, u, s, n = map(np.array, (d, u, s, n))

    # Vergleich mit handschriftlichem Protokoll (optional)
    proto = {}
    pf = daten_dir / "protokoll.csv"
    px = daten_dir.parent / "Messprotokoll_Versuch1.xlsx"
    if px.exists():
        from openpyxl import load_workbook
        ws = load_workbook(px, data_only=True)["Messprotokoll"]
        for nr, di, ui in ws.iter_rows(min_col=1, max_col=3, values_only=True):
            if isinstance(nr, int) and isinstance(di, (int, float)) and isinstance(ui, (int, float)):
                proto[round(float(di), 2)] = float(ui)
    elif pf.exists():
        p = np.genfromtxt(pf, delimiter=";", skip_header=1,
                          converters={0: _komma_zu_float, 1: _komma_zu_float},
                          encoding="utf-8")
        p = np.array(p.tolist(), dtype=float).reshape(-1, 2)
        proto = {round(di, 2): ui for di, ui in p}

    log(f"{'d [cm]':>8} {'U_mittel [V]':>13} {'s [mV]':>8} {'n':>6} {'U_Protokoll [V]':>16} {'Diff [mV]':>10}")
    for di, ui, si, ni in zip(d, u, s, n):
        up = proto.get(round(di, 2))
        zus = f"{up:16.3f} {1000 * (ui - up):10.1f}" if up is not None else f"{'-':>16} {'-':>10}"
        log(f"{di:8.1f} {ui:13.4f} {1000 * si:8.2f} {ni:6d} {zus}")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(d, u, yerr=s, fmt="o", ms=4, capsize=3, label="Messung (Mittelwert ± s)")
    if proto:
        dp = np.array(list(proto.keys())); up = np.array(list(proto.values()))
        ax.plot(dp, up, "x", color="C3", label="Protokoll (Oszilloskop-Anzeige)")
    ax.set_xlabel("Abstand d [cm]"); ax.set_ylabel("Ausgangsspannung U [V]")
    ax.set_title("Kennlinie Sharp GP2Y0A21YK0F")
    ax.grid(alpha=.3); ax.legend()
    fig.tight_layout(); fig.savefig(plot_dir / "1_kennlinie.png", dpi=150)
    return d, u, s


def aufgabe2(d, u, plot_dir, log):
    log("\n" + "=" * 70)
    log("AUFGABE 2: Modellierung der Kennlinie (doppelt logarithmisch)")
    log("=" * 70)
    x_log, y_log = np.log(u), np.log(d)            # x' = ln U, y' = ln d
    maske = (d >= D_MIN_FIT) & (d <= D_MAX_FIT)
    a, b = lineare_regression(x_log[maske], y_log[maske])
    rest = y_log[maske] - (a * x_log[maske] + b)
    r2 = 1 - np.sum(rest ** 2) / np.sum((y_log[maske] - y_log[maske].mean()) ** 2)
    log(f"Regression über {maske.sum()} von {len(d)} Punkten ({D_MIN_FIT:g}–{D_MAX_FIT:g} cm)")
    log(f"  ln d = a * ln U + b   mit  a = {a:.4f},  b = {b:.4f}   (R² = {r2:.5f})")
    log(f"  => d(U) = e^b * U^a = {np.exp(b):.3f} cm * (U/V)^({a:.4f})")
    d_mod = kennlinie(u, a, b)
    log(f"\n{'d [cm]':>8} {'d_Modell [cm]':>14} {'Abw. [cm]':>10}")
    for di, dm in zip(d, d_mod):
        log(f"{di:8.1f} {dm:14.2f} {dm - di:10.2f}")

    fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
    ax = axs[0]
    ax.plot(x_log[maske], y_log[maske], "o", ms=4, label="Messpunkte (Fit)")
    if (~maske).any():
        ax.plot(x_log[~maske], y_log[~maske], "o", ms=4, mfc="none", color="gray",
                label="nicht im Fit")
    xx = np.linspace(x_log.min(), x_log.max(), 100)
    ax.plot(xx, a * xx + b, "-", color="C1", label=f"y' = {a:.3f}·x' + {b:.3f}")
    ax.set_xlabel("x' = ln(U / V)"); ax.set_ylabel("y' = ln(d / cm)")
    ax.set_title("Doppelt logarithmische Darstellung"); ax.grid(alpha=.3); ax.legend()

    ax = axs[1]
    ax.plot(u, d, "o", ms=4, label="Messpunkte")
    uu = np.linspace(u.min(), u.max(), 200)
    ax.plot(uu, kennlinie(uu, a, b), "-", color="C1",
            label=f"d = {np.exp(b):.2f}·U^({a:.3f})")
    ax.set_xlabel("Spannung U [V]"); ax.set_ylabel("Abstand d [cm]")
    ax.set_title("Umrechnungskennlinie U → d"); ax.grid(alpha=.3); ax.legend()
    fig.tight_layout(); fig.savefig(plot_dir / "2_regression.png", dpi=150)
    return a, b


def einzelmessung(pfad, a, b, soll, name, log):
    """Aufgabe 3a: Messergebnis mit Vertrauensbereichen + Fehlerfortpflanzung."""
    um, s, n = mittelwert_std(pfad)
    sx = s / np.sqrt(n)
    t68, t95 = t_faktor(n)
    du68, du95 = t68 * sx, t95 * sx
    d = kennlinie(um, a, b)
    abl = kennlinie_ableitung(um, a, b)
    dd68, dd95 = abs(abl) * du68, abs(abl) * du95

    log(f"\n--- {name} ({Path(pfad).name}) ---")
    log(f"  n = {n},  Ū = {um:.5f} V,  s = {1000 * s:.3f} mV,  s_x = s/√n = {1000 * sx:.4f} mV")
    log(f"  t-Faktoren (n={n}): t68 = {t68},  t95 = {t95}")
    log(f"  Spannung (P=68 %):  U = ({um:.4f} ± {du68:.4f}) V   "
        f"Vertrauensbereich [{um - du68:.4f}; {um + du68:.4f}] V")
    log(f"  Spannung (P=95 %):  U = ({um:.4f} ± {du95:.4f}) V   "
        f"Vertrauensbereich [{um - du95:.4f}; {um + du95:.4f}] V")
    log(f"  Fehlerfortpflanzung: Δd = |dd/dU|·ΔU,  dd/dU = a·e^b·U^(a-1) = {abl:.3f} cm/V")
    log(f"  Abstand (P=68 %):   d = ({d:.3f} ± {dd68:.3f}) cm")
    log(f"  Abstand (P=95 %):   d = ({d:.3f} ± {dd95:.3f}) cm")
    log(f"  Sollwert {soll} cm -> Abweichung {d - soll:+.2f} cm "
        f"({100 * (d - soll) / soll:+.1f} %)")
    return d, dd68, dd95


def aufgabe3(daten_dir, a, b, log):
    log("\n" + "=" * 70)
    log("AUFGABE 3: Flächenmessung mit Fehlerrechnung")
    log("=" * 70)
    fl, fb = daten_dir / "a4_laenge.csv", daten_dir / "a4_breite.csv"
    if not fl.exists():
        log(f"(übersprungen: {fl.name} fehlt)")
        return
    l, dl68, dl95 = einzelmessung(fl, a, b, A4_LAENGE_CM, "3a: Länge (lange A4-Seite)", log)
    if not fb.exists():
        log(f"(3b übersprungen: {fb.name} fehlt)")
        return
    w, dw68, dw95 = einzelmessung(fb, a, b, A4_BREITE_CM, "3b: Breite (kurze A4-Seite)", log)

    A = l * w
    # Gauß: ΔA = sqrt((∂A/∂l·Δl)² + (∂A/∂w·Δw)²) = sqrt((w·Δl)² + (l·Δw)²)
    dA68 = np.sqrt((w * dl68) ** 2 + (l * dw68) ** 2)
    dA95 = np.sqrt((w * dl95) ** 2 + (l * dw95) ** 2)
    soll = A4_LAENGE_CM * A4_BREITE_CM
    log("\n--- 3b: Fläche A = l · w ---")
    log("  Gauß: ΔA = sqrt((w·Δl)² + (l·Δw)²)")
    log(f"  A (P=68 %) = ({A:.1f} ± {dA68:.1f}) cm²")
    log(f"  A (P=95 %) = ({A:.1f} ± {dA95:.1f}) cm²")
    log(f"  Sollwert {soll:.1f} cm² -> Abweichung {A - soll:+.1f} cm² "
        f"({100 * (A - soll) / soll:+.1f} %)")


def main():
    hier = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--daten", default=hier / "daten", type=Path)
    ap.add_argument("--zeigen", action="store_true", help="Plots zusätzlich anzeigen")
    args = ap.parse_args()

    plot_dir = args.daten.parent / "plots"
    plot_dir.mkdir(exist_ok=True)
    ausgabe = []

    def log(text=""):
        print(text); ausgabe.append(text)

    d, u, s = aufgabe1(args.daten, plot_dir, log)
    a, b = aufgabe2(d, u, plot_dir, log)
    aufgabe3(args.daten, a, b, log)

    (args.daten.parent / "ergebnisse.txt").write_text("\n".join(ausgabe), encoding="utf-8")
    print(f"\nPlots in {plot_dir}, Ergebnisse in {args.daten.parent / 'ergebnisse.txt'}")
    if args.zeigen:
        plt.show()


if __name__ == "__main__":
    main()
