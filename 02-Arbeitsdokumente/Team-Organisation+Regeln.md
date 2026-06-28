# Team-Organisation — Gruppe 2 (Backend & Entscheidungslogik) · final

> Wer muss eng zusammenarbeiten, und wie organisiert sich G2 am besten?
> Bezug: Rollenverteilung (`Bild (1).png`, in CLAUDE.md), `Backend-Konzept.md`,
> `Usecase-quick.md`, `Schwellenwerte.md`, `teamstruktur-final.md`.
> **Teamorganisation ist eigenes Bewertungskriterium.**

## 1. Team & Rollen

| Sub-Team / Rolle | Personen | Kern-Verantwortung (DRI) |
|---|---|---|
| **Backend-Developer** | Sarkhab, Arash · Ganter, Luca | Ingest, Geschäftslogik, **Vereisungs-Bewertungslogik**, API-Implementierung |
| **Datenbank-Engineers** | Moritz, Andreas · Hartling, Leon | Datenbankschema, Repository-Pattern, Persistenz, Datenintegrität, Abfrageoptimierung |
| **Architekten** | **Vöhringer, Lucas** · Petzold, Johannes | API + Datenmodell (die Naht), Architekturentscheidungen, technische Unterstützung der aktiven Entwickler, Schnittstelle zu G1/G3 |
| **Test & Code-Review** | Mohammadi, Arezo · Berger, Amelie | Testfälle, Definition-of-Done, Testprotokoll, Code-Review |

> **Hinweis:** Die verfeinerte Aufteilung inklusive Begründung steht in
> `02-Arbeitsdokumente/teamstruktur-final.md`.

## 2. Zusammenarbeits-Map — wer eng koppeln muss

```
                 [Teilprojektleiter] ──Scope/Prioritäten──┐
                          │                                │
   extern G1/G3 ◄──Naht──►[Architekten]────Spec/Review────►[Backend-Developer]
                          │    │                           │      │
                          │    └────Schema/Repository─────►[DB-Engineers]
                          │                                  │
                          └────────────┐          TDD-/Review-Schleife
                                       ▼                        ▼
                   [Dokumentation]◄──liefert──►            [Test & Code-Review]
                   (Logbuch/API-Doku)                    (DoD, Testprotokoll)
```

**Engste Kopplungen (täglich/eng):**
1. **Architekten ⇄ Backend-Developer + Datenbank-Engineers** — Spec → Implementierung. Die wichtigste
   Achse. Devs bauen strikt gegen das vom Architekten definierte API/Datenmodell.
2. **Backend-Developer ⇄ Datenbank-Engineers** — gemeinsame Repository-Schnittstelle; DB-Engineers
   liefern die Persistenz, Backend-Developer die Verwendung in der Geschäftslogik/API.
3. **Architekten ⇄ G1 Sensorik + G3 Frontend (extern)** — die **eine Naht** (API/Datenmodell).
   Lucas V. + Johannes stimmen das Schema früh mit den anderen Gruppen ab. **Kritischster Außenpunkt.**
4. **Backend-Developer + Datenbank-Engineers ⇄ Test & Code-Review** — TDD: Tests gegen die Logik und
   Persistenz, Befunde zurück an die Entwickler.
5. **Teilprojektleiter ⇄ Architekten** — Scope/Prioritäten/Blocker; übersetzt Außenanforderungen
   in Architektur-Aufgaben.
6. **Dokumentation ⇄ alle (v. a. Architekt + Test)** — Entscheidungen, API-Doku, Testprotokoll laufend
   einsammeln (nicht erst am Ende).

## 3. Organisationsprinzipien (für 3 Wochen + heterogenes Team)

1. **Contract-first:** Als Erstes das **T0-Datenmodell + API-Schema einfrieren** (Verantwortung
   Systemarchitekt). Danach arbeiten Sensorik, Frontend und Backend-Devs **parallel** gegen denselben
   Vertrag — das entkoppelt die Teams und ist der größte Hebel gegen Abstimmungschaos.
2. **Vertical Slice zuerst (T0):** 1 Sensor → Ingest+Speichern → Schwellwert-Bewertung → Anzeige.
   Erst wenn der Faden end-to-end läuft, Features ausbauen (T1–T3, s. `Backend-Konzept.md`).
3. **Ein Owner pro Aufgabe (DRI), kein Komitee.** Jede Aufgabe hat genau eine verantwortliche Person.
   Entscheidungen trifft der jeweilige DRI, dokumentiert sie — keine Endlos-Abstimmung.
4. **Definition of Done = `Schwellenwerte.md` §3-Checkliste.** Test verifiziert dagegen; ohne
   erfüllte DoD gilt eine Aufgabe nicht als fertig.
5. **Non-Performer entkoppeln:** Den **kritischen Pfad** (API/Datenmodell, Kern-Bewertungslogik, Ingest)
   auf die verlässlichsten Leute legen. Abgegrenzte, parallelisierbare Tasks (einzelne Endpunkte,
   Testfälle, Doku-Abschnitte) an den Rest — so blockiert ein Ausfall nie die Naht.

## 4. Cadence & Kommunikation

- **Standup** 2–3×/Woche (10 Min oder async): Was lief, was blockt, was als Nächstes.
- **Team-Sync** 1×/Woche mit G1/G3 (Architekten-Runde) — Schema/Schnittstelle abgleichen.
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
