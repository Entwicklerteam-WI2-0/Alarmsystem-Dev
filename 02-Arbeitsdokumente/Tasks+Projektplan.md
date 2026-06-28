# Projektplan Backend (G2) — Phasen · Meilensteine · Tasks

> Kanban-Quelle für Gruppe 2. Bezug: `Backend-Konzept.md`, `Schwellenwerte.md`, `Usecase-quick.md`.
> **Epics/Labels:** Architektur&API · Backend-Impl · Test&Qualität · Anforderungen&Stakeholder · Dokumentation.
> **Kanban-Spalten (Workflow):** Backlog → To-Do → In Arbeit → Review/Test → Erledigt (+ Blockiert).
> Jede Task: `[Epic] Owner-Rolle · Anf-ID · DoD · Größe(S/M/L)`. Prinzip: **contract-first**.

## 1. Phasen → Meilenstein-Zuordnung

| Phase | Inhalt | Tier | Ziel-Meilenstein | Prio |
|---|---|---|---|---|
| **P0 Setup & Fundament** | Stack, Repo-Struktur, Grundgerüst | — | M1 (Ende Wo 1) | Muss |
| **P1 Contract: API + Datenmodell** | die Naht festzurren | T0 | Entwurf M1 → **final Anfang Wo 2** | Muss |
| **P2 T0 Vertical Slice** | Ingest→Speichern→Bewertung→GET | T0 | M2 (Ende Wo 2) | Muss |
| **P3 T1 Kernfunktion** | Plausibilität, Alarme, alle Messgrößen | T1 | M2 | Muss |
| **P4 T2 Sicherheit & Betrieb** | Quittierung, Audit, Config, Historie | T2 | M3 (Ende Wo 3) | Soll |
| **P5 Integration · Test · Demo** | E2E mit G1/G3, Testprotokoll, Präsentation | — | M3 | Muss |
| **P6 T3 Erweiterung (Stretch)** | Prognose, Multi-Sensor, Fernwartung | T3 | M3 falls Zeit | Kann |

> **Kritischer Pfad:** P1 (Contract) + die Bewertungslogik in P2 auf die **verlässlichsten Köpfe**
> (Systemarchitekt + 1–2 starke Devs) legen — der Rest parallelisiert. Steht P1 spät, blockiert es alles.

## 2. Tasks je Phase

### P0 — Setup & Fundament
- **P0.1** Stack-Entscheidung treffen + begründen — `[Architektur&API]` Systemarchitekt · NF-05/NF-10 · DoD: Wahl im Entscheidungslogbuch begründet · **S** · *DB-Teil durch GL-Vorgabe gesetzt: **MySQL/MariaDB** (s. E-29 / `Surprise Anforderungen.txt`); offen bleiben nur noch Sprache/Framework/Protokoll.*
- **P0.2** Repo-Struktur anlegen (`src/...` aus Backend-Konzept §7) + README — `[Architektur&API]` Systemarchitekt · DoD: Struktur gepusht · **S**
- **P0.3** Lauffähiges Grundgerüst (Server startet, `GET /health`) — `[Backend-Impl]` Backend-Dev · DoD: `/health` → 200 · **S**
- **P0.4** Branch/PR-Konventionen + Definition of Ready/Done festlegen — `[Dokumentation]` PL/Doku · DoD: im Repo dokumentiert · **S**

### P1 — Contract: API + Datenmodell (kritisch)
- **P1.1** Datenmodell-Schema festzurren (reading/assessment/alarm/ack/threshold/audit) — `[Architektur&API]` Systemarchitekt · Schnittstelle · DoD: Schema dokumentiert + reviewed · **M**
- **P1.2** API-Spezifikation v1 (Endpoints, Request/Response, Envelope) — `[Architektur&API]` Systemarchitekt · DoD: API-Spec-Doc, OpenAPI-fähig · **M**
- **P1.3** Team-Sync: `GET /current`-Payload + `GET /health` mit G1 abstimmen (G2 = Client) + GET-Serving-Formate mit G3 — `[Anforderungen&Stakeholder]` Systemarchitekt+PL · DoD: G1 & G3 bestätigen den Contract · **M**
- **P1.4** Contract v1 **einfrieren** + kommunizieren — `[Architektur&API]` Systemarchitekt · DoD: v1 getaggt/an alle kommuniziert · **S**

