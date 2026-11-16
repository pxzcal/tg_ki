"""Aufnahmeskript Versuch 2 – Kalibrierung von Digitalkameras.

Aufruf:
    python aufnahme.py keil      -> 1 Bild  : bilder/grauwertkeil.png
    python aufnahme.py dunkel    -> 10 Bilder: bilder/dunkel_01.png ... dunkel_10.png
    python aufnahme.py weiss     -> 10 Bilder: bilder/weiss_01.png  ... weiss_10.png

Im Live-Fenster werden Min/Max/Mittelwert des Grauwertbildes angezeigt.
  Leertaste = Aufnahme starten,  q = abbrechen.
Die Kameraeinstellungen werden bei jeder Aufnahme in bilder/kamera_<modus>.txt
protokolliert (Werte fürs Messprotokoll).
"""
import sys, os, time
import cv2
import numpy as np

KAMERA_INDEX = 0        # ggf. 1, falls die Laptop-Kamera Index 0 hat
ANZAHL = {"keil": 1, "dunkel": 10, "weiss": 10}
NAME = {"keil": "grauwertkeil", "dunkel": "dunkel", "weiss": "weiss"}

# Optional: Parameter fest setzen (None = nicht anfassen).
# Windows (DirectShow): AUTO_EXPOSURE 0.25 = manuell, EXPOSURE -1 … -7 (2^x Sekunden),
#   z.B. {AUTO_EXPOSURE: 0.25, EXPOSURE: -5, AUTOFOCUS: 0}.
# macOS ignoriert diese Werte oft -> in der Logitech-App fest einstellen.
EINSTELLUNGEN = {
    cv2.CAP_PROP_AUTO_EXPOSURE: None,
    cv2.CAP_PROP_EXPOSURE: None,
    cv2.CAP_PROP_GAIN: None,
    cv2.CAP_PROP_BRIGHTNESS: None,
    cv2.CAP_PROP_AUTOFOCUS: None,
}

PROPS = {"Breite": 3, "Hoehe": 4, "Brightness": 10, "Contrast": 11,
         "Saturation": 12, "Gain": 14, "Exposure": 15, "WhiteBalance": 17,
         "AutoExposure": cv2.CAP_PROP_AUTO_EXPOSURE, "Autofocus": cv2.CAP_PROP_AUTOFOCUS,
         "Focus": cv2.CAP_PROP_FOCUS}


def main():
    modus = sys.argv[1] if len(sys.argv) > 1 else ""
    if modus not in ANZAHL:
        print(__doc__); sys.exit(1)
    os.makedirs("bilder", exist_ok=True)

    # Unter Windows DirectShow verwenden: dort funktioniert cap.set() für Belichtung
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(KAMERA_INDEX, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(KAMERA_INDEX)
    if not cap.isOpened():
        sys.exit("Kamera nicht gefunden – KAMERA_INDEX prüfen.")
    for prop, wert in EINSTELLUNGEN.items():
        if wert is not None:
            print(f"set {prop}={wert}: {'ok' if cap.set(prop, wert) else 'NICHT unterstützt'}")

    for _ in range(20):          # Kamera "einschwingen" lassen
        cap.read()

    while True:
        ok, frame = cap.read()
        if not ok:
            sys.exit("Kein Bild von der Kamera.")
        grau = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        info = f"min {grau.min()}  max {grau.max()}  mean {grau.mean():.1f}"
        if modus == "keil" and (grau.min() == 0 or grau.max() == 255):
            info += "  SAETTIGUNG!"
        if modus == "weiss":
            info += "  (Ziel mean 77-128)"
        anzeige = frame.copy()
        cv2.putText(anzeige, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(anzeige, "Leertaste = speichern, q = Ende", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow(f"Versuch 2 – {modus}", anzeige)
        taste = cv2.waitKey(1) & 0xFF
        if taste == ord("q"):
            break
        if taste == ord(" "):
            n = ANZAHL[modus]
            for i in range(n):
                ok, frame = cap.read()
                datei = (f"bilder/{NAME[modus]}.png" if n == 1
                         else f"bilder/{NAME[modus]}_{i + 1:02d}.png")
                cv2.imwrite(datei, frame)        # PNG = verlustfrei
                print("gespeichert:", datei)
                time.sleep(0.2)
            with open(f"bilder/kamera_{modus}.txt", "w") as f:
                for name, pid in PROPS.items():
                    f.write(f"{name}: {cap.get(pid)}\n")
            print(open(f"bilder/kamera_{modus}.txt").read())
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
