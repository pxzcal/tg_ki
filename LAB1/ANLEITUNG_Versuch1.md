# Versuch 1 – Infrarot-Entfernungsmesser: Leitfaden

Die Auswertung macht `versuch1.py` vollständig. Im Labor musst du nur messen und
die Dateien richtig benennen.

## 1. Im Labor (Checkliste)

**Aufbau**
- Netzgerät **Output 3** (fest 5 V): Sensor-Vcc (rot) an +, GND (schwarz) an −.
- Sensorausgang Vo (gelb) an Oszilloskop Kanal A, Masse des Tastkopfs an GND.
- Abstand **ab Gehäuseende** des Sensors bis zur senkrechten Platte, Meterstab als Normal.

**Handschriftliches Messprotokoll** (Kopf: Datum, „Versuch 1“, Namen aller Beteiligten)

| Nr. | Abstand d [cm] | U (Mittelwert laut Oszi-Messfunktion) [V] | Dateiname |
|-----|----------------|-------------------------------------------|-----------|
| 1   | 10             |                                           | 10cm.csv  |
| …   | …              |                                           | …         |
| 20  | 70             |                                           | 70cm.csv  |

- **20 Abstände zwischen 10 und 70 cm**, z.B. 10, 13, 16, … 70 cm (Schritt ≈ 3,2 cm). Im
  Nahbereich (10–30 cm) eher dichter messen, weil die Kennlinie dort steil ist.
- Für jeden Abstand die Kurve im PicoScope als **CSV exportieren**. Der Abstand muss im
  Dateinamen stehen, z.B. `10cm.csv`, `12.5cm.csv`.
- Aufnahme lang genug wählen: deutlich **mehr als 1000 Samples** (das Skript verwirft die
  ersten 1000), z.B. 5000–10 000.
- **Aufgabe 3:** Platte auf **29,7 cm** (lange A4-Seite) stellen und **eine** Messung als
  `a4_laenge.csv` speichern. Danach auf **21,0 cm** (kurze Seite) und als
  `a4_breite.csv` speichern.

## 2. Dateien ablegen

```
LAB1/
  versuch1.py
  daten/
    kennlinie/   10cm.csv, 13cm.csv, … 70cm.csv
    protokoll.csv     (optional, Werte aus dem Handprotokoll)
    a4_laenge.csv
    a4_breite.csv
```

`protokoll.csv` (für den Vergleich in Aufgabe 1):
```
Abstand_cm;U_V
10;2,31
13;1,92
...
```

Dann `python versuch1.py` ausführen (mit `--zeigen` werden die Plots auch angezeigt).
Das Skript erzeugt `plots/1_kennlinie.png`, `plots/2_regression.png` und `ergebnisse.txt`.

Stellschrauben oben im Skript: `SKIP`, `N_WERTE` (sinnvolle Anzahl, z.B. 2000), `KANAL`,
`D_MAX_FIT` (wenn die großen Abstände im log-log-Plot von der Geraden abknicken, z.B.
auf 60 setzen).

## 3. Was das Skript rechnet (für das Protokoll)

**Aufgabe 1:** Die CSV wird mit `np.genfromtxt(..., converters=...)` eingelesen. Der
Converter wandelt `XX,YY` in `XX.YY` um. Danach werden die ersten 1000 Werte
übersprungen (Einschwingvorgang) und aus dem Rest Mittelwert und Standardabweichung
s (mit n−1) berechnet. Ausgegeben wird eine Tabelle mit der Differenz zum Handprotokoll
und ein Plot U(d) mit Fehlerbalken.

**Aufgabe 2:** Mit x' = ln U und y' = ln d ergibt die Regression nach Vorlesung
(a = Σ(x−x̄)(y−ȳ)/Σ(x−x̄)², b = ȳ − a·x̄) die Kennlinie **d = e^b · U^a**.
Erwartet wird a ≈ −1,1 bis −1,2 und e^b ≈ 25–30 cm (je nach Sensorexemplar).

**Aufgabe 3a:**
- s_x = s/√n. Der Korrekturfaktor t kommt aus der Vorlesungstabelle. Bei n ≈ 2000 Samples
  ist t₆₈ = 1,0 und t₉₅ ≈ 1,96–1,98.
- Ergebnis: U = Ū ± t·s_x [V], jeweils für 68 % und 95 %.
- Fehlerfortpflanzung durch die Kennlinie:
  Δd = |dd/dU| · ΔU = |a · e^b · U^(a−1)| · ΔU

**Aufgabe 3b:** A = l·w, Gauß: **ΔA = √((w·Δl)² + (l·Δw)²)**. Sollwert:
29,7 × 21,0 = 623,7 cm².

## 4. Diskussionspunkte fürs Protokoll

1. **Der Fehler wird massiv unterschätzt.** Weil n (Samples) sehr groß ist, wird s_x
   winzig (≈ 0,01 cm). Die tatsächliche Abweichung vom Sollwert ist meist viel größer
   (mm bis cm). Gründe: Jeder Abstand wurde nur **einmal eingestellt** (Hinweis im
   Arbeitsblatt). Ablesefehler am Meterstab und Ausrichtung der Platte fließen nicht ein.
   Die Samples sind außerdem nicht unabhängig (Rauschen, Signalprozessor im Sensor).
2. **Systematische Fehler:** Unsicherheit der Regressionsparameter a, b wird nicht
   fortgepflanzt. Modellfehler, weil das Potenzgesetz nur näherungsweise gilt
   (Residuen bei großen Abständen ansehen). Bezugspunkt „Gehäuseende“ vs. Sensoroptik.
3. **Empfindlichkeit:** |dd/dU| wächst mit dem Abstand (flache Kennlinie). Gleiches
   Spannungsrauschen bedeutet bei 30 cm also einen größeren Abstandsfehler als bei 20 cm.
4. **Messbereich:** Unter ≈ 8–10 cm fällt die Spannung wieder ab (Mehrdeutigkeit).
   Über 70–80 cm reichen reflektierte Lichtmenge und PSD-Auflösung nicht mehr aus.
5. **Verbesserung:** Jeden Abstand mehrfach neu einstellen und messen (z.B. 5×), dann
   Mittelwert und s über diese Wiederholungen bilden, mit dem passenden t-Faktor für
   kleines n.
