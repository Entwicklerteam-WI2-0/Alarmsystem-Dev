# Team-Sync G3 — Abstimmungsfragen zur API-Naht (v1)

**Kontext:** DTB-19 (OpenAPI-Spec v1) → DTB-26 (Team-Sync mit G1+G3)
**Autor:** Luca Ganter (G2, Backend) · **Stand:** 2026-06-23
**Zweck:** Bevor wir den API-Vertrag (G2 → G3) einfrieren, klären wir mit G3 die offenen
Punkte. Grundlage: DTB-19-Beschreibung + Klarstellungen von Lucas Vöhringer (Architekt).

> **DoD-Hinweis (DTB-26):** Wir brauchen am Ende eine **schriftliche Bestätigung** von G3
> (E-Mail oder GitHub-Issue mit Label `team-sync-confirmed`).

---

## Nachricht an den G3-Repräsentanten (copy-paste-fertig)

**Betreff: API-Naht G2 → G3 — kurze Abstimmung für den Vertrags-Entwurf (v1)**

Hi [Name],

ich baue gerade die **API-Spezifikation** unseres Backends (G2), gegen die ihr euer Frontend
bauen werdet. Bevor wir den Vertrag einfrieren, brauche ich von euch zu **5 Punkten** kurz eure
Sicht. Ich schicke euch parallel einen ersten Entwurf, gegen den ihr reden könnt — diese Fragen
bestimmen, wie die Daten konkret aussehen:

**1. Anzeige — Ampel oder auch die Messwerte?**
Reicht euch zur Anzeige die **Risiko-Ampel** (grün / gelb / orange / rot / unbekannt) +
Zeitstempel, oder wollt ihr auch die **Roh-Messwerte** dahinter anzeigen? Verfügbar wären:
`measured_at` (Zeitstempel), `sensor_id`, `surface_temp_c` (Oberflächentemp.),
`air_temp_c` (Lufttemp.), `humidity_pct` (Luftfeuchte), `pressure_hpa` (Luftdruck, optional),
`status`.
→ Wir können euch problemlos alles mitschicken; sagt einfach, was ihr anzeigen wollt.

**2. Datenabruf — alles oder nur Alarm + Prognose?**
Wollt ihr die Möglichkeit, **jederzeit alle unsere Daten** abzurufen (aktuelle Bewertung,
Messwert-Historie, Alarmliste), oder reicht euch für den Prototyp **der aktuelle Alarm + die
30-min-Prognose**? Das entscheidet, welche Abruf-Endpoints wir in v1 anbieten.

**3. Quittierung & Bahnfreigabe (wichtig — Sicherheitsregel RB-01):**
Eure UI darf einen Alarm **selbst quittieren/beenden** (= „gesehen/bearbeitet", nur fürs
Protokoll). Aber: Die **Freigabe oder Sperrung der Startbahn macht immer ein Mensch** — unser
System gibt **keinen** automatischen Freigabe-/Sperr-Befehl, das ist reine
Entscheidungsunterstützung. Bitte plant **keinen** „Startbahn freigeben/sperren"-Knopf ein, der
etwas automatisch schaltet.

**4. 30-Minuten-Prognose — Ampel oder genaue Werte?**
Beim Prognose-Feature: wollt ihr eine **Prognose-Ampel** (Risiko in 30 min) oder **konkrete
Werte/Trend**? (Kommt erst später, aber wir reservieren jetzt schon den Platz im Vertrag.)

**5. Schwellenwert-Menü (nur zur Info):**
Wie mit Lucas geklärt: Ihr baut ein **Menü zum Anpassen der Grenzwerte**. Zum Lesen geben wir
die Werte frei; das **Ändern** sichern wir später mit einer Anmeldung ab.

Wenn ihr mir zu 1–4 kurz antwortet, kann ich den Vertrag finalisieren. Danke! 🙏

---

## Interne Notizen (nicht Teil der G3-Nachricht)

- **Punkt 3 (RB-01) ist der kritischste** — G3 muss das **schriftlich bestätigen**
  (DoD DTB-26).
- Antworten zu **1–4** fließen direkt in den OpenAPI-Entwurf (DTB-19) ein; offene Stellen
  markieren wir dort als `TBD Team-Sync DTB-26`.
- **Nicht in dieser Nachricht** (betrifft G1 + Architekt, separat klären):
  Messintervall + Stale-Timeout (NF-02) und Geoposition (FA-13).

### Antworten von G3 (hier eintragen)

| # | Frage | Antwort G3 | bestätigt am |
|---|---|---|---|
| 1 | Ampel oder Messwerte | | |
| 2 | Voller Datenabruf oder nur Alarm+Prognose | | |
| 3 | RB-01 verstanden, kein Auto-Freigabe-Knopf | | |
| 4 | Prognose: Ampel oder Werte | | |
