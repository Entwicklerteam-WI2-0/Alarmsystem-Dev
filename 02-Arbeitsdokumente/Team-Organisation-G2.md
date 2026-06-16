# Team-Organisation — Gruppe 2 (Backend & Entscheidungslogik)

> Wer muss eng zusammenarbeiten, und wie organisiert sich G2 am besten?
> Bezug: Rollenverteilung (`Bild (1).png`, in CLAUDE.md), `Architektur-Stack-Konzept.md`,
> `Usecase-quick.md`, `Randbedinungsmetriken.md`. **Teamorganisation ist eigenes Bewertungskriterium.**

## 1. Team & Rollen

| Rolle | Personen | Kern-Verantwortung (DRI) |
|---|---|---|
| Teilprojektleiter | Landmann, Lucas | Scope, Prioritäten, Meilensteine, Blocker, Außenkontakt (andere Gruppen/Dozent) |
| Systemarchitekt | **Vöhringer, Lucas** · Petzold, Johannes | API + Datenmodell (die Naht), Architekturentscheidungen, Schnittstelle zu G1/G3 |
| Backend-Entwickler | Hartling, Leon · Ganter, Luca · Moritz, Andreas · Sarkhab, Arash · (Vöhringer, Lucas) | Ingest, Persistenz, **Vereisungs-Bewertungslogik**, API-Implementierung |
| Test | Mohammadi, Azezoo · Berger, Amelie | Testfälle, Definition-of-Done, Testprotokoll |
| Dokumentation | Reisi, Maryam · Ilchyshyn, Vladyslav | Entscheidungslogbuch, API-Doku, Lastenheft-Pflege |

## 2. Zusammenarbeits-Map — wer eng koppeln muss

```
                 [Teilprojektleiter] ──Scope/Prioritäten──┐
                          │                                │
   extern G1/G3 ◄──Naht──►[Systemarchitekt]──Spec/Review──►[Backend-Entwickler]
                                  │                                │
                                  └────────────┐         TDD-Schleife
                                               ▼                ▼
                          [Dokumentation]◄──liefert──►       [Test]
                          (Logbuch/API-Doku)         (DoD, Testprotokoll)
```

**Engste Kopplungen (täglich/eng):**
1. **Systemarchitekt ⇄ Backend-Entwickler** — Spec → Implementierung. Die wichtigste Achse. Devs bauen
   strikt gegen das vom Architekten definierte API/Datenmodell.
2. **Systemarchitekt ⇄ G1 Sensorik + G3 Frontend (extern)** — die **eine Naht** (API/Datenmodell).
   Lucas V. + Johannes stimmen das Schema früh mit den anderen Gruppen ab. **Kritischster Außenpunkt.**
3. **Backend-Entwickler ⇄ Test** — TDD: Tests gegen die Logik, Fehler zurück an Devs.
4. **Teilprojektleiter ⇄ Systemarchitekt** — Scope/Prioritäten/Blocker; übersetzt Außenanforderungen
   in Architektur-Aufgaben.
5. **Dokumentation ⇄ alle (v. a. Architekt + Test)** — Entscheidungen, API-Doku, Testprotokoll laufend
   einsammeln (nicht erst am Ende).

## 3. Organisationsprinzipien (für 3 Wochen + heterogenes Team)

1. **Contract-first:** Als Erstes das **T0-Datenmodell + API-Schema einfrieren** (Verantwortung
   Systemarchitekt). Danach arbeiten Sensorik, Frontend und Backend-Devs **parallel** gegen denselben
   Vertrag — das entkoppelt die Teams und ist der größte Hebel gegen Abstimmungschaos.
2. **Vertical Slice zuerst (T0):** 1 Sensor → Ingest+Speichern → Schwellwert-Bewertung → Anzeige.
   Erst wenn der Faden end-to-end läuft, Features ausbauen (T1–T3, s. `Architektur-Stack-Konzept.md`).
3. **Ein Owner pro Aufgabe (DRI), kein Komitee.** Jede Aufgabe hat genau eine verantwortliche Person.
   Entscheidungen trifft der jeweilige DRI, dokumentiert sie — keine Endlos-Abstimmung.
4. **Definition of Done = `Randbedinungsmetriken.md` §3-Checkliste.** Test verifiziert dagegen; ohne
   erfüllte DoD gilt eine Aufgabe nicht als fertig.
5. **Non-Performer entkoppeln:** Den **kritischen Pfad** (API/Datenmodell, Kern-Bewertungslogik, Ingest)
   auf die verlässlichsten Leute legen. Abgegrenzte, parallelisierbare Tasks (einzelne Endpunkte,
   Testfälle, Doku-Abschnitte) an den Rest — so blockiert ein Ausfall nie die Naht.

## 4. Cadence & Kommunikation

- **Standup** 2–3×/Woche (10 Min oder async): Was lief, was blockt, was als Nächstes.
- **Seam-Sync** 1×/Woche mit G1/G3 (Architekten-Runde) — Schema/Schnittstelle abgleichen.
- **Ein** fester Kommunikationskanal; **jede Entscheidung sofort** ins Entscheidungslogbuch
  (Verantwortung Dokumentation) — Bewertungskriterium „Nachvollziehbarkeit".

## 5. Git-Workflow (zwei Repos)

| Repo | Zweck |
|---|---|
| `technology engeneering` (GitHub `ArchiDoxx/...`) | Planung / Requirements / Doku |
| `Backend Sensor POC` | **Code** des Teams — hier wird implementiert & gepusht |

- **Offen/zu erledigen:** `Backend Sensor POC` braucht ein **gemeinsames GitHub-Remote** + Teammitglieder
  als **Collaborators** (sonst kann niemand außer dem Owner pushen).
- **Feature-Branches → Pull Request → Review (Architekt/Lead) → Merge in `main`.** `main` bleibt immer
  lauffähig. Kein direkter Push auf `main`.

## 6. Kritischer Pfad & Risiko

Der **Engpass** ist die **API/Datenmodell-Naht** (Systemarchitekt). Steht sie spät, blockiert sie G1
und G3 gleichzeitig → Gesamtprojekt-Risiko. Deshalb: Schema **vor** allem anderen festzurren, früh mit
den Nachbargruppen gegenzeichnen, dann erst breit implementieren.
