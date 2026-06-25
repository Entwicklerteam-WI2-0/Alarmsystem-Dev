*Seam-Sync-Anfrage G1 → G2 (Versand-Vorlage). Sign-off von G1-Lead erhalten am 2026-06-23 → Naht G1-seitig eingefroren (siehe `Team-Sync-Entscheidungen.md`, DTB-26).*

---

Betreff: Seam-Sync G1 -> G2 — kurze schriftliche Bestaetigung der Sensordaten-Naht (v1)

Hi Nils,

wir (G2, Backend) frieren gerade den Datenvertrag zwischen euren Sensoren (G1) und unserem
Backend ein. Wir bauen einen Poller, der euren Endpoint regelmaessig abfragt. Bitte bestaetigt
uns kurz die folgenden vier Punkte (eine kurze Antwort-Mail oder WhatsApp reicht vollkommen aus:

1) ABRUF-ENDPOINT
   Ihr stellt bereit:
   - GET /current  -> alle aktuellen Messwerte als EIN Snapshot mit EINEM gemeinsamen
     Mess-Zeitstempel (measured_at, UTC/ISO-8601)
   - GET /health   -> Verfuegbarkeit (200 = ok / 503 = fault)
   Passt das so?

2) FELDER + TYPEN von GET /current (bitte bestaetigen oder korrigieren):
   sensor_id       (Text, z. B. "anr-rwy-01")
   measured_at     (Zeitstempel, UTC/ISO-8601, z. B. 2026-06-22T14:03:05Z)
   surface_temp_c  (Zahl, Grad C)   - Oberflaechentemperatur
   air_temp_c      (Zahl, Grad C)   - Lufttemperatur
   humidity_pct    (Zahl, Prozent)  - ist das die LUFTFEUCHTE? Bitte bestaetigen.
   pressure_hpa    (Zahl, hPa)      - Luftdruck, optional
   status          ("ok" / "fault")

3) WAS WIR NICHT VON EUCH BRAUCHEN:
   Ihr muesst KEINEN Taupunkt und KEINEN fertigen Vereisungs-/Eis-Indikator liefern.
   Den Taupunkt und die Risiko-Bewertung rechnen wir (G2) selbst aus euren Rohwerten.
   Bitte nur die Messwerte oben.

4) ABFRAGE-TAKT:
   Wir fragen GET /current alle 30 Sekunden ab. Sind eure Werte aktueller als 2 Minuten?
   Wir behandeln Daten, die aelter als 120 Sekunden sind, als "veraltet" (Sicherheits-
   Fallback: dann zeigen wir nie GRUEN). Passt 30 s Abruf / 120 s Stale-Grenze fuer euch?

Danke euch! Sobald ihr 1-4 bestaetigt, ist die Naht auf eurer Seite eingefroren.

Viele Gruesse
[Lucas / G2]
