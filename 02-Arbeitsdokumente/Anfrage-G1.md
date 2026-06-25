*Seam-Sync-Anfrage G1 → G2 (Versand-Vorlage). Sign-off von G1-Lead erhalten am 2026-06-23 → Naht G1-seitig eingefroren (siehe `Team-Sync-Entscheidungen.md`, DTB-26).*

---

Betreff: Bestaetigung G1 -> G2 Sensordaten-Naht (v1) — VERTRAG EINGEFROREN

Hi Lucas / G2,

wir (G1, Sensorik) bestaetigen hiermit schriftlich den Datenvertrag zwischen unseren Sensoren
und eurem Backend. Die folgenden vier Punkte sind von unserer Seite abgestimmt und gelten ab
sofort als eingefrorene Naht fuer den Prototypen:

1) ABRUF-ENDPOINT (bestaetigt)
   Wir stellen bereit:
   - GET /current  -> alle aktuellen Messwerte als EIN Snapshot mit EINEM gemeinsamen
     Mess-Zeitstempel (measured_at, UTC/ISO-8601)
   - GET /health   -> Verfuegbarkeit (200 = ok / 503 = fault)
   Das passt fuer uns.

2) FELDER + TYPEN von GET /current (bestaetigt):
   sensor_id       (Text, z. B. "anr-rwy-01")
   measured_at     (Zeitstempel, UTC/ISO-8601, z. B. 2026-06-22T14:03:05Z)
   surface_temp_c  (Zahl, Grad C)   - Oberflaechentemperatur
   air_temp_c      (Zahl, Grad C)   - Lufttemperatur
   humidity_pct    (Zahl, Prozent)  - LUFTFEUCHTE, bestaetigt
   pressure_hpa    (Zahl, hPa)      - Luftdruck, optional
   status          ("ok" / "fault")

3) WAS WIR NICHT LIEFERN (bestaetigt)
   Wir liefern KEINEN Taupunkt und KEINEN fertigen Vereisungs-/Eis-Indikator.
   Taupunkt und Risiko-Bewertung werden von G2 aus unseren Rohwerten berechnet.
   Wir liefern ausschliesslich die oben genannten Messwerte.

4) ABFRAGE-TAKT (bestaetigt)
   G2 fragt GET /current alle 30 Sekunden ab.
   Unsere Werte sind aktueller als 2 Minuten.
   Daten, die aelter als 120 Sekunden sind, werden von G2 als "veraltet" behandelt
   (Fail-safe: dann wird nie GRUEN angezeigt). Das passt fuer uns.

Mit dieser Bestaetigung ist die G1->G2 Naht auf unserer Seite eingefroren.

Bestaetigt von G1:
Name:       [Nils / G1-Lead]
Datum:      2026-06-23
Status:     seam-sync-confirmed G1->G2 v1
