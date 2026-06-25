*Seam-Sync-Anfrage G2 → G3 (Versand-Vorlage). Sign-off von G3-Lead erhalten am 2026-06-23 → Contract beidseitig eingefroren (siehe `Team-Sync-Entscheidungen.md`, DTB-26).*

---

Betreff: Seam-Sync G2 -> G3 — Abstimmung + Bestaetigung fuer den API-Vertrag (v1)

Hi [Name G3-Lead],

wir (G2, Backend) bauen die API, gegen die ihr euer Frontend baut. Hier ist unser Entwurf plus
fuenf Punkte, zu denen wir kurz eure Sicht brauchen. Eine kurze Antwort-Mail oder ein
GitHub-Issue mit Label "seam-sync-confirmed" reicht.

WICHTIG ZUR ROLLENVERTEILUNG (damit das klar ist):
WIR (G2) sind der SERVER. Wir stellen die Endpoints bereit, ihr (G3) ruft sie ab.
Ihr muesst NICHTS hosten und keinen eigenen Endpoint bauen - ihr holt euch die Daten
per GET bei uns ab (genau wie ein Browser eine Webseite laedt). Einzige Ausnahme:
Alarme pushen WIR euch live ueber einen Stream (SSE), den ihr bei uns abonniert -
auch da hostet ihr nichts, ihr haltet nur die Verbindung offen.

UNSER ENTWURF: GET /v1/assessment/current liefert euch Ampel + Messwerte in einem:
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
Hinweis: Alle Endpoints liegen unter /v1/ (z. B. /v1/assessment/current). Falls wir spaeter
etwas grundlegend aendern muessen, machen wir /v2/ daneben auf - euer /v1/ bricht nicht.

FRAGEN AN EUCH:

1) ANZEIGE: Reicht euch die Risiko-Ampel (gruen/gelb/orange/rot/unbekannt) + Zeitstempel,
   oder wollt ihr auch die Roh-Messwerte dahinter anzeigen?
   (Wir koennen euch problemlos alles mitschicken - sagt einfach, was ihr anzeigt.)

2) DATENABRUF: Wollt ihr jederzeit ALLE Daten abrufen koennen (aktuelle Bewertung, Historie,
   Alarmliste), oder reicht fuer den Prototyp der aktuelle Alarm + die 30-min-Prognose?

3) QUITTIERUNG & BAHNFREIGABE (Sicherheitsregel RB-01 - WICHTIG, bitte schriftlich bestaetigen):
   Eure UI darf einen Alarm selbst quittieren/beenden (= "gesehen", nur fuers Protokoll).
   ABER: Die Freigabe oder Sperrung der Startbahn macht IMMER ein Mensch. Unser System gibt
   KEINEN automatischen Freigabe-/Sperr-Befehl - es ist reine Entscheidungsunterstuetzung.
   Bitte plant KEINEN Knopf ein, der die Startbahn automatisch freigibt oder sperrt.

4) 30-MINUTEN-PROGNOSE: wollt ihr eine Prognose-Ampel (Risiko in 30 min) oder konkrete
   Werte/Trend? (Kommt spaeter, aber wir reservieren jetzt den Platz im Vertrag.)

5) SCHWELLENWERT-MENUE (nur zur Info): Ihr baut ein Menue zum Anpassen der Grenzwerte. Zum
   Lesen geben wir die Werte frei; das Aendern sichern wir spaeter mit einer Anmeldung ab.

Wenn ihr mir zu 1-4 kurz antwortet und 3 (RB-01) bestaetigt, finalisiere ich den Vertrag.
Danke!

Viele Gruesse
[Lucas / G2]