### P2 — T0 Vertical Slice
- **P2.1** Poller `GET /current` (G1-Pull, Intervall ≤ 60 s) + Eingangsvalidierung — `[Backend-Impl]` Backend-Dev · FA Schnittstellen · DoD: Poll liefert Snapshot → validiert + persistiert (`measured_at` als `ts`) · **M**
- **P2.2** Persistenz `readings` (Repository-Pattern) — `[Backend-Impl]` Backend-Dev · FA Datenspeicherung · **M**
- **P2.3** Taupunkt-Berechnung (Magnus) — `[Backend-Impl]` Backend-Dev · DoD: gegen Referenzwerte geprüft · **S**
- **P2.4** **Bewertungsmodul: 4-Stufen-Logik** (Schwellenwerte §2) als reine Funktion über **3 Faktoren** (`T_s` + `ΔT` + `RH` als Kontext) — `[Backend-Impl]` Backend+Architekt · FA Risikobewertung · DoD: **beide Vorfälle korrekt** — Vorfall 1 (−2,1 °C, 92 % **Luft**-RH, **trockene** Oberfläche → `ΔT > 1,0`) ergibt **GELB** (kein Fehlalarm), Vorfall 2 (+1,2 °C, Oberfläche < 0 °C → `ΔT ≤ 0`) ergibt ORANGE/ROT. **Feuchte-Kriterium = `ΔT (T_s − T_d) ≤ 1,0 °C` (Oberfläche), NICHT Luft-`RH ≥ 90 %`** (entfernt → E-33). ROT := `T_s ≤ 0` **und** `ΔT ≤ 0` · **L**
- **P2.5** `GET /assessment/current` — `[Backend-Impl]` Backend-Dev · DoD: liefert Stufe+Werte+Datenstand · **S**
- **P2.6** Unit-Tests Bewertung (≥ 80 % Coverage, inkl. 2 Vorfälle) — `[Test&Qualität]` Test · DoD: Tests grün; **benannter Testfall Vorfall 1 → GELB** (92 % Luft-RH bei trockener Oberfläche, `ΔT > 1,0` ⇒ keine Feuchte, kein Fehlalarm — der frühere `RH ≥ 90 %`-Term hätte fälschlich ORANGE erzeugt, entfernt → E-33) · **M**

### P3 — T1 Kernfunktion
- **P3.1** Plausibilität + Stale-Erkennung (> 120 s) — `[Backend-Impl]` Backend-Dev · FA veraltete Daten · **M**
- **P3.2** Sensor-Defekt-Erkennung (Flatline/Sprung/Timeout) — `[Backend-Impl]` Backend-Dev · FA defekte Sensoren · **M**
- **P3.3** Alarm-Generierung + Schweregrad + Hysterese/Entprellung — `[Backend-Impl]` Backend-Dev · FA Alarmierung · **M**
- **P3.4** `GET /alarms` — `[Backend-Impl]` Backend-Dev · **S**
- **P3.5** Restliche Messgrößen aufnehmen (RH, Druck) — `[Backend-Impl]` Backend-Dev · **S**
- **P3.6** Integrationstest Ingest→Bewertung→API — `[Test&Qualität]` Test · **M**
- **P3.7** Fail-safe testen (Ausfall/Stale → nie GRÜN) — `[Test&Qualität]` Test · NF-01 · **S**

### P4 — T2 Sicherheit & Betrieb
- **P4.1** Quittierung `POST /alarms/{id}/ack` + `acknowledgements` — `[Backend-Impl]` Backend-Dev · FA-10/RB-01 · **M**
- **P4.2** Audit-Log (append-only, Zeitstempel) — `[Backend-Impl]` Backend-Dev · NF-09 · **M**
- **P4.3** Schwellen-Config (Laufzeit, ohne Recompile) — `[Backend-Impl]` Backend-Dev · NF-05/FA-11 · **M**
- **P4.4** Historie `GET /readings?from&to` — `[Backend-Impl]` Backend-Dev · FA-03 · **S**
- **P4.5** RB-01-Nachweis: **kein** Freigabe-/Aktor-Endpoint (Code-Review) — `[Test&Qualität]` Test/Architekt · RB-01 · **S**

### P5 — Integration · Test · Demo
- **P5.1** E2E-Integration mit **G1** (echte/sim Sensordaten) — `[Backend-Impl]` Backend+Architekt · **M**
- **P5.2** E2E-Integration mit **G3** (Frontend konsumiert API) — `[Backend-Impl]` Backend+Architekt · **M**
- **P5.3** Testprotokoll (Abnahme-Checkliste aus `Schwellenwerte.md` §3 + NFA) — `[Test&Qualität]` Test · **M**
- **P5.4** Entscheidungslogbuch finalisieren — `[Dokumentation]` Doku · **M**
- **P5.5** Abschlusspräsentation Backend-Teil + Demo-Skript — `[Dokumentation]` Doku/alle · **M**
- **P5.6** Reflexion (Methodenvergleich, Backend-Sicht) — `[Dokumentation]` Doku · **S**

### P6 — T3 Erweiterung (Stretch, nur falls Zeit)
- **P6.1** 30-min-Prognose (Trend-Extrapolation) — `[Backend-Impl]` · FA-06 · **L**
- **P6.2** Multi-Sensor/Standorte — `[Backend-Impl]` · NF-11 · **M**
- **P6.3** Fernwartung + Auth — `[Backend-Impl]` · NF-07 · **M**

## 3. Definition of Done (global, gilt für jede Task)

1. Code im PR, **Review** durch Architekt/Lead bestanden, in `main` gemerged (main bleibt lauffähig).
2. **Tests** vorhanden/grün (Bewertungslogik ≥ 80 % Coverage).
3. **Anforderungs-ID** referenziert; relevante **Schwellenwerte** eingehalten.
4. Entscheidung (falls getroffen) im **Entscheidungslogbuch** notiert.

> **Realismus-Hinweis:** Muss = P0–P3 + P5 (das ist das benotete Minimum). P4 = Soll. P6 nur Bonus.
> Bei ~11 Leuten + Ausfallrisiko: kritischen Pfad (P1, P2.4) eng besetzen, abgegrenzte Tasks (einzelne
> Endpoints, Testfälle, Doku) an den Rest verteilen — so blockiert ein Ausfall nie die Naht.
