# config/ — Default-Schwellenwerte (parametrierbar, NF-05)

Hier liegen die **Schwellenwert-Defaults** der Vereisungsbewertung als Konfiguration —
**nicht im Code hartverdrahtet** (NF-05, FA-11; s. CLAUDE.md-Pflicht).

> STATUS PROJEKTFINAL (Stand 2026-07-01): Die Werte stammen aus
> `../../02-Arbeitsdokumente/Schwellenwerte.md` §2 und sind für diesen Prototyp **projektfinal**.
> Messtechnisch validierte G1-Finalwerte sind nicht mehr zu erwarten (ein Sensor defekt,
> einer nicht kalibrierbar) — die Werte wurden stattdessen aus den Sensor-Datenblättern
> abgeleitet und an Standort-Realdaten (ANR ≈ Coburg) plausibilisiert. Sie bleiben
> **parametrierbar (NF-05)** und ohne Code-Änderung austauschbar; die endgültige
> messtechnische Kalibrierung ist Teil der 2-Jahres-Weiterentwicklung (Ausblick).

Die konkrete Config-Datei (z. B. `thresholds.json`) entsteht mit P2.4/P4.3.
