*Seam-Sync-Anfrage G2 → G3 (Versand-Vorlage). Sign-off von G3-Lead erhalten am 2026-06-23 → Contract beidseitig eingefroren (siehe `Team-Sync-Entscheidungen.md`, DTB-26).*

---

Betreff: Bestaetigung G2 -> G3 API-Vertrag (v1) — VERTRAG EINGEFROREN

Hi Lucas / G2,

wir (G3, Frontend) bestaetigen hiermit schriftlich den API-Vertrag fuer euer Backend.
Die folgenden Punkte sind von unserer Seite abgestimmt und gelten ab sofort als
eingefrorene Naht fuer den Prototypen:

ROLLENVERTEILUNG (bestaetigt)
G2 ist der SERVER. G2 stellt die Endpoints bereit, G3 ruft sie per GET ab.
G3 hostet keine eigenen Endpoints. Ausnahme: Alarme werden von G2 live per SSE-Stream
uebertragen; G3 haelt dabei nur die Verbindung zu G2 offen.

UNSER ENTWURF: GET /v1/assessment/current (bestaetigt)
{
  "risk_level": "yellow",        // green | yellow | orange | red | unknown
  "driving_factor": "dew_point",
  "explanation": "Klartext-Begruendung",
  "surface_temp_c": -0.4,
  "dew_point_c": -1.1,
  "delta_t": 0.7,
  "humidity_pct": 96,
  "measured_at": "2026-06-22T14:03:05Z",   // Messzeit (UTC)
  "assessed_at": "2026-06-22T14:03:30Z",   // Bewertungszeit (UTC)
  "is_stale": false,             // true = Daten veraltet, Fallback aktiv
  "sensor_status": "ok"
}
Alle Endpoints liegen unter /v1/. Spaetere grundlegende Aenderungen werden ueber /v2/
bereitgestellt; /v1/ bleibt stabil.

ABGESTIMMTE PUNKTE (bestaetigt):

1) ANZEIGE: Wir benoetigen die Risiko-Ampel (gruen/gelb/orange/rot/unbekannt) plus
   Zeitstempel. Roh-Messwerte duerfen mitgeschickt werden; welche Werte wir anzeigen,
   entscheiden wir im Frontend.

2) DATENABRUF: Fuer den Prototypen reichen aktuelle Bewertung, Alarmliste und
   Resync-Endpoint. Historie und 30-min-Prognose sind als Erweiterung vorgesehen.

3) QUITTIERUNG & BAHNFREIGABE (RB-01 bestaetigt):
   Unsere UI quittiert Alarme nur protokollierend ("gesehen").
   Die Freigabe oder Sperrung der Startbahn erfolgt ausschliesslich durch einen Menschen.
   G2 gibt KEINEN automatischen Freigabe-/Sperr-Befehl ab. Unser Frontend enthaelt
   KEINEN Knopf zur automatischen Startbahnfreigabe oder -sperrung.

4) 30-MINUTEN-PROGNOSE: Der Platz im Vertrag ist reserviert. Konkrete Umsetzung folgt
   spaeter; vorerst reicht uns die Reservierung des Feldes/Endpoints.

5) SCHWELLENWERT-MENUE: Zur Kenntnis genommen. Schwellenwerte werden von G2 zum Lesen
   bereitgestellt; das Aendern wird spaeter durch Anmeldung abgesichert.

Mit dieser Bestaetigung ist die G2->G3 Naht auf unserer Seite eingefroren.

Bestaetigt von G3:
Name:       [Name G3-Lead]
Datum:      2026-06-23
Status:     seam-sync-confirmed G2->G3 v1

---

## Versandbegleittext G2 -> G3 (Hinweise zur eingefrorenen v1-Spec)

Geht zusammen mit der bereinigten `openapi.yaml`-Versandkopie an G3 — bewusste Design-Entscheidungen,
keine Spec-Luecken:

1. **Quittierung ist (noch) nicht authentifiziert.** `POST /v1/alarms/{id}/ack` hat im Prototyp (M2)
   **kein** Security-Requirement; das `operator`-Feld ist aktuell der einzige Audit-Anker. Ein
   Credential-/Auth-Konzept ist ein **offener Backlog-Punkt fuer M3** (analog zum Schwellenwert-Aendern,
   Punkt 5 oben). **Bitte den Ack-Aufruf so bauen, dass spaeter ein Auth-Header ergaenzt werden kann** —
   nicht davon ausgehen, dass der Endpoint dauerhaft offen bleibt.
2. **SSE-Alarm-Events tragen `severity` + `assessment_id`, aber kein `risk_level`.** Bewusst (E-37): ein
   Alarm ist ein Ereignis, kein Bewertungs-Snapshot. Fuer den Ampel-/Risiko-Kontext (Initial-Load bzw. je
   Event) einen Folge-Call `GET /v1/assessment/current` machen (siehe auch die `AlarmSeverity`-Beschreibung
   in der Spec).
