# G2 Backend — Projektplan & Jira-Backlog (internes Arbeitsdokument)

> **Zweck:** Grundlage zum Aufziehen des Jira-Projekts **DTB** (Dev-Team-Backend) und zum Verteilen der Tasks. Internes, **versioniertes** Arbeitsdokument (im Repo unter Versionskontrolle; kein benotetes Deliverable).
> **Stand:** 2026-06-22 (Woche 2; **Pull-Naht + 3-Faktor umgestellt**, vgl. E-31/E-32 + `Umstellung-Pull-3Faktor-Faktenblatt.md`) · **Quelle:** Ultracode-Workflow `g2-jira-plan` (11 Agenten, ~849k Tokens, ~20,6 Min) · Analyse → Architektur-Scan → Synthese → Verifikation.
> **NAHT-UMSTELLUNG (E-31, Pull):** Die G1→G2-Ingest-Richtung ist **Pull**, kein Push mehr. G1 stellt `GET /current` (EIN Snapshot aller aktuellen Messwerte + EIN gemeinsamer `measured_at`, UTC) und `GET /health` bereit; G2 baut einen **Poller/HTTP-Client** (Intervall ≤ 60 s), der validiert + persistiert. **Kein** von G2 gehosteter `POST /readings`-Endpoint mehr. Die G2→G3-Serving-Endpoints (`GET /assessment/current`, `GET /readings`, `GET /alarms`) **bleiben** unverändert.
> **3-FAKTOR-BEWERTUNG (E-32):** Niederschlag ist **komplett gestrichen** (Customer-Scope) — als Bewertungsfaktor UND als Datenfeld `precip_type`. Bewertet wird über **Oberflächentemp `T_s` + Taupunkt-Abstand `ΔT` + Oberflächenfeuchte (via `ΔT`)**.
> **FEUCHTE-FIX (E-33):** „Feuchte vorhanden" := `ΔT (T_s − T_d) ≤ 1,0 °C` — an die **Oberfläche** gebunden. Der frühere Luft-RH-Trigger (`RH ≥ 90 %`) ist **komplett entfernt**, weil Luftfeuchte nichts über die Oberfläche aussagt (Vorfall 1: 92 % Luftfeuchte bei trockener Oberfläche → ΔT > 1,0 → **GELB**, nicht ORANGE). `RH` (= **Luftfeuchte**) fließt nur **indirekt** über den Taupunkt `T_d` (Magnus) in `ΔT` ein; `humidity_pct` im G1-`GET /current`-Snapshot ist Luftfeuchte und reiner T_d-Input — **kein** separater Oberflächenfeuchte-Wert nötig.
> **DUMMY-SCHWELLEN:** Alle Schwellenwerte bleiben Platzhalter bis G1 liefert — ausnahmslos über `config/` parametrierbar, NIE hardcoden.
> **Owner = Empfehlung** (skill-bewusst), kein harter Assignee. Tasks gehören in den Backlog; Owner-Hinweis je Task unten.
> **⚠️ STACK-KORREKTUR (nach 2026-06-22 · E-29/E-31/E-35):** Dieses Dokument ist ein Snapshot vom 22.06. Der ursprüngliche T0-Stack **SQLite + HTTP-POST** ist **überholt**. Verbindlich: **DB = MySQL/MariaDB** (GL-Vorgabe E-29) über **rohes PyMySQL** + handgeschriebenes `schema.sql` (kein ORM/Alembic, native, kein Docker — E-35); **Ingest = Pull-Poller** gegen G1 `GET /current` (E-31), kein `POST /readings`. SQLite-Nennungen unten sind als **MySQL/MariaDB** zu lesen; rein historische Audit-Begründungen (E-08-Snapshot) bleiben als Zeitdokument stehen.

---

## 1. Verdikt der Verifikation (Go/No-Go)

**GO mit Anpassungen. Der Plan ist strukturell solide und deckt die Anforderungen weitgehend ab. Die Architektur (Contract-First, Vertical Slice, Config-Parametrierung, Fail-safe als benannte Tests) ist korrekt. Die kritischen Anpassungen sind nicht inhaltlicher, sondern sequenzierungs- und ressourcentechnischer Natur: P0 muss heute (2026-06-21) abgeschlossen werden, P6.1 (FA-06 Prognose) muss von Kann zu Soll hochgestuft und mit einem einfachen Lineare-Regression-Ansatz als eigene M3-Task eingeplant werden, und der 40%-Individualanteil muss sofort mit Personenzuweisung versehen werden.**

**Abdeckung:** WEITGEHEND ABGEDECKT, aber drei strukturelle Luecken. Alle FA/NF/RB aus Usecase-quick.md sind einem Task zugeordnet — mit diesen Ausnahmen: (1) FA-06 (30-min-Prognose mit >=30 min Vorlaufzeit) ist MUSS-Anforderung laut Usecase-quick.md §3.1, aber als P6.1 ausschliesslich unter T3/Stretch/Kann eingeplant. Das erzeugt eine harte Luecke zum Pruefungs-Minimum. (2) NF-02 (Datenaktualitaet/Latenz, Zielwert TBD) hat keinen expliziten Task, der den Zielwert festlegt und im Entscheidungslogbuch dokumentiert — nur ein offener Punkt in openDecisions. (3) FA-13 (Geoposition je Wetterstation, Kann-Anforderung) hat keinen Task, der die Klaerung im Seam-Sync formalisiert und das Ergebnis ins Datenmodell uebernimmt. Alle Pflicht-Deliverables laut Pruefungsleistung Anforderungen.txt (Woche 2: Datenmodell, API-Dokumentation, Vereisungslogik) sind ueber P1+P2+E-07 abgedeckt. Der 40%-Individualanteil (Entscheidungslogbuch, je Person) ist als P5.4 geplant, aber nicht verteilt — kein Task weist den 11 Einzelpersonen ihre Reflexion zu.

**Machbarkeit:** M2 KRITISCH GEFAEHRDET, M3 machbar mit Abstrichen. Zentrale Befunde: (1) Null Produktionscode vorhanden (04-Source-code/source/test-suite/dfghjk.txt als einziger Inhalt). Scaffolding (P0.2+P0.3) haette M1-Ende (2026-06-19) erledigt sein muessen — ist es nicht. Das kostet heute Montag einen vollen Tag bevor P1 beginnen kann. (2) Lucas als einziger echter Backend-Dev auf P0+P1.1+P1.2+P1.4+P2.4+P5.1+P5.2: sieben kritische Pfad-Tasks, bei realistisch 30 Produktiv-Stunden/Woche. Das ist physikalisch nicht vollstaendig in 5 Tagen moeglich. Petzold kann P1.2 und P2.2 uebernehmen, aber P2.4 (Bewertungsmodul, Groesse L) ist nicht delegierbar. (3) P2.4 (Groesse L, ~40-60h) soll bis Freitag 2026-06-26 fertig + getestet (>=80% Coverage) sein — das setzt voraus, dass Lucas ab Mittwoch 08:00 ausschliesslich an P2.4 arbeitet, was nur moeglich ist wenn P1 bis Dienstag Abend vollstaendig abgeschlossen ist. (4) P3 (T1 Kernfunktion) als M2-Ziel bei gleichzeitigem P2: realistisch NUR wenn Petzold P3.1/3.2/3.3 vollautomatisch uebernimmt, waehrend Lucas P2.4 macht. (5) teamstruktur-final.md nennt 'Arash, Luca' als Backend-Developer — aber im Plan werden Hartling und Ganter als Anfaenger behandelt, was nicht konsistent ist. Die tatsaechliche Verfuegbarkeit von Arash/Sarkhab fuer Bewertungslogik ist unklar. (6) P6.1 (Prognose, FA-06=MUSS) als T3/Stretch ist fachlich riskant — ohne Prognose fehlt ein dokumentiertes MUSS-Feature im Prototyp fuer M3.

### Sofort-Anpassungen (aus Verifikation)
- **Prioritaetsaenderung:** P6.1 (30-min-Prognose) von T3/Kann auf T1/Soll mit M3 hochstufen. Implementierungsansatz vereinfachen: 3-Punkt-Lineare-Regression ueber T_s-Zeitreihe der letzten 30 Minuten statt ARIMA/komplexe Methode. Das ist eine S-Groesse (~1 Tag Lucas oder Petzold), nicht L. Ohne diese Anpassung ist FA-06 (MUSS laut Usecase-quick.md) nicht im Prototyp. Epic E-07 oder E-03 erweitern.
- **Owner-Korrektur kritischer Pfad:** P2.4 (Bewertungsmodul) steht als Owner 'Lucas Voehringer (Backend+Architekt, DRI kritischer Pfad)' — korrekt. Aber P2.1 (Poller-Client gegen G1 `GET /current`) ist als Owner 'Hartling oder Ganter (Anfaenger)' eingeplant mit Abhaengigkeit von P2.4 und P2.2. Korrektur: P2.1 Owner = Arash Sarkhab (Backend-Developer laut teamstruktur-final.md), NICHT Hartling/Ganter. Hartling und Ganter bekommen P3.4 (GET /alarms) und P4.4 (GET /readings?from&to) als wirklich abgegrenzte, von anderen Tasks unabhaengige Endpoints.
- **Milestone-Anpassung Realismus:** P3 (T1 Kernfunktion) als M2-Ziel ist unrealistisch bei null Produktionscode am 2026-06-21. Empfehlung: P3.1+P3.2+P3.3 explizit zu M3-Beginn (Woche 3 Mo/Di) verschieben, P3.4+P3.5 in Woche 2 parallel zu P2 halten. Den Spillover-Hinweis im Plan ('M2 mit Spillover M3 realistisch') in eine harte Abgrenzung umwandeln: P3.3 (Alarm-Generierung) ist M3-Task, nicht M2-Task. Das entlastet den kritischen Pfad ohne die Pruefungsanforderungen zu verletzen (Zeitplan.txt M2 fordert 'funktionierende Einzelmodule' — T0 Vertical Slice reicht dafuer).
- **Task-Scope-Fehler korrigieren:** P4.3 (Schwellen-Config) steht als M3-Deliverable, ist aber als Abhaengigkeit von P2.4 eingetragen ('dependsOn: [P2.4, P4.3]'). Das ist zirkulaer falsch. Korrektur: P4.3 muss VOR P2.4 kommen, da assessment() parametrierbar sein muss. Config-Grundstruktur (config/thresholds.json + src/config/loader.py) in E-07 voranziehen auf M1/P0-Zeitfenster und als ENABLER fuer P2.4 markieren, nicht als Nachfolger.
- **Bewertungslogik-Praezisierung Vorfall 2:** Plan benennt Vorfall 2 mehrfach als '+1,2 °C Luft, T_s<0 → ORANGE/ROT'. Schwellenwerte.md §2 (3-Faktor, E-32/E-33) sagt: ROT wenn T_s<=0 UND DeltaT<=0; 'Feuchte vorhanden' := DeltaT (T_s − T_d) <= 1,0 °C — der frühere Luft-RH-Term (RH>=90%) ist **komplett entfernt** (E-33), weil Luftfeuchte nichts über die Oberfläche aussagt. Fuer Vorfall 2 (Reif, naechliche Abstrahlung) ist ROT korrekt (DeltaT<=0 bei Reifbildung). Der Test test_vorfall_2_ice_at_positive_air_temp() muss daher spezifisch 'ROT' erwarten, nicht 'ORANGE oder ROT'. DoD in P2.4 und P2.6 entsprechend praezisieren.
- **CI/CD-Luecke:** GitHub hat zwei Workflows (claude-code-review.yml, claude.yml), aber KEINEN pytest-Gate. E-08-TestCI hat die richtige Idee, aber P0.4 (DoD) muss explizit .github/workflows/test.yml als Pflicht-Deliverable enthalten. Alternativ: Petzold schreibt test.yml heute Mo als ersten PR (15 Minuten Aufwand), damit alle weiteren PRs automatisch abgesichert sind. Das fehlt als explizites Task-Deliverable in P0.
- **Entscheidungslogbuch-Individualanteil strukturieren:** P5.4 ('Entscheidungslogbuch finalisieren') ist als Gruppen-Task modelliert. Aber 40% der Note ist individuelle Reflexion je Person (Pruefungsleistung Anforderungen.txt). Korrektur: P5.4 in zwei Sub-Tasks aufteilen: (a) Gruppen-Entscheidungslogbuch (AE/E-Eintraege, kollektiv), (b) 11 individuelle Reflexionen (je 4-6 Seiten, DRI = jeweilige Person, Deadline = M3). Jeder der 11 Personen muss einer konkreten Entscheidung aus E-01..E-27 zugewiesen werden, die sie selbst reflektieren. Lucas' Entscheidungslog deckt bereits E-01..E-28, ist aber noch nicht auf andere Personen verteilt.
- **Fail-safe Ownership-Klaerung:** Plan weist Fail-safe-Verantwortung diffus zu: P3.1 an Petzold, P3.7 an Mohammadi/Berger, aber die Architektur-Entscheidung 'wer ist verantwortlich fuer den sicheren Zustand' (Ingest vs. Storage vs. Assessment) fehlt als expliziter ADR-Eintrag. E-29 (Fail-safe Multi-Layer wie im Scan beschrieben) sollte als eigener Task ergaenzt werden mit DRI Lucas, bevor P3.1/P3.2 implementiert werden.
- **Stack-Entscheidung formalisieren:** E-08 im Entscheidungslog-Lucas.md hat Status 'offen' und 'hängt an Team-Kompetenz' — obwohl .venv seit 2026-06-17 FastAPI+SQLite+pytest installiert hat. Das ist widerspruelich und pruefungsrelevant (Bewertungskriterium: Nachvollziehbarkeit technischer Entscheidungen). P0.1 muss als Ergebnis einen abgeschlossenen E-08-Eintrag im Entscheidungslog produzieren, der FastAPI+SQLite+HTTP-POST begruendet (Team-Kompetenz: bekanntes Oekosystem; Deployment: SQLite als Datei, kein Server; HTTP-POST: G1 liefert HTTP, kein MQTT-Broker). Das ist 30 Minuten Schreiben, kein Tech-Aufwand.

### Abdeckungslücken / Nachzuziehen
- FA-06 (30-min-Prognose) ist MUSS-Anforderung laut Usecase-quick.md §3.1 und Pruefungsleistung Anforderungen.txt (Deliverable 'Vereisungslogik' Woche 2 schliesst Vorwarnlogik ein), ist aber als P6.1 ausschliesslich unter T3/Stretch/Kann geplant. Ohne Prognose fehlt ein MUSS-Feature im M3-Prototyp.
- NF-02 (Datenaktualitaet/Latenz: Messintervall + max. Latenz) hat keinen Task, der den Zielwert verbindlich festlegt und im Entscheidungslogbuch dokumentiert. Aktuell nur als offener Punkt ohne Owner und Deadline.
- FA-13 (Geoposition je Wetterstation) hat keinen Task, der die Entscheidung aus dem Seam-Sync (ortsfestes Stationsdatum vs. pro Reading) formalisiert und das Ergebnis im Datenmodell verankert.
- 40%-Individualleistung (Pruefungsleistung Anforderungen.txt): P5.4 plant Entscheidungslogbuch als Gruppenaufgabe, aber die individuelle Reflexion (4-6 Seiten je Person, 11 Personen) hat keinen einzigen Task mit Personenzuweisung und Deadline. Ohne explizite Zuweisung pro Person drohen individuelle Notenabzuege.
- Systemkontext-Dokument (Deliverable Woche 1 laut Pruefungsleistung Anforderungen.txt): Existiert nicht explizit im Repo — Backend-Konzept.md §1 ist Kandidat, aber kein Task verifiziert oder erstellt das formale Systemkontextdiagramm.
- Deployment-/Betriebsmodell AE-01 (Lokal vs. Cloud) ist als offene Entscheidung gelistet, aber kein Task erzwingt eine verbindliche Entscheidung vor M2. Ohne Entscheidung fehlt eine Betriebsanleitung fuer die Live-Demo.
- NF-07 (Zugriffsschutz/Auth fuer Config-Endpoint) ist als NF-Stub fuer M2 erwaehnt, hat aber keinen konkreten Minimal-Task (z.B. einfacher API-Key-Check fuer POST /config), der verhindert dass der Config-Endpoint offen erreichbar ist.

---

## 2. Überblick

Alarmsystem Vereisungserkennung — Backend Gruppe 2 (G2). Prototyp zur Erfassung und Bewertung von Vereisungsbedingungen auf der Startbahn des Flughafens ANR (3-wöchiges Projekt). Stack T0 (Python + FastAPI + **MySQL/MariaDB**, rohes PyMySQL — E-29/E-35) ist gewählt; die G1→G2-Naht ist **Pull** (G2 = HTTP-Client/Poller gegen G1s `GET /current`, vgl. E-31). Kritischer Pfad: API/Datenmodell-Naht P1 (bis Woche 2, Di fällig) + Bewertungsmodul P2.4 (3-Faktor: T_s + ΔT + RH) mit beiden Vorfall-Testfällen + Fail-safe. Meilenstein M2 (Ende Woche 2, ca. 2026-06-26) ist risikoreich: kein Produktionscode vorhanden, Lucas als Single-Point-of-Failure auf kritischem Pfad.

**Kritischer Pfad:** P0.2–P0.3 (Scaffolding, Mo Woche 2) → P1.1–P1.4 (Contract, Mo/Di Woche 2) → Seam-Sync (Di 08:00) → P2.1–P2.6 (Vertical Slice, Mi–Fr Woche 2) → M2 Deadline (Fr 17:00 2026-06-26). Kein Überschreitung, alle PRs gemergt auf main bis Do 17:00 damit Fr für Abgabe-Freeze Zeit bleibt. Reservezeit: <12h für Rollback/Hotfixes. P3 Spillover zu Woche 3 akzeptiert. **Engpässe:** Lucas (P0+P1+P2.4+P5.1/5.2), Test-Team (P2.6+P3.6+P3.7+P5.3), DB-Engineers (P2.2+P3.1/3.2). **Mitigation:** Pair-Programming Mo/Di, Parallelisierung kleiner Tasks, TDD-Ansatz (Testfälle vor Code).

**Sequencing:** **Kritischer Pfad (sequenziell):** P0 (Scaffolding, 1–2 Tage) → P1 (Contract, Mo/Di Woche 2, 2–3 Tage) → P2 (Vertical Slice, Mi–Fr Woche 2, 3–4 Tage) ⇒ M2-Deadline (2026-06-26). **Parallel nach P1.4 (Contract eingefror):** P3 (T1 Kernfunktion, Mi Woche 2 – Mi Woche 3, mit Spillover), P4 (T2 Ops, Di Woche 3 – Do Woche 3), P5 (Integration/Demo/Doku, Do–Fr Woche 3), P6 (T3 Stretch, nur wenn Zeit). **Täglich Standup erforderlich:** Kritischer Pfad-Status (Traffic-Light), Blocker früh eskalieren. **Weekly Seam-Sync mit G1+G3:** Mo oder Di je Woche, schriftlich dokumentieren. **Entscheidungslogbuch laufend:** nicht erst Woche 3. Jedes Teamitglied ≥1 Entscheidung (40% Individualleistung).

---

## 3. Phasen & Zeitplan

### P0 — Setup & Fundament  ·  M1
**Zeitfenster:** Woche 1 (vor 2026-06-19, laut Zeitplan M1-Ende)

Repo-Struktur, Stack-Entscheidung, lauffähiges Grundgerüst (GET /health), Branch/PR-Konventionen etablieren. Enabler für alle nachfolgenden Phasen.

**Exit-Kriterien:**
- src/, tests/, config/ Ordnerstruktur angelegt und gepusht
- GET /health Endpoint startet mit HTTP 200
- Stack-Entscheidung (Python+FastAPI+MySQL/MariaDB, rohes PyMySQL — E-29/E-35) im Entscheidungslogbuch begründet
- Branch/PR-Konventionen + DoD in README.md dokumentiert

### P1 — Contract: API + Datenmodell (KRITISCH)  ·  M2
**Zeitfenster:** Woche 2, Montag/Dienstag (2026-06-22 bis ca. 2026-06-24, laut Zeitplan 'API Spec final' Di)

Einfrieren der Naht zwischen G2/G1 und G2/G3. Formale API-Spezifikation v1, Datenmodell-Schema, Seam-Sync mit G1 (Ingest-Payload) und G3 (GET-Formate). Alles blockiert, bis P1.4 final ist.

**Exit-Kriterien:**
- Datenmodell-Schema (6 Entitäten: reading, assessment, alarm, acknowledgement, threshold_set, audit_log) dokumentiert + reviewed
- OpenAPI 3.0 Spezifikation (YAML/JSON) mit ≥15 Endpoints/Operationen vorhanden
- Seam-Sync mit G1 + G3 durchgeführt, beide Gruppen schriftlich bestätigt
- Contract v1 getaggt und an alle Gruppen kommuniziert, PR gemergt

### P2 — T0 Vertical Slice (Ingest→Bewertung→API)  ·  M2
**Zeitfenster:** Woche 2, Mittwoch bis Freitag (2026-06-25 bis 2026-06-26, Deadline M2)

Funktionsfähiger T0-Stack: Datenbeschaffung via Poller-Client gegen G1s `GET /current` (Snapshot + `measured_at`), Persistenz, Bewertungslogik, GET /assessment/current mit ≥80% Unit-Test-Coverage. Beide Vorfälle (−2,1 °C, +1,2 °C) als grüne Testfälle.

**Exit-Kriterien:**
- Poller ruft G1s `GET /current` (≤ 60 s) ab, validiert (Bereich, Stale via `measured_at`, Defekt) → persistiert
- GET /assessment/current liefert risk_level (green|yellow|orange|red) + Erklärung
- Bewertungsmodul als reine Funktion (assessment/core.py), 3-Faktor (T_s + ΔT + RH), parametrierbar aus config/thresholds.json
- Unit-Tests ≥80% Coverage mit benannten Vorfall-Testfällen (test_vorfall_1_dry_cold, test_vorfall_2_ice_at_positive_air_temp)
- Fail-safe-Test: Stale/Ausfall → nie GRÜN

### P3 — T1 Kernfunktion (Plausibilität, Alarme, Messgrößen)  ·  M2 (mit Spillover zu M3 realistisch)
**Zeitfenster:** Woche 2, parallel zu P2, oder Woche 2/3 Überlauf (2026-06-25 bis Anfang Woche 3)

Stale/Defekt-Erkennung, Alarm-Generierung mit Hysterese, alle Messgrößen (RH, Druck), Integrationstests, Fail-safe-Test konkretisiert.

**Exit-Kriterien:**
- P3.1: Stale-Erkennung > 180s, Plausibilitäts-Gate funktioniert
- P3.2: Sensor-Defekt (Flatline/Sprung/Timeout) erkannt, gekennzeichnet
- P3.3: Alarm-Generierung ab ORANGE mit Schweregrad + Hysterese/Entprellung
- P3.4/P3.5: GET /alarms, alle Messgrößen RH/Druck im Poller-Ingest vorhanden
- P3.6: Integrationstests Ingest→Bewertung→API grün
- P3.7: Fail-safe-Test konkretisiert (5 Szenarios: stale, out-of-range, flatline, no-data, network-delay)

### P4 — T2 Sicherheit & Betrieb (Quittierung, Audit, Config, Historie)  ·  M3
**Zeitfenster:** Woche 3 (2026-06-26 bis Anfang Woche 3, oder später)

Alarm-Quittierung, append-only Audit-Log, Schwellen-Config-Endpoint (Laufzeit-Parametrierbarkeit), Historie-Endpoint, RB-01-Nachweis (kein Aktor-Endpoint). Soll-Prio für M2, Muss für M3.

**Exit-Kriterien:**
- P4.1: POST /alarms/{id}/ack + acknowledgements-Tabelle append-only
- P4.2: audit_log mit event_type, actor, ts, payload (append-only, Index auf ts)
- P4.3: Config-Endpoint (laufzeitänderbar, ohne Recompile; threshold_set Versioning)
- P4.4: GET /readings?from=&to= (parametrisierte Historie)
- P4.5: Code-Review RB-01 bestätigt, keine Freigabe-/Aktor-Endpoints vorhanden

### P5 — Integration, Test, Demo  ·  M3
**Zeitfenster:** Woche 3 (2026-06-26 bis 2026-07-03, geschätzt M3-Ende, exaktes Datum TBD in Zeitplan)

E2E-Integration mit G1 (echte/sim Daten) + G3 (Frontend konsumiert API), Testprotokoll (Abnahme-Checkliste), Entscheidungslogbuch finalisieren, Abschluss-Präsentation + Demo-Skript, Reflexion (Methodenvergleich).

**Exit-Kriterien:**
- P5.1: E2E mit G1 läuft, realistische oder simulierte Sensordaten fließen end-to-end
- P5.2: E2E mit G3 läuft, Frontend konsumiert GET /assessment/current + weitere Endpoints
- P5.3: Testprotokoll vollständig (Abnahme-Checkliste aus Schwellenwerte.md §3 + NFA, ≥80% Coverage bestätigt)
- P5.4: Entscheidungslogbuch (alle E-Einträge inkl. AE-01/AE-02 finalisiert, jedes Teamnitglied hat ≥1 Entscheidung dokumentiert)
- P5.5: Abschluss-Präsentation (Backend-Teil, Live-Demo, Demo-Skript)
- P5.6: Reflexion (Methodenvergleich Wasserfall G2 vs. Scrum G3, Learnings)

### P6 — T3 Erweiterung (Stretch, nur falls Zeit)  ·  M3 (optional, kein Muss)
**Zeitfenster:** Woche 3, falls Zeit (2026-07-01 bis 2026-07-03)

30-min-Prognose (Trend-Extrapolation), Multi-Sensor/Standorte, Fernwartung + Auth. Bonus-Ziele bei verbleibender Kapazität in Woche 3.

**Exit-Kriterien:**
- P6.1: 30-min-Trend-Prognose (T_s/T_d/Drucktendenz-Extrapolation) als Modul vorhanden
- P6.2: Multi-Sensor-Support (sensor_id in readings, aggregierte assessment-Ausgabe)
- P6.3: Fernwartung + Auth (JWT oder Basic-Auth für privilegierte Endpoints)

---

## 4. KPIs

| KPI | Ziel | Messung |
|---|---|---|
| M2-Deadline Einhaltung | 100% | P0–P3 Abschluss bis 2026-06-26 17:00 (Einfrieren main-Branch für M2-Abgabe) |
| API/Datenmodell-Naht eingefroren | P1.4 bis 2026-06-24 | Contract v1 getaggt in Git, schriftliche Bestätigung von G1/G3, PR gemergt auf main |
| Bewertungsmodul mit Vorfällen | Beide Testfälle (VF-1: −2,1 °C trocken→GELB; VF-2: +1,2 °C Luft, T_s<0→ROT) grün | pytest test_vorfall_1_* und test_vorfall_2_* bestanden, Coverage ≥80% |
| Fail-safe-Test vorhanden | P3.7 definiert + implementiert: 5 Szenarios (stale, out-of-range, flatline, no-data, network-delay) → alle GELB/nie GRÜN | pytest test_fail_safe_* bestanden |
| Code Coverage assessment/ | ≥80% | pytest --cov=src/assessment --cov-report=term-missing zeigt ≥80% line coverage |
| Schwellen parametrierbar | Alle Schwellwerte aus config/thresholds.json geladen, keine Hardcodes | grep -r '>\s*[0-9.]+' src/ zeigt keine Literal-Schwellen in Bewertungslogik |
| Projektrichtlinie RB-01 eingehalten | 0 Freigabe-/Aktor-Endpoints in API | Code-Review + Lint-Hook prüft auf Strings 'unlock|freigabe|sperr|execute' in src/api/ |
| Entscheidungslogbuch mit Beteiligten | ≥6 Entscheidungen dokumentiert, ≥5 unterschiedliche Personen als Autoren | git log --all --format=%aN -- Entscheidungslog*.md | sort | uniq | wc -l |
| CI/CD Green Gate | Alle PRs müssen pytest + coverage bestanden haben vor Merge | .github/workflows/test.yml erfolgreich + Status-Check required im main-Branch |

---

## 5. Risiken

| Risiko | Schwere | Mitigation |
|---|---|---|
| R1: Lucas-Bottleneck auf kritischem Pfad (P1 + P2.4) | Critical | Pair-Programming Lucas + Petzold für P1.1/P1.2 (Mo/Di Woche 2). Hartling/Ganter on separate abgegrenzten Tasks (P3.4, P3.5). Backup: Johannes Petzold kennt API-Design, kann P1.2 übernehmen falls Lucas ausfällt. |
| R2: Kein Produktionscode vorhanden (src/, tests/ leer) | Critical | P0.2 + P0.3 SOFORT (Mo 08:00 Woche 2). Scaffolding ist 3–4h Arbeit, muss VOR P1/P2 done sein. Nicht blockieren lassen. |
| R3: G1-Finalwerte ausstehend (~2 Tage), Schwellen sind DUMMIES | High | Alle Schwellen parametrierbar halten (config/thresholds.json, NICHT hardcoden). Sobald G1-Werte kommen: config aktualisieren, Tests rerun (kein Code-Change nötig). Grep-Hook gegen Hardcodes setzen. |
| R4: P1 (Contract) nicht bis Di Woche 2 eingefroren → G1/G3 blockiert | Critical | Lucas/Petzold Pair-Programmierung Mo/Di. Seam-Sync Di 08:00 durchführen. OpenAPI-Export bis Di 17:00. |
| R5: Zeitbombe M2 (Deadline Ende Woche 2, nur 5 Tage) | Critical | Realistisches Spillover: P3 (T1) wird teilweise zu M3 (Woche 3). Fokus: P0–P2.6 MUSS bis Do Woche 2 done sein, P3.1–P3.7 dann teils parallel teils Woche 3. Kanban-Board (Jira) mit täglichem Standup + Velocity-Tracking. |
| R6: Seam-Sync nicht durchgeführt → API-Payload-Variationen offen | High | Termin verbindlich Mo 10:00 oder Di 08:00 Woche 2 blockieren. Protokoll schriftlich (E-Mail, Issue mit Label 'seam-sync-confirmed'). |
| R7: Fail-safe NF-01 wird vergessen oder nicht testbar implementiert | High | P3.7 ist explizite Testfälle-Task (5 Szenarien). DoD: alle 5 Tests grün. Code-Review-Gate: 'Keine GRÜN bei Ausfall'. |
| R8: Bewertungsmodul P2.4 (Größe L, kritischer Pfad) läuft über | High | Zeitschätzung ~40–60h bei Lucas allein. Mit Petzold-Support (Code-Review, Config-Setup) reduzierbar auf ~30h. Mo/Di P0+P1 parallelisieren, Mi–Fr P2.4 intensive Focus. Backup-Plan: Simple Version Mi–Do, Refinement Fr/Woche 3. |
| R9: RB-01 wird durch Versehen in Code-Review übersehen | Medium | Pre-Commit-Hook + GitHub-Action Lint vor Merge (suche nach 'unlock|freigabe|sperr|execute'). P4.5 als explizite Review-Task. Entscheidungslog E-15: RB-01 Enforcement dokumentiert. |
| R10: API-Versioning + Breaking-Changes unklar → Integrations-Chaos | Medium | P1.2: Versionierungsstrategie (z.B. /v1/ in URL). P1.3: Seam-Sync klären, wie neue GET-Parameter eingeführt werden (z.B. /v1/assessment/current?version=2). Dokumentation in CHANGELOG.md. |

---

## 6. Offene Entscheidungen

- AE-01: Lokal vs. Cloud Betriebsmodell — IT bevorzugt lokal (kein Cloud-Overhead), sieht aber Cloud-Wartungsvorteile. Entscheidung bis M2 treffen + ins Entscheidungslogbuch dokumentieren.
- AE-02: Fernzugriff (Umfang, Sicherheit) — Fernzugriff als 'wäre praktisch' erwähnt (Wunsch/Kann, kein Muss). Umfang offen. T3-Feature. Abh. von AE-01.
- NF-02-Zielwert: Datenaktualität/Latenz (Messintervall + max. Latenz) nicht definiert. Muss vor M2 Pipeline-Bau festgelegt werden. Seam-Sync P1.3 klären.
- NF-04-Zielwert: Sensorgenauigkeit, FP/FN-Rate Zielwerte (FP<1%, FN=0%) sind Designziele, keine harten Metriken. Validierung gegen Referenzmessung offen.
- NF-10-Budget: Kein konkreter Budgetrahmen definiert. WX-500 ~4.800 EUR/St., ggf. 10 Stationen. Budget-Entscheidung ausstehend.
- FA-05-Präzisierung: 'Vereisung erkennen' noch nicht präzisiert. Akzeptanzkriterium: Bewertungslogik zeigt auslösende Messgröße + Schwellwert deutlich (driving_factor + explanation).

---

## 7. Architektur-/Logik-Scan — Kernbefunde

### Linse: Contract- & Architektur-Kohärenz | API/Datenmodell-Naht G2 (M2-Blockers)

_CRITICAL MISALIGNMENT: G2 hat dokumentierte Architektur + klare Anforderungen, aber ZERO Code (src/tests leer). Die API/Datenmodell-Naht ist nicht eingefroren; P1 ist verbindlich bis Ende Woche 2 (Montag/Dienstag), aber noch nicht begonnen. Der assessment/-Kern ist die Höhe des Risikos: beide Vorfälle müssen als benannte grüne Testfälle fungieren, aber die schwellenwert-ZAHLEN sind DUMMIES (G1-Finalwerte ausstehend ~2 Tage). Betriebsmodell (AE-01/AE-02) unbegründet offen. Die Architektur ist strukturell tragfähig; die kritischen Lücken sind Timing + Contract-Freeze + Testfälle-Reifheit, nicht inhaltliche Widersprüche._

- **[CRITICAL] API/Datenmodell-Naht P1 nicht eingefroren, fällig SOFORT (Mo/Di Woche 2)** _(betrifft: G1 (Ingest-Payload unklar), G3 (GET-Formate unklar), paralleles Arbeiten blockiert)_
  - → Lucas + Johannes müssen Mo/Di die gesamte P1 (P1.1–P1.4) abschließen, bevor ein einziger Zeile Code-PR für P2 anfange. Seam-Sync mit G1+G3 muss bis Di 17:00 Uhr stattgefunden haben. Fallback: formale OpenAPI-Spezifikation schreiben und die 6 kritischen Felder (reading-Ingest + assessment-Response) in .md + Schema als JSON-Beispiel dokumentieren.
- **[CRITICAL] Null Produktionscode vorhanden: src/ + tests/ komplett leer** _(betrifft: P2 kann nicht parallel zu P1 laufen (Blockedependency), kritischer Pfad wird sequenzialisiert statt parallelisiert)_
  - → P0 sofort (heute/Mo) abschließen: 2-3 Stunden für Ordnerstruktur src/ingest/.../tests/ + pyproject.toml + /health-Endpoint. Dann P1 parallel zu P2 über gemeinsame .gitignore + feature-branches.gitignore. Ohne P0-heute können P2.1–P2.6 nicht beginnen.
- **[CRITICAL] Datennaht G1↔G2 unspezifisch: G1s `GET /current`-Snapshot-Shape nicht final** _(betrifft: G2 weiß nicht exakt, welche Felder G1 im Snapshot liefert; G2 kann keine robuste Validierung schreiben; G3 weiß nicht, welche Felder in GET /assessment/current zu erwarten sind)_
  - → P1.1–P1.2 als blockedPRIORITY: formale API-Spec (OpenAPI 3.1 JSON oder minimal Markdown + JSON-Schema) mit: (1) **Konsum von G1s `GET /current`** — EIN Snapshot aller aktuellen Messwerte + gemeinsamer `measured_at` (UTC/ISO-8601): erwartete Felder (sensor_id, measured_at, surface_temp_c, air_temp_c, humidity_pct, pressure_hpa, status); plus `GET /health` als Erreichbarkeits-Check. Feldnamen final im Seam-Sync (G1 = Server, definiert den Shape). (2) GET /assessment/current: Response {ts, risk_level, driving_factor, explanation, reading_id, threshold_set_id}. (3) Fehlerbehandlung + Status-Codes (inkl. Poller-Timeout/503 von G1). (4) Versioning-Strategie (z.B. /v1/).
- **[CRITICAL] Bewertungsmodul P2.4 ist größte einzelne Risikoaufgabe; beide Vorfälle als benannte Testfälle still offen** _(betrifft: DoD für P2.4 kann nicht erfüllt werden ohne echte Schwellenwerte; Testschreiben läuft gegen Dummy-Werte; Risiko: am Freitag (M2) Test bestanden, am Montag mit realen Werten fehlgeschlagen)_
  - → Parallel zu P1: (1) Beide Vorfälle als parametrisierte pytest-Testfälle schreiben, mit Dummy-Schwellenwerten ausfüllen (z.B. über Config-Fixture). (2) assessment() als reine Funktion (ggf. mit Mock-Config) implementieren. (3) sobald G1-Finalwerte eintreffen: Config aktualisieren + Tests rerun (kein Code-Change nötig dank Parametrierbarkeit). Fail-safe-Test (Stale → GELB) ebenfalls schreiben, auch ohne finale Schwellen. Ziel: >=80% Coverage bis M2, beide VF-Tests grün.
- **[HIGH] Betriebsmodell AE-01/AE-02 unbegründet offen, impactet NF-03/NF-07/K9** _(betrifft: Architektur-Entscheidung müsste vor M2 dokumentiert sein, um Betriebsbetrieb-szenarios (Docker, systemd, Netzwerk-Config) zu validieren)_
  - → E-28 ins Entscheidungslog: 'Lokal mit Raspberry-Pi als T0 (preiswert, Demo-gültig, Single-PoF akzeptiert); Cloud (AWS/Azure) als T2-Erweiterung später'. Begründung: (1) 3-Woche Projekt, (2) kein Operations-Team, (3) lokale Wartung einfacher für Demo. Notieren: bei Produktivübergang müsste Hochverfügbarkeit (AE-01 Cloud) entschieden werden. NF-07-Stub (Auth-Placeholder) reicht für M2.
- **[HIGH] G1-Schwellenwert-Finalwerte ausstehend (~2 Tage); Config-Parametrierbarkeit noch nicht implementiert** _(betrifft: Testmethodologie (Test gegen Config-Fixture vs. Hard-coded Schwellen), M2-DoD-Akzeptanz (echte vs. Dummy-Schwellen), Vertraubarkeit der Bewertungslogik)_
  - → SOFORT: (1) config/thresholds.example.json mit Dummy-Werten anlegen (aus Schwellenwerte.md §2). (2) src/config/__init__.py mit Config-Loader schreiben (YAML/JSON-Read, Fallback auf Defaults). (3) P2.4 assessment() erhält config als Argument oder liest aus sys-Config (DI-Pattern). (4) P2.6 Unit-Tests verwenden pytest.mark.parametrize über Config-Varianten (z.B. '@pytest.fixture(params=[config_dummy, config_conservative])'). Sobald G1-Werte eintreffen: config/thresholds.json aktualisieren, Tests rerun, kein Code-Änderung nötig. P4.3 (Laufzeit-UI) kann danach gebaut werden.
- **[HIGH] Seam-Sync mit G1+G3 nicht stattgefunden (1×/Woche laut Team-Organisation, aber noch nicht durchgeführt)** _(betrifft: Kommunikations-Fehler zwischen G1/G2/G3 in der kritischsten Phase (Contract-Lock-in Woche 2))_
  - → Lucas/Johannes müssen heute (Mo) oder spätestens Di 09:00 den Seam-Sync durchführen (virtuelles Treffen oder schriftliche Bestätigung je Gruppe). Agenda: (1) G1s `GET /current`-Snapshot-Felder + Formate (welche Messwerte, gemeinsamer `measured_at` in UTC, `status`-Encoding) + `GET /health`-Vertrag (200=ok/503=fault) + G2-Poll-Intervall (≤ 60 s) abstimmen. (2) GET /assessment/current Response. (3) FA-13 Geoposition: wie und wo. Schriftliche Bestätigung per E-Mail an Architekten + GitHub-Issue labeln 'seam-sync-confirmed' oder ähnlich. Ohne Mo/Di-Bestätigung: P1.4 (Freeze) nicht möglich → M2 blockiert.
- **[HIGH] OpenAPI-Spezifikation als verbindliches Deliverable D-08 noch nicht erstellt** _(betrifft: Interop-Testing zwischen G1/G2/G3 fehlt visuelle Schnittstellen-Dokumentation, Demo-API-Docs)_
  - → P1.2 wird zum schreiben einer OpenAPI 3.1 JSON-Datei erweitert (z.B. src/openapi.json oder docs/api-v1.json). Minimales Gerüst: (1) info{title, version}, (2) paths (G2-Serving): /health, /assessment/current (GET), /alarms (GET, T1), /readings (GET-Historie, T1) — die G1-Naht selbst ist KEIN G2-Endpoint mehr, sondern der dokumentierte Konsum von G1s `GET /current` + `GET /health` durch den Poller. (3) components.schemas: Reading, Assessment, Alarm, Error. Mit FastAPI + Pydantic: `from fastapi.openapi.utils import get_openapi` in main.py, dann in P2.1 auto-generiert. Oder Redoc/SwaggerUI per `app.openapi_schema = get_openapi(...)` + `@app.get('/openapi.json')`. Bis M2 muss docs/ einen Link zu live-API enthalten (z.B. Swagger UI unter /docs).
- **[HIGH] Audit-Log-Schema unspezifisch; append-only Implementierung + Feld-Liste fehlend** _(betrifft: Logging-Konsistenz, Compliance-Nachweise, forensische Analyse von Zwischenfällen)_
  - → P1.1-Erweiterung: audit_log-Schema definieren: {id, event_type: enum(reading_received, assessment_computed, alarm_raised, alarm_acknowledged, config_changed), actor: string (system|operator_id), ts: datetime_utc, reading_id: int (nullable), assessment_id: int (nullable), alarm_id: int (nullable), payload: json}. Append-only erzwingen: Datenbank-Constraint (NOT NULL, kein UPDATE), Application-seitig: nur INSERT. Aufbewahrung: 12 Monate (abgeleitet aus Entscheidungslogbuch, offen). P4.2 wird dann Implementierungsdetail.
- **[HIGH] Fail-safe NF-01 Implementierungs-Pfad unklar: wer is responsible (Ingest vs. Storage vs. Assessment)?** _(betrifft: Fehlerbehandlungs-Logik, Testabdeckung (P2.6/P3.7), DoD-Verifikation für P3.1/P3.2)_
  - → Architecture-Decision E-29: Fail-safe ist Multi-Layer: (1) **Ingest (P2.1)**: Plausibilitäts-Gate (Bereich-Check T_s -40..+60, RH 0..100); ungültige Einträge → 400 BadRequest + Log. (2) **Storage (P2.2 + P3.1)**: Stale-Detection beim Read: if last_reading.ts < now() - 180s → set risk=GELB (fallback color). (3) **Assessment (P2.4 + P3.2)**: Sensor-Defekt-Check (Flatline/Sprung) vor Schwellwert-Logik → if defect_detected → risk=GELB + `driving_factor='Sensor defect detected'`. DoD für P3.7: Test mit 5 Szenarios: (a) stale reading, (b) out-of-range T_s, (c) flatline RH, (d) no data, (e) network-delay → alle müssen risk=GELB liefern, nie GRUEN.
- **[MEDIUM] Stack-Entscheidung noch nicht ins Entscheidungslogbuch protokolliert (E-08 offen)** _(betrifft: Bewertungskriterium 'Nachvollziehbarkeit technischer Entscheidungen' der 40%-Individualleistung)_
  - → E-08 vor M2 finalisieren: 'FastAPI gewählt statt Flask (schnellere REST-Validierung via Pydantic, weniger Boilerplate für T0), SQLite gewählt statt Postgres (Deployment-Einfachheit, Dateien-basiert für lokalen Pi-Betrieb, leicht austauschbar später). HTTP-POST statt MQTT (G1 liefert HTTP, einfache Testbarkeit, kein Message-Broker-Setup nötig). Begründung: geringer Deployment-Overhead im 3-Wochen-Prototyp, Skill-Match (Team hat FastAPI-Erfahrung), später Postgres/MQTT möglich ohne Rewrite der Geschäftslogik (DB + Ingest-Schicht isolierbar).' Dann von Lucas unterzeichnen + Datum + ins Entscheidungslog commiten.
- **[MEDIUM] Ressourcen-Engpass: Lucas = CTO+PM+Systemarchitekt+Backend-Dev; kritischer Pfad vollständig bei ihm** _(betrifft: Projekt-Risiko bei Personal-Ausfall, Burnout-Risiko für Lucas)_
  - → E-30: 'Backup für kritischen Pfad: Johannes Petzold übernimmt P1.2 (API-Spezifikation) parallel zu Lucas' P1.1 (Datenmodell), sodass Freeze bis Di eingeplant ist even wenn Lucas 50% Zeit verliert. Hartling + Ganter (Backend-Dev mit niedriger Komplexität) schreiben P2.3 (Magnus-Taupunkt-Berechnung) schon Mo/Di, um Parallel-Velocity zu zeigen. Non-Performer auf kleine abgegrenzte Tasks (P3.4 GET /alarms, P3.5 Messgrößen-Aufnahmen, P4.4 Historie) verteilen → keine Blockade auf eine Person.' Im Daily Stand: kritischer Pfad-Status täglich reviewen (Traffic-Light).
- **[MEDIUM] Modul-Zerlegung ist kohärent strukturiert, aber Schnittstellen zwischen ingest/validation/assessment/storage nicht formal spezifiziert** _(betrifft: Parallele Implementierung von Ingest, Storage, Assessment ohne gegenseitige Blockaden)_
  - → P1.1-Erweiterung: Schnittstellen-Spezifikation (Python-Pseudocode oder Pydantic-Stubs): (1) **storage.repository.ReadingRepository**: `save(reading: Reading) -> Reading`, `get_latest(sensor_id: str) -> Optional[Reading]`, `get_since(sensor_id: str, from_ts: datetime) -> List[Reading]`. (2) **assessment.core**: `assess(reading: Reading, config: AssessmentConfig) -> Assessment`. (3) **validation.plausibility**: `check_plausibility(reading: Reading) -> Tuple[bool, str]` (valid, reason). Diese Stubs können als mock-Modul (z.B. `src/storage/mock_repository.py`) gebaut werden, sodass P2.1+P2.4 parallel gegen Mocks entwickeln können, bis P2.2 ready ist. Dann Mocks durch real ersetzt. P0.2 wird um diese Stubs erweitert.
- **[MEDIUM] Kein automatisiertes Testing-Gate (.github/workflows) etabliert; Manual-Reviewer-Abhängigkeit für jeden PR** _(betrifft: Code-Qualitäts-Consistency, Merge-Velocity, Test-Compliance)_
  - → P0.4 um CI/CD erweitern: `.github/workflows/test.yml` schreiben: (1) auf push/PR: `python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=80`. (2) bei Fehler: PR blocked bis fixed. (3) optional: `flake8`/`black` auto-format oder warning. Mit GitHub Actions (frei für öffentliche Repos) ist das 15-Minuten-Setup. Entfernt manuelle Coverage-Prüfung, beschleunigt Reviews.

### Linse: Anforderungs- & DoD-Abdeckung: Ist jede FA/NF/RB in der geplanten Arbeit abgedeckt? Sind kritische Fail-Safe-Tests benannt? Ist RB-01 strukturell sichergestellt?

_KRITISCHER STAND — M2-Deadline (Ende Woche 2, ca. 2026-06-26) in 5 Tagen mit KEIN Produktionscode vorhanden. DoD-Abdeckung strukturell definiert und vollständig (alle FA/NF/RB auf Tasks gemappt), aber Umsetzungsrisiko SEHR HOCH durch Ressourcen-Engpass (Lucas als einziger echter Backend-Dev + kritischer Pfad P1+P2.4) und fehlende CI/CD-Automation. RB-01 (kein Aktor) ist architektonisch durch API-Design erzwungen, aber noch nicht code-reviewed. NF-01 (Fail-safe) ist als benannter Test P3.7 + Teil von P2.6 vorgesehen, aber implementierungspflichtig. Die zwei Vorfall-Testfälle (FA-05-Nachvollziehbarkeit) sind als grüne Tests in P2.4 + P2.6 definiert, aber noch nicht geschrieben._

- **[CRITICAL] KEIN PRODUKTIONSCODE — Scaffolding blockiert alle Deliverables M2** _(betrifft: Alle P0–P3 Tasks (Scaffolding P0.2→P0.3 blockiert alles), insbesondere kritischer Pfad P1 (Contract) und P2 (Vertical Slice). Meilenstein M2 fällig Ende Woche 2 (5 Tage), aber Scaffolding ist noch nicht erledigt.)_
  - → Nach Scaffolding: P1.1–P1.4 (Contract einfrieren) Montag/Dienstag parallel abschließen — dies ist kritischer Pfad für G1 und G3.
- **[CRITICAL] G1-Finalwerte (Schwellenwerte) noch ausstehend — Dummy-Werte in Schwellenwerte.md** _(betrifft: P2.4 (Bewertungsmodul mit 2 Vorfall-Testfällen): Tests MÜSSEN gegen Config-Parameterwerte, nicht gegen Hardcode, geschrieben werden. P4.3 (Schwellen-Config-Endpoint) wird zur MUSS-Task, nicht Soll.)_
  - → Risk Mitigation: Dummy-Werte aus Schwellenwerte.md §2 in config/ als Startwerte + Unit-Tests gegen diese Config schreiben (nicht gegen absolute Werte). So können G1-Finalwerte später per Config-Update ohne Code-Änderung eingesetzt werden.
- **[CRITICAL] API/Datenmodell-Naht P1 blockiert BEIDE Gruppe 1 und 3 — noch nicht eingefroriert** _(betrifft: G1 kann nicht gegen finales API-Format entwickeln; G3 kann nicht gegen finales Datenformat UI planen. Ohne P1.3-Seam-Sync (G1 + G3 bestätigen Contract) kann P1.4 nicht umgesetzt werden. P2 und alle nachfolgenden Backend-Tasks brauchen finales Datenmodell aus P1.1.)_
  - → Formale Lieferdatei: OpenAPI 3.0 YAML/JSON im Repo unter docs/api/v1/openapi.yaml (oder .json). Dies ist Teil der DEL-08 Abnahmekriterium (Prüfungsleistung).
- **[CRITICAL] RB-01 (kein Aktor) architektonisch definiert, aber noch nicht code-reviewed** _(betrifft: Sicherheits-Compliance: Wenn ein Entwickler versehentlich einen Endpoint wie POST /runway/lock oder DELETE /restrictions schreibt, ist RB-01 verletzt. Enforcement-Hook (RB-01-Guard) ist geplant (erinnerung/stand.md), aber noch nicht aktiv. Bis dahin: manuelles Review im PR.)_
  - → Dokumentation in README.md: Listing der erlaubten G2-Endpoints (GET /assessment/current, GET /health, GET /alarms, POST /alarms/{id}/ack, GET /readings?from&to) mit Begründung, dass KEIN POST/DELETE für Runway/Sperrung existiert. Die G1-Daten kommen per Poller (G2 = Client gegen G1s `GET /current`), nicht über einen G2-eigenen Ingest-Endpoint. Dies ist auch Teil der DEL-08 API-Dokumentation.
- **[CRITICAL] NF-01 Fail-Safe (nie GRÜN bei Ausfall/Stale) als benannter Test noch nicht geschrieben** _(betrifft: Meilenstein M2: Wenn P2.6 (Unit-Tests ≥80% Coverage) keine Fail-Safe-Testfälle enthält, ist die Anforderung NF-01 nicht nachgewiesen. Prüfungsleistung: Ohne diese Tests können die Betreuer nicht validieren, dass das System sicherheitskritisch robust arbeitet.)_
  - → P3.7 Task parallel zu P2.6 starten und vor M2-Abschluss mergen. Verantwortung: Test & Code-Review (Mohammadi + Berger).
- **[HIGH] Zwei Vorfall-Testfälle (FA-05 Nachvollziehbarkeit) noch nicht benannt/geschrieben** _(betrifft: Risiko: Implementierer könnte eine Logik schreiben, die 'funktioniert' (alle Tests grün) aber beide Vorfälle NICHT korrekt löst, weil die spezifischen Testfälle fehlen. Dies ist direkter Verstoß gegen FA-05 (nachvollziehbare Bewertung) und ein Risiko für das Kernziel des Projekts.)_
  - → Diese Tests müssen Test-Suite vor M2-Merge enthalten und in der Testprotokoll (P5.3) aufgelistet sein.
- **[HIGH] Ressourcen-Engpass: Lucas ist einziger echter Backend-Dev auf kritischem Pfad** _(betrifft: Single Point of Failure auf kritischem Pfad. Wenn Lucas krank wird oder sich in Details verfangen, spill-over zu M3 und M2 wird nicht erreicht.)_
  - → Hartling/Ganter nur auf abgegrenzten Tasks: P3.4 (GET /alarms Endpoint, S-Größe), P4.4 (GET /readings Historie, S-Größe). Diese parallelisieren mit P2, nicht blockieren P2.
- **[HIGH] P2 + P3 beide Ende Woche 2 fällig, aber sequenziell abhängig → Spillover zu W3 wahrscheinlich** _(betrifft: M2 wird wahrscheinlich verfehlt. P3 spill-over zu Woche 3 (M3). Dies ist nicht das benotete Minimum (Realismus-Hinweis in Tasks+Projektplan.md §3: 'Muss = P0–P3 + P5'), aber realistisch: P3 wird teilweise in Woche 3 landen.)_
  - → Kanban-Board (Jira) muss diese Parallelisierung abbilden mit expliziten Story-Dependencies und Swim-Lanes.
- **[HIGH] API/Datenmodell-Naht: Formale OpenAPI-Spez noch nicht erstellt** _(betrifft: DEL-08 (API-Dokumentation, fällig Ende Woche 2) ist eine Pflicht-Abgabe der Prüfungsleistung. Ohne formale Spezifikation können G1 und G3 nicht wirklich dagegen entwickeln. Auto-Codegen (OpenAPI-Generator) für Clients nicht möglich.)_
  - → Tool-Empfehlung: FastAPI auto-generiert OpenAPI aus Pydantic-Schemas (uvicorn --reload erzeugt docs unter /docs und /redoc). Aber EXPLIZIT ins Repo als statische Datei exportieren: `python -m fastapi openapi generate app.py > docs/api/v1/openapi.yaml`.
- **[HIGH] Seam-Sync mit G1 und G3 noch nicht terminiert — aber T0 des Projekts** _(betrifft: P5.1 (E2E-Integration mit G1) und P5.2 (E2E-Integration mit G3) sind abhängig von Seam-Sync. Wenn Payload-Format erst in Woche 2 geklärt wird, bleibt wenig Zeit für Fehlersuche.)_
  - → Dokumentieren in P1.3-Task oder neuem Dokument 02-Arbeitsdokumente/Seam-Sync-G1-G2-G3.md.
- **[MEDIUM] DoD für M2 nicht explizit zum Taskzustand gesynced — potenzielle Verwirrung bei Definition of Done** _(betrifft: M2-Abschluss-Bewertung: Ohne explizite DoD-Prüfung pro Task können 'fertige' Tasks trotzdem als incomplete gelten.)_
  - → Vor M2-Ablauf (2026-06-26): Explizite DoD-Checkliste für Jira-Tasks erstellen (oder in PR-Template). Beispiel:
- [ ] Code reviewed und gemerged auf main
- [ ] Unit-/Integrations-Tests grün (pytest --cov)
- [ ] Anforderungs-ID im Commit referenziert (zB 'Fix FA-01: Oberflächentemperatur erfasst')
- [ ] Entscheidung (falls getroffen) im Entscheidungslogbuch notiert
Dies muss im PR-Template in .github/pull_request_template.md stehen.
- **[MEDIUM] Schwellenwerte.md §3 Sensor-Kalibriervorgaben: G1-Verantwortung, aber Backend muss diese kennen** _(betrifft: P2.4 Bewertungsmodul: wenn Schwellwerte auf ±0,3 °C ausgelegt sind, aber echte Sensoren ±0,5 °C geben, können beide Vorfälle falsch klassifiziert werden.)_
  - → Abhängigkeit hinzufügen: P2.4 blockiert durch P1.3 Seam-Sync (G1-Genauigkeits-Bestätigung).
- **[MEDIUM] Entscheidungslogbuch: 40% Individualleistung wird nicht von KI dokumentiert, aber noch nicht geplant** _(betrifft: Jeder Studierende (11 Leute in G2) muss eine Entscheidung selbst dokumentieren und reflektieren. Falls dies nicht passiert, verliert die gesamte Gruppe bis zu 40% der Gesamtnote.)_
  - → Fälligkeitstermin: 2026-07-03 (Ende Woche 3). Dies wird NICHT von KI geschrieben — jeder Mensch schreibt seine eigene Reflexion. KI darf nur als Schreib-Assistent fungieren (z.B. Draft-Struktur bereitstellen), aber der Text und die Reflexion müssen vom Menschen kommen.
- **[MEDIUM] Audit-Log-Entitaet: Schema noch nicht spezifiziert** _(betrifft: P2.2 (Persistenz) + P4.2 (Audit-Log Implementierung): Entwickler wissen nicht, wie audit_log Schema aussehen soll. Risiko: mehrere Implementierungen, Inkompatibilität.)_
  - → Beispiel-Einträge in docs/audit-log-examples.json dokumentieren.
- **[MEDIUM] CI/CD-Pipeline (.github/workflows) nicht vorhanden** _(betrifft: M2-Qualitäts-Sicherung: Wenn P2.6 Tests nicht automatisiert laufen, können manuelle Test-Fehler durchrutschen.)_
  - → Interim: PR-Template (docs/PULL_REQUEST_TEMPLATE.md) mit Checklist: '- [ ] pytest --cov passed locally, coverage ≥80%' + manuelles Review.
- **[MEDIUM] Prognose-Modul (P6.1, forecast/) nicht im T0/M2 Scope, aber FA-06 ist MUSS** _(betrifft: M3-Deliverable: Wenn Prognose nicht implementiert, ist ein MUSS-Feature nicht in Prototyp. Aber: In Schwellenwerte.md §2 gibt es bereits GELB-Vorwarnung für Prognose ('Prognose: T_s wird in ≤ 30 min unter Gefriergrenze fallen'). Diese Vorwarnungs-Logik könnte ohne vollständigen Forecast als einfacher Trend (Linear Regression über letzte 5 Messwerte) implementiert werden.)_
  - → Oder: Simple Prognose in P2 einbauen — 3-Punkt-Linear-Regression über T_s-Trend statt komplexe Methode. Zahl-Aufwand: S-Task (1 Tag), nicht L-Task.
- **[LOW] Repository-Struktur: 01-quellen/ als read-only korrekt, aber keine .gitignore Regel** _(betrifft: Risiko: Jemand ändert versehentlich Die Hintergrundgeschichte.txt, committed es, und später gibt es Konfusion über 'das Original'.)_
  - → Hinweis in 01-quellen/README.md: 'Dieses Verzeichnis ist read-only. Bei Änderungen Rücksprache mit Betreuung. Für Projektvariationen neue Datei erstellen.'  Oder: 01-quellen/ aus .gitignore herausnehmen und explizit als immutable Branch (git update-index --assume-unchanged) markieren (für Local-Dev).
- **[LOW] Zeitplan.txt Woche 3: Enddatum unklar, M3 nicht präzise** _(betrifft: Wenig praktische Auswirkung, aber für die Projektplanung sollte M3 exakt sein.)_
  - → Zeitplan.txt vollständig lesen oder aktualisieren; M3-Datum in Tasks+Projektplan.md festschreiben.

### Linse: Zeitplan- & Kritischer-Pfad-Machbarkeit für M2 (Ende Woche 2)

_M2 ist KRITISCH GEFÄHRDET. Realistische Machbarkeit unter 50%. Der kritische Pfad P1 (API/Datenmodell-Naht) MUSS sofort Montag/Dienstag abgeschlossen werden (Deadline Di Ende dieser Woche ~26.06). Lucas V. als einziger echter Backend-Dev sitzt gleichzeitig auf CTO/PM/Architekt-Rollen. P2.4 (Bewertungsmodul, Größe L, ~40-60h Schätzung) liegt kritisch auf ihm. Kein Produktionscode (src/tests/ nicht vorhanden) — Scaffolding blockiert alles und kostet 1-2 Tage. Drei parallele Engpässe: (1) API-Naht einfrieren + parallele Entwicklung ermöglichen, (2) Bewertungsmodul testen mit beiden Vorfällen + Fail-safe, (3) Ressourcen-Engpass bei Lucas. G1-Finalwerte nicht Blocker (parametrierbar bleiben), aber Drift-Risiko._

- **[CRITICAL] P1 (Contract-first API/Datenmodell) liegt allein bei Lucas — 4 Tage bis Deadline** _(betrifft: P2 (Vertical Slice), P3 (T1), G1-Datenformat, G3-Frontend-Integration)_
  - → SOFORT: Mo 09:00 — Lucas + Petzold (Pair) skizzieren Datenmodell in 2h (6 Entities, JSON-Schema; `reading` ohne `precip_type`, `ts` = G1s `measured_at`). Mo 14:00 — Lucas schreibt API-Spezifikation formal (OpenAPI 3.0 YAML, <3h). Di 08:00 — Telekonferenz Seam-Sync mit G1 + G3 (1h, Lucas moderiert): G1s `GET /current`-Snapshot-Shape + `GET /health` abstimmen. Di 17:00 — P1.4 Tag + Push. NICHT warten auf G1-Finalwerte (können später als Config-Werte kommen). ENTSCHEIDUNG JETZT: Poll-Intervall (≤ 60 s) + welche Felder G1 im `GET /current`-Snapshot garantiert liefert (Niederschlag ist gestrichen, E-32).
- **[CRITICAL] Kein Produktionscode vorhanden — Scaffolding (src/, tests/, config/) blockiert M2** _(betrifft: P0, P2, P3 — alle anderen Tasks sind von Ordnerstruktur abhängig)_
  - → Mo 08:00 — START: Lucas legt SOFORT die Ordnerstruktur an (15 min mit Bash). Pair mit Petzold, um pyproject.toml + FastAPI-Main aufzusetzen (45 min, einfach). Mo 09:30 — GET /health läuft, main branch wird via PR gemergt. Ab Mo 10:00 können alle anderen auf Feature-Branches gegen diese Struktur arbeiten. NICHT blockieren lassen — Scaffolding vor P1 oder parallel, nicht nach.
- **[CRITICAL] P2.4 (Bewertungsmodul, Größe L) — Lucas als einziger Owner bei kritischem Datenmangelrisiko** _(betrifft: M2 Deliverables (DEL-09), Alarmierungslogik, Live-Demo-Credibility)_
  - → PRIORISIERUNG: (1) Mo 10:00 (nach Scaffolding): Lucas + Petzold schreiben die reine Funktion der Bewertungslogik als isolierbares Modul assessment/core.py (Funktion evaluate_ice_risk(T_s, T_d, RH) -> str; 3-Faktor, kein Niederschlag-Argument). Startzeit: Mo 10:00, Ziel: Di 12:00 (Grundversion, ~6h Pair). (2) Alle Schwellen aus config/thresholds.json LADEN, nicht hardcoden. (3) Mi 08:00: Unit-Tests schreiben + beide Vorfälle als Testfälle. (4) Mi 17:00: Code-Review mit Arezo + Amelie (Test-Team). FEHLER VERMEIDEN: wenn T_s = -2.1 bei trockener Oberfläche (ΔT > 1,0 °C, auch bei 92 % Luftfeuchte), MUSS result=yellow sein (nicht orange) — Luft-RH triggert keine Feuchte mehr (E-33). Wenn T_s ≤ 0 und ΔT ≤ 0, MUSS result=rot sein. Testfälle sind nicht optional.
- **[CRITICAL] Lucas-Bottleneck: CTO/PM/Systemarchitekt + einziger echter Backend-Dev in einer Person** _(betrifft: Alle kritischen Pfad-Tasks, Risiko für Ausfallkatastrophe bei Lucas' Krankheit/Überlastung)_
  - → RESSOURCEN-UMLENKUNG: (1) Petzold übernimmt P2.2 (Repository-Pattern, DB-Schema) + P3.1/P3.2 (Stale/Defekt-Erkennung) — das sind Backend-intensive aber von Bewertungslogik unabhängig. (2) Hartling + Ganter: NICHT auf kritischem Pfad. Ihnen geben: P3.4 (GET /alarms einfacher Endpoint, 2h), P3.5 (restliche Messgrößen, 3h), P4.4 (Historie-Endpoint, 2h). (3) Lucas fokussiert: SOFORT P0.2 (Scaffolding, 3h), dann P1.1–P1.4 (15h Mo/Di), dann P2.4 (40h Mi/Do/Fr und übers Wochenende). (4) TEST-TEAM (Arezo, Amelie): nicht idle rumstehen — sie schreiben Testfälle parallel zu Implementierung (P2.6, P3.6, P3.7 können concurrent laufen sobald Code da ist).
- **[HIGH] Seam-Sync mit G1 + G3 nicht durchgeführt — API-Payload-Variationen sind offen** _(betrifft: P1.3, P2.1 (Ingest), P2.5 (GET /assessment), P5.1 (G1-Integration), P5.2 (G3-Integration))_
  - → Di 08:00–09:00 Konferenz mit allen 3 Gruppen: Lucas (G2), G1-Lead, G3-Lead (30 min pro Seite). Agenda: (1) G1s `GET /current`-Snapshot finalisieren (garantierte Felder, gemeinsamer `measured_at` in UTC, `status`-Encoding, Constraints) + `GET /health`-Vertrag. (2) GET /assessment/current Antwort-Format (welche Felder müssen dabei sein?). (3) G2-Poll-Intervall (≤ 60 s) + Stale-Timeout absprechen. (4) Commitment: G1 sagt 'unser `GET /current` ist ab X stabil', G3 sagt 'wir konsumieren Y bis Montag Woche 3'. ENTSCHEIDUNG-PROTOKOLL ins Entscheidungslogbuch.
- **[HIGH] G1-Finalwerte (~2 Tage ausstehend) — Parametrierbarkeit ist Bedingung, nicht Lösung** _(betrifft: P2.4 (Bewertungslogik), P4.3 (Config-Endpoint T2), Live-Demo-Zuverlässigkeit)_
  - → (1) JETZT Architektur-Design: Config-Layer muss zuerst kommen. Schwellenwerte.md definiert: welche 15–20 Parameter sind konfigurierbar (T_s_gruen_min, delta_T_feucht [ΔT-Oberflächenfeuchte-Schwelle ≤ 1,0 °C; kein Luft-RH-Parameter mehr, E-33], stale_timeout_s, etc.). (2) Implementierung: assessment/core.py NUR reine Funktion mit Parametern. Alle Schwelle-Laden-Logik in config/loader.py. (3) Fallback: config/thresholds.json hat hardcodierte Dummies. (4) STRENGE Regel: jede Schwelle muss als Konstante oder ENV-Var referenzierbar sein, NICHT als Literal. Code-Review-Gate: Search for '> 1.0' oder '0.0 °C' Strings wird REJECTED.
- **[HIGH] Definition-of-Ready fehlende Klarheit — Task-Abhängigkeitsmatrix nicht explizit** _(betrifft: Jira-Backlog-Synchronisierung, Parallelisierungspotential, Task-Zuordnung)_
  - → Heute Montag 11:00: Lucas + Petzold zeichnen eine 2D-Matrix (Task × Zeit in Stunden) auf, mit expliziten Abhängigkeiten. Beispiel: [P0.2: 3h, P0.3: 2h, P1.1: 6h parallel zu P0.2, P1.2: 4h nach P1.1, etc.]. Diese Matrix wir ins Jira übertragen (Sprints für Woche 2). So wird klar: Welche Tasks können Di parallel laufen während Lucas an P1 arbeitet? (Antwort: Petzold P2.2, Hartling/Ganter andere Dinge — aber NICHT ohne klare Abhängigkeitsauflösung). ARBEITSPRODUKT: einfaches CSV oder ASCII-Art-Diagram in 02-Arbeitsdokumente/.
- **[HIGH] Keine CI/CD-Pipeline (.github/workflows/) — Tests müssen manuell geprüft werden** _(betrifft: Code-Quality, Merge-Safety, M2-Deliverable-Stabilität)_
  - → (1) Heute Mo 15:00: Petzold + Hartling (25min Pair) schreiben .github/workflows/test.yml: pytest auf main + branches, pytest-cov Report, Branch-Protection-Rule 'test.yml muss green sein'. (2) config/pyproject.toml anpassen: pytest muss einfach mit 'pytest' aufzurufen sein. (3) Do 09:00 (Woche 2 vor M2-Deadline): alle Feature-Branches sind auf aktueller main. CI/CD läuft. Kein manueller 'Test-Chaos' vor M2.
- **[HIGH] RB-01 Enforcement-Hook noch nicht aktiv — manuelle Review bleibt Single Point of Failure** _(betrifft: RB-01 Compliance, Live-Demo-Sicherheit, Projektbestandteilnahme-Kriterium)_
  - → (1) Heute Mo 16:00: Lucas schreibt einen einfachen Pre-Commit-Hook check_rb01.sh (30 min): Sucht nach Strings 'unlock', 'freigabe', 'sperr', 'execute' in src/api/*.py. REJECT, wenn gefunden. Hook geht ins Repo (.git/hooks/pre-commit + Dokumentation in DEVELOPMENT.md). (2) Do Woche 2: Enforce-Hooks auch auf GitHub Actions (lint-stage). (3) P4.5 wird zu P0 verschoben (MUSS). Das ist 30 min Security-Review am Ende, aber MUSS vor M2 bestandem sein.
- **[MEDIUM] Entscheidungslogbuch liest sich einseitig — Lucas trägt allein ein, Risk für 40%-Individualleistung** _(betrifft: 40%-Individualleistung jedes Teamnitglieds, Prüfungsergebnis)_
  - → Mo 11:00: Lucas + PM (oder ganzes Team) führen Retrospektive 'Welche Entscheidungen haben wir getroffen?' durch: (1) AE-01 (Lokal vs. Cloud) — OFFEN, muss bis M2 entschieden werden. (2) AE-02 (Fernzugriff ja/nein) — OFFEN. (3) P0.1 (Stack Final) — behauptet entschieden aber nicht ins Entscheidungslog geschrieben. (4) API-Versioning (URL /v1/ oder was?). (5) Tastenbelegung: Was ist minimum viable product für M2 vs. was ist Stretch? Jede dieser Entscheidungen bekommt einen Owner (Person, nicht KI), der die 4-6 Seiten reflektierendes Schreiben übernimmt. Das verhindert individuelle Benotungs-Risiken.
- **[MEDIUM] Datenmodell-Audit-Log-Schema nicht spezifiziert — NF-09-Anforderung unterspecced** _(betrifft: P2.2 (Persistenz), P4.2 (Audit-Trail Implementation), Testprotokoll-Design)_
  - → Mo 13:00: Lucas + DB-Engineers (Andreas, Leon) in 30 min Pair schreiben das audit_log-Schema: id(pk), event_type(enum: reading_ingested|assessment_generated|alarm_raised|alarm_acknowledged), event_payload(json), actor(string), ts(datetime), version(int). Beispiel-Instanzen schreiben. Schema-Dokument in Backend-Konzept §4 ergänzen. Das gibt P2.2 klare Vorgaben.
- **[MEDIUM] API-Versioning + Breaking-Change-Kommunikation nicht dokumentiert — riskant für G3** _(betrifft: P1.4 (Contract finalisieren), P5.2 (G3-Integration), Wartbarkeit)_
  - → Di 09:00 (bei Seam-Sync): Lucas + G3-Lead einigen sich: (1) URL-basierte Versionierung (/v1/, /v2/) oder Header-basierte (Accept: application/vnd.anr-api.v1+json)? Empfehlung: URL (/v1/) is einfacher für Prototyp. (2) Breaking-Change-Regel: neue GET-Parameter müssen mit ?version=2 queryable sein, alte bleiben supported. (3) Deprecation-Window (z.B. 1 Woche in Woche 3). (4) Dokumentation: CHANGELOG.md im Repo, enthält alle API-Versionen.
- **[MEDIUM] Prognose-Modul (forecast/, T3) nicht spezifiziert — aber als Stretch im Zeitplan** _(betrifft: Code-Struktur, T3-Stretch-Arbeit (Woche 3))_
  - → Do Woche 1 (noch diese Woche, Mo 17:00): Lucas + Petzold skizzieren forecast/-Modul-API (1h): Input=Zeitreihe der letzten 30min von T_s/T_d/p, Output=trend_prediction(T_s_in_30min). Nicht implementieren, nur Schnittstelle. Kommentar in src/forecast/__init__.py. Das verhindert, dass Bewertungslogik (assessment/) später Prognose-Code inline hat.
- **[MEDIUM] Fail-safe-Test (P3.7) ist abhängig von Stale/Defekt-Erkennung (P3.1/P3.2), aber nicht explizit sequenziert** _(betrifft: P3.1/P3.2/P3.7 Sequenzierung, Test-Team-Auslastung)_
  - → Abhängigkeitsmatrix (siehe Befund oben): P3.7 Test-Code kann Mo-Di concurrent geschrieben werden (Test-Spezifikation auf REQUIREMENTS basierend, Petzold/Lucas schreiben die Requirements für Stale-Erkennung bis Mo 17:00), aber P3.7 Code-Review + Merge braucht P3.1/P3.2 Implementation. DoD: 'Unit-Tests müssen grün laufen', bedeutet: P3.1/P3.2-Code existent + funktional.
- **[LOW] Systemkontext-Dokument (DEL-03) explizit nicht im Repo gefunden — möglicherweise Lücke für M1-Abgabe** _(betrifft: M1-Abgabe-Vollständigkeit, Bewertungs-Checklisten)_
  - → Mo 12:00: Lucas + PM prüfen Abgabeverzeichnis 03-abgaben/ und Studierenden-Handreichung.txt: Was ist Systemkontext genau? Ist Backend-Konzept.md §1 ausreichend? Falls nein: kurze Diagra-mme (C4-Model, Context-Diagram) in 1h neu schreiben. Sollte keine M1-Überraschung sein.
- **[LOW] erinnerung/stand.md ist 4 Tage alt (2026-06-17) — liest sich wie Montag-Morgen-Notiz aus Vorwoche** _(betrifft: Projektgedächtnis, Onboarding neuer Personen)_
  - → Mo 17:00 (End-of-Day): Lucas + PM aktualisieren erinnerung/stand.md: Woran wir diese Woche arbeiten (P0.2, P0.3, P1.1–P1.4). Offene Punkte (Seam-Sync Di, G1-Werte ausstehend). Blockers (Lucas-Ressourcen). Fälligkeiten (API Spec final Fr). Commit ins Repo. Wird beim nächsten /start gelesen.

---

## 8. Jira-Backlog: Epics → Tasks

**Übersicht:**

| Epic | Meilenstein | #Tasks |
|---|---|---|
| E-01 Setup & Repo-Scaffolding | M1 | 4 |
| E-02 API/Datenmodell-Naht (Contract-First) | M2 | 4 |
| E-03 T0 Vertical Slice (Ingest → Bewertung → API) | M2 | 7 |
| E-04 T1 Kernfunktion (Plausibilität, Alarme, Messgröβen) | M2 (mit Spillover M3) | 6 |
| E-05 T2 Sicherheit & Betrieb | M3 | 5 |
| E-06 Integration, Test & Demo | M3 | 6 |
| E-07 Schwellenwerte-Parametrierung (Config/Environment) | M2 | 2 |
| E-08 Testing & CI/CD Pipeline | M2 | 2 |
| **Summe (Synthese-Epics E-01–E-08)** |  | **36** |

> **Gesamtzahl:** 36 (Synthese-Epics) + 6 Nachträge (§9 / Jira-Epic E-09) + 1 aus dem P5.4-Split = **43 Tasks in Jira** (DTB-1…DTB-52, 9 Epics).

---

### E-01 Setup & Repo-Scaffolding  ·  M1

**Ziel:** Repo-Struktur, Stack-Decision, lauffähiges Grundgerüst (GET /health) etablieren.

**Anforderungen:** P0.1, P0.2, P0.3, P0.4

#### P0.1: Stack-Entscheidung treffen + begründen
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Lucas Voehringer (Systemarchitekt)
- **Anforderungen:** NF-05, NF-10
- **Beschreibung:** Begründe Wahl Python+FastAPI+MySQL/MariaDB (rohes PyMySQL, E-29/E-35) vs. Alternativen (Flask, Node, MQTT). Dokumentation ins Entscheidungslogbuch (E-08).
- **DoD:**
  - Wahl im Entscheidungslogbuch E-08 mit Begründung (Deployment-Einfachheit, Team-Kompetenz, Skalierbarkeit)
  - Commit mit 'E-08: Stack final' Nachricht

#### P0.2: Repo-Struktur anlegen (src/, tests/, config/)
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Lucas Voehringer (CTO/Systemarchitekt)
- **Abhängig von:** P0.1
- **Beschreibung:** Lege Ordnerstruktur an (ingest, model, assessment, storage, api, config, forecast, tests). Schreibe README.md mit Übersicht + Branch/PR-Konventionen.
- **DoD:**
  - Ordnerstruktur src/ingest/, src/model/, src/assessment/, src/storage/, src/api/, src/config/, src/forecast/, tests/ vorhanden
  - README.md mit Modul-Kurzbeschreibung und Branch/PR-Konventionen
  - PR gemergt auf main

#### P0.3: Lauffähiges Grundgerüst (GET /health)
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Petzold (Backend-Dev, mittel) oder Lucas (mit Petzold Pair)
- **Abhängig von:** P0.2
- **Beschreibung:** Richte FastAPI auf, schreibe main.py mit Grundstruktur + GET /health Endpoint. Server soll lokal starten.
- **DoD:**
  - main.py oder src/api/main.py existiert
  - GET /health → HTTP 200 {status: ok}
  - Server läuft via 'uvicorn src.api.main:app --reload'

#### P0.4: Branch/PR-Konventionen + Definition of Ready/Done
- **Typ / Prio / Schätzung:** Task · High · S
- **Owner (Empfehlung):** Reisi (Doku) + Lucas (PM)
- **Beschreibung:** Dokumentiere Branching-Strategie (feature/* → PR → review → main), DoD (Code Review, Tests, Anforderungs-ID, Entscheidungslogbuch-Eintrag). Template in docs/ oder .github/pull_request_template.md.
- **DoD:**
  - docs/BRANCH_CONVENTIONS.md oder .github/pull_request_template.md mit DoR und DoD
  - Commit mit 'P0.4: DoD etabliert'

---

### E-02 API/Datenmodell-Naht (Contract-First)  ·  M2

**Ziel:** Formale API-Spezifikation v1, Datenmodell-Schema, Seam-Sync mit G1+G3, Contract einfrieren bis Di Woche 2.

**Anforderungen:** FA-09, FA-01, FA-03

#### P1.1: Datenmodell-Schema festzurren
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Lucas Voehringer + Johannes Petzold (Architekten)
- **Anforderungen:** Schnittstelle
- **Abhängig von:** P0.2
- **Beschreibung:** Definiere 6 Entitäten (reading, assessment, alarm, acknowledgement, threshold_set, audit_log) mit Feldern, Datentypen, Constraints. Pydantic-Schemas schreiben.
- **DoD:**
  - 6 Pydantic-Modelle in src/model/schemas.py definiert
  - JSON-Schema-Beispiele für jede Entität in docs/api/examples/
  - Schema-Dokument in docs/API_SCHEMA.md (oder als Python-Docstring)
  - Review durch Architekten + Test-Team bestanden

#### P1.2: API-Spezifikation v1 (OpenAPI)
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Lucas Voehringer (Systemarchitekt)
- **Abhängig von:** P1.1
- **Beschreibung:** Schreibe formale OpenAPI 3.0 Spezifikation (YAML/JSON) der **G2-Serving-Endpoints**: GET /assessment/current, GET /health, GET /alarms (T1), GET /readings (T1, Historie), POST /alarms/{id}/ack (T2). Request/Response-Formate, Error-Codes, Versionierung-Strategie. **Zusätzlich** den konsumierten **G1-Vertrag dokumentieren** (kein G2-Endpoint): erwartetes Schema von G1s `GET /current` (Snapshot + gemeinsamer `measured_at`) + `GET /health`, gegen das der Poller (P2.1) baut.
- **DoD:**
  - docs/api/v1/openapi.yaml oder openapi.json vorhanden (≥15 Operationen, G2-Serving)
  - FastAPI auto-generiert /docs (Swagger UI) + /redoc korrekt
  - Endpoint-Deckung: min. GET /assessment/current, GET /health, GET /alarms
  - G1-Naht dokumentiert: erwartetes `GET /current`-Snapshot-Schema + `GET /health` (Client-Sicht), gegen das der Poller validiert
  - Fehlerbehandlung (400 BadRequest, 503 ServiceUnavailable bei Stale/G1-Ausfall) dokumentiert

#### P1.3: Seam-Sync mit G1+G3 durchführen
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Lucas Voehringer (G2 Moderator)
- **Abhängig von:** P1.2
- **Beschreibung:** Synchronisationstermin Montag 10:00 oder Di 08:00 mit G1-Lead + G3-Lead. Abstimmung: (1) G1s `GET /current`-Snapshot-Felder + Datentypen (welche Messwerte garantiert, gemeinsamer `measured_at` in UTC, `status`-Encoding) + `GET /health`-Vertrag + G2-Poll-Intervall (≤ 60 s), (2) GET /assessment/current Response-Format, (3) Messintervall + Stale-Timeout, (4) Geoposition (FA-13). Schriftliche Bestätigung von beiden Gruppen.
- **DoD:**
  - Termin mit G1+G3 durchgeführt (Konferenz oder async schriftlich)
  - Geklärt: G1s `GET /current`-Snapshot-Felder/Typen + `measured_at` + `GET /health`, GET-Response Format, G2-Poll-Intervall
  - G1 + G3 unterschreiben Bestätigung per E-Mail oder GitHub-Issue mit Label 'seam-sync-confirmed'
  - Entscheidungslog-Eintrag: AE-03 'API-Versioning Strategie' + Final-Zielwerte für NF-02 (Messintervall)

#### P1.4: Contract v1 einfrieren + kommunizieren
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Lucas Voehringer
- **Abhängig von:** P1.3
- **Meilenstein:** M2
- **Beschreibung:** Tag Contract v1 in Git (z.B. git tag api-v1.0 + PR-Merge auf main). Versand an G1 + G3 mit Zusammenfassung der gesammelten API-Payload-Formate.
- **DoD:**
  - Git-Tag 'api-v1.0' + 'P1.4' Commit vorhanden
  - docs/API_FROZEN_v1.md (oder Ticket-Kommentar) mit Summary: G1 `GET /current`-Snapshot-Felder (Client-Konsum) + `GET /health`, GET /assessment/current format, Poll-Intervall, Versionierung
  - E-Mail an G1/G3 mit Link zu openapi.yaml

---

### E-03 T0 Vertical Slice (Ingest → Bewertung → API)  ·  M2

**Ziel:** Funktionsfähiger T0-Stack: Poller (G1 `GET /current`) → Validierung → Persistenz → Bewertung → GET /assessment/current mit ≥80% Coverage + beide Vorfälle grün.

**Anforderungen:** FA-01, FA-03, FA-05, FA-09

#### P2.1: Poller-Client gegen G1 `GET /current` + Eingangsvalidierung
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Arash Sarkhab (Backend-Developer) — NICHT Hartling/Ganter (vgl. Owner-Korrektur §1)
- **Anforderungen:** FA-Schnittstellen
- **Abhängig von:** P1.4, P2.2
- **Beschreibung:** Implementiere einen **Poller/HTTP-Client**, der G1s `GET /current` in einem selbst bestimmten Intervall (≤ 60 s) abruft (EIN Snapshot aller Messwerte + gemeinsamer `measured_at`, UTC) und `GET /health` als Erreichbarkeits-Check nutzt. Empfangene Felder: sensor_id, measured_at, surface_temp_c (T_s), air_temp_c (T_a), humidity_pct (= **Luftfeuchte RH**, nur Input für T_d via Magnus — **kein** separater Oberflächenfeuchte-Wert nötig, E-33), pressure_hpa (Druck) — **kein** precip_type (E-32). Validierung: Bereichscheck (T_s -40..+60, RH 0..100), Pflichtfelder, Stale (`measured_at` älter als 3 × Intervall / > 180 s) und Erreichbarkeit (`/health`/Timeout) **getrennt** prüfen. Persistieren via Repository.save_reading() mit `ts` = G1s `measured_at`.
- **DoD:**
  - Poller ruft G1 `GET /current` zyklisch (≤ 60 s) ab; gültiger Snapshot → persistiert via Repository
  - `GET /health`/Timeout-Behandlung: G1 nicht erreichbar → kein Absturz, sicherer Zustand (nie GRÜN), Log
  - Ungültige Snapshot-Werte (Out-of-Range, fehlende Felder) → verworfen/markiert + Fehler-Log (kein stiller Ausfall)
  - Stale-Erkennung über `measured_at` (getrennt von Erreichbarkeit) greift
  - Unit-Test: Poller gegen gemockten G1-`GET /current` (httpx-Mock) speichert korrekt

#### P2.2: Persistenz (Repository-Pattern)
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Andreas Moritz oder Leon Hartling (DB-Engineers)
- **Abhängig von:** P1.1
- **Beschreibung:** Implementiere Repository-Pattern für readings: Klasse ReadingRepository mit Methoden save(reading), get_latest(sensor_id), get_since(sensor_id, from_ts). MySQL/MariaDB-Tabelle 'reading' mit Index auf sensor_id + ts. Transaktionen + Error-Handling.
- **DoD:**
  - src/storage/repository.py mit ReadingRepository klasse
  - DDL (CREATE TABLE reading ...) in `migrations/schema.sql` (handgeschrieben, kein Alembic — E-35)
  - Unit-Tests für Repository (save, get_latest, get_since)
  - Integration mit src/api/main.py via Dependency Injection

#### P2.3: Taupunkt-Berechnung (Magnus-Formel)
- **Typ / Prio / Schätzung:** Task · High · S
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Abhängig von:** P0.2
- **Beschreibung:** Implementiere Magnus-Formel (a=17.62, b=243.12 — über flüssigem Wasser; Quelle: Alduchov & Eskridge 1996. Im Vereisungsbereich ggf. Eis-Konstanten a=22.46, b=272.62 prüfen — Quelle/Variante als Code-Kommentar festhalten) zur Berechnung T_d aus T_a + RH. Unit-Tests gegen Referenzwerte (z.B. T_a=20°C, RH=60% → T_d≈11,9°C). Funktion als reine Funktion in src/assessment/utils.py.
- **DoD:**
  - Funktion calculate_dew_point(T_a, RH) → T_d vorhanden
  - ≥3 Unit-Tests gegen bekannte Referenzwerte
  - Kommentar mit Magnus-Parameter-Erklärung

#### P2.4: Bewertungsmodul — 4-Stufen-Logik (KRITISCHER PFAD)
- **Typ / Prio / Schätzung:** Story · Highest · L
- **Owner (Empfehlung):** Lucas Voehringer (Backend+Architekt, DRI kritischer Pfad)
- **Anforderungen:** FA Risikobewertung, Schwellenwerte.md §2
- **Abhängig von:** P2.3, P0.5 (Config-Infrastruktur: config/thresholds.json + loader, E-09; ENABLER, M1) — NICHT der Laufzeit-Endpunkt P4.3
- **Beschreibung:** Implementiere Vereisungslogik aus Schwellenwerte.md §2: 4 Stufen (GRÜN/GELB/ORANGE/ROT) **3-Faktor** basierend auf T_s (Oberflächentemp), ΔT (Taupunkt-Abstand) und RH (Luftfeuchte, nur T_d-Input) — **kein Niederschlag** (E-32). ROT := T_s ≤ 0 °C UND ΔT ≤ 0 °C; 'Feuchte vorhanden' := ΔT (T_s − T_d) ≤ 1,0 °C — an die **Oberfläche** gebunden (Nähe zum Taupunkt). Der frühere Luft-RH-Trigger (`RH ≥ 90 %`) ist **komplett entfernt** (E-33), weil Luftfeuchte nichts über die Oberfläche aussagt; T_a/RH fließen nur **indirekt** über T_d (Magnus) in ΔT ein. Hysterese + Entprellung. KRITISCH: beide Vorfälle (−2,1 °C, 92 % Luftfeuchte bei trockener Oberfläche → ΔT > 1,0 → **GELB**, NICHT ORANGE; +1,2 °C Luft, T_s<0, ΔT≤0→ROT) als benannte grüne Testfälle. Schwellen aus config/ laden, keine Hardcodes. Reine Funktion (testbar). Coverage ≥80%.
- **DoD:**
  - Reine Funktion assess_ice_risk(T_s, T_d, RH, config) → Assessment in src/assessment/core.py (3-Faktor, kein precip_type-Argument; RH = Luftfeuchte nur als T_d-Input, kein direkter Feuchte-Trigger)
  - Config-Loader lädt thresholds aus config/thresholds.json (YAML oder JSON mit Dummy-Werten)
  - Test-Suite mit ≥15 Testfällen inkl. test_vorfall_1_false_alarm_dry_cold() + test_vorfall_2_ice_at_positive_air_temp()
  - Hysterese/On-Delay (60s) + Rückstufungs-Stabilität (5min) implementiert
  - Coverage ≥80% (pytest --cov=src/assessment --cov-fail-under=80)

#### P2.5: GET /assessment/current Endpoint
- **Typ / Prio / Schätzung:** Task · High · S
- **Owner (Empfehlung):** Backend-Dev (Hartling/Ganter oder Petzold)
- **Abhängig von:** P2.4
- **Beschreibung:** Implementiere FastAPI Endpoint GET /assessment/current, liest latest reading → ruft assessment auf → liefert {risk_level, driving_factor, explanation, threshold_set_id, ts}. Status-Code 503 bei Stale/Ausfall (fail-safe GELB).
- **DoD:**
  - GET /assessment/current → 200 {risk_level: green/yellow/orange/red, driving_factor: string, explanation: string, threshold_set_id: int, ts: datetime}
  - Bei Stale (> 180s): 503 Service Unavailable + {risk_level: yellow, message: 'Stale data, manual verification required'}
  - Swagger-Docs zeigt Endpoint + Beispiel-Response

#### P2.6: Unit-Tests Bewertung (≥80% Coverage)
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Mohammadi oder Berger (Test & QA), mit Lucas Code-Input
- **Anforderungen:** NF-01
- **Abhängig von:** P2.4, P3.1, P3.2
- **Beschreibung:** Schreibe umfassende Unit-Tests für assessment/core.py: ≥15 Test-Cases inkl. (1) Vorfall 1 (−2,1 °C, 92 % Luftfeuchte bei trockener Oberfläche → ΔT > 1,0 → GELB, NICHT ORANGE; Luft-RH triggert bewusst keine Feuchte mehr, E-33), (2) Vorfall 2 (+1,2 °C Luft, T_s<0, ΔT≤0 → ROT), (3) Grenzfälle (T_s=0°C, ΔT=1,0 °C als Feuchte-Schwelle, ΔT=0), (4) Hysterese-Schaltungen, (5) Fail-safe (Stale/Defekt → GELB/rot). pytest --cov ≥80%.
- **DoD:**
  - tests/test_assessment_core.py mit ≥15 Testfällen
  - test_vorfall_1_false_alarm_dry_cold() grün — Erwartung GELB über ΔT > 1,0 (nicht über Luft-RH)
  - test_vorfall_2_ice_at_positive_air_temp() grün
  - pytest --cov=src/assessment --cov-report=term-missing → ≥80%
  - Alle Tests grün vor PR-Merge

#### P3.7: Fail-safe-Test (Stale/Defekt → nie GRÜN)
> _Hinweis: gehört logisch zu Epic E-04 (T1), da abhängig von P3.1/P3.2; in Jira aktuell unter E-03 angelegt — bei Bedarf in Jira umhängen._
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Mohammadi oder Berger (Test & QA)
- **Anforderungen:** NF-01
- **Abhängig von:** P2.6, P3.1, P3.2
- **Beschreibung:** Schreibe konkrete Fail-safe-Tests: (1) stale > 180s → GELB, (2) T_s out-of-range → GELB, (3) Flatline RH → GELB, (4) no data → GELB, (5) network-delay 5min → GELB. Alle 5 Szenarien müssen nie GRÜN ausgeben.
- **DoD:**
  - tests/test_fail_safe.py mit 5 benannten Testfällen (test_fail_safe_stale_*, test_fail_safe_outofrange_*, etc.)
  - Alle 5 Tests grün (risk_level='yellow' oder 'unknown')
  - Code-Review bestätigt: kein risk_level='green' bei Ausfall

---

### E-04 T1 Kernfunktion (Plausibilität, Alarme, Messgröβen)  ·  M2 (mit Spillover M3)

**Ziel:** Stale/Defekt-Erkennung, Alarm-Generierung mit Hysterese, alle Messgrößen eingepflegt, Integrationstests. Realistische Spillover zu Woche 3.

**Anforderungen:** FA-04, FA-08

#### P3.1: Plausibilität + Stale-Erkennung
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Abhängig von:** P2.1
- **Beschreibung:** Implementiere Validierungslogik vor Bewertung: Bereichscheck (T_s -40..+60, RH 0..100), Stale-Detection (letzter Messwert >180s), Fehler-Markierung. Fail-safe: bei Stale/Fehler → risiko_level=GELB (nicht GRÜN).
- **DoD:**
  - src/ingest/validation.py mit Funktionen check_plausibility(), detect_stale()
  - Stale-Schwelle konfigurierbar (config/thresholds.json: stale_timeout_s = 180)
  - Unit-Tests: test_plausibility_out_of_range(), test_stale_detection()

#### P3.2: Sensor-Defekt-Erkennung (Flatline/Sprung/Timeout)
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Petzold oder DB-Engineers (Andreas/Leon)
- **Abhängig von:** P2.2
- **Beschreibung:** Implementiere Defekt-Erkennung: (1) Flatline: keine Änderung > 15 min trotz Rauschen → defekt, (2) Sprung: Änderung > 5 °C/min → defekt, (3) NaN/Timeout. Markiere Sensor, triggere sicheren Zustand.
- **DoD:**
  - src/storage/anomaly_detector.py oder Validator-Modul mit detect_flatline(), detect_jump(), detect_timeout()
  - Konfigurierbare Schwellen (flatline_min_minutes, jump_threshold_c_per_min)
  - Unit-Tests: test_flatline_detection(), test_jump_detection()
  - Integration mit P3.1: defekt → fail-safe

#### P3.3: Alarm-Generierung + Schweregrad + Hysterese
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Abhängig von:** P2.4
- **Beschreibung:** Implementiere Alarm-Logik: assess() liefert risk_level → wenn ORANGE oder ROT → Alarm generieren mit severity (warning/critical). Hysterese: Hochstufung nach 60s, Rückstufung nach 5min stabil. On-Delay implementieren. Alarm-Tabelle + alarm-Entität.
- **DoD:**
  - src/alarm/generator.py mit generate_alarm_on_risk_level()
  - Alarm-Tabelle in src/storage/schema.sql (id, assessment_id, severity, raised_at, state)
  - Hysterese-Logik: On-Delay ≥60s, Rückstufungs-Stabilität ≥5min
  - Unit-Tests: test_alarm_on_orange(), test_alarm_on_red(), test_hysterese_no_chatter()

#### P3.4: GET /alarms Endpoint
- **Typ / Prio / Schätzung:** Task · Medium · S
- **Owner (Empfehlung):** Hartling oder Ganter (einfacher Endpoint)
- **Abhängig von:** P3.3
- **Beschreibung:** Implementiere GET /alarms Endpoint, liefert Liste aktiver Alarme {id, assessment_id, severity, raised_at, state}. Query-Parameter: ?active=true (nur aktive), ?limit=10 (Paginierung).
- **DoD:**
  - GET /alarms → 200 + JSON Array
  - Filtermöglichkeit ?active=true für aktive Alarme
  - Pagination ?limit=10 &offset=0
  - Swagger-Docs zeigt Endpoint

#### P3.5: Restliche Messgrößen aufnehmen (RH, Druck)
- **Typ / Prio / Schätzung:** Task · Medium · S
- **Owner (Empfehlung):** Backend-Dev (Hartling/Ganter)
- **Abhängig von:** P2.1
- **Beschreibung:** Erweitere den Poller-Mapper + Reading-Entität um alle aus G1s `GET /current`-Snapshot gelieferten Messgrößen: humidity_pct (= Luftfeuchte RH, nur T_d-Input via Magnus — kein direkter Feuchte-Trigger, E-33), pressure_hpa (air_temp_c bereits in P2.1). **Kein** precip_type (E-32). Validierung + Persistenz. Bereits teilweise in P2.1 vorhanden, jetzt komplett.
- **DoD:**
  - Reading-Pydantic-Schema erweitert: humidity_pct, pressure_hpa (kein precip_type)
  - Validierung: RH 0..100, Druck 300..1100 hPa
  - Unit-Tests: test_reading_with_all_fields()

#### P3.6: Integrationstest Ingest→Bewertung→API
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Mohammadi oder Berger (Test & QA)
- **Abhängig von:** P2.5, P3.3
- **Beschreibung:** Schreibe Integrationstests: gemockter G1-`GET /current`-Snapshot mit realistischen Daten (z.B. Vorfall 1, Vorfall 2, Normalbedingungen) → Poller verarbeitet → GET /assessment/current → prüfe risk_level + driving_factor. End-to-End-Verifikation; G1-HTTP gegen einen lokalen Stub/Mock, der Rest ohne Mocks.
- **DoD:**
  - tests/test_integration_e2e.py mit ≥5 Integrationstests
  - Test-Datensätze: Vorfall 1 (-2.1°C, dry), Vorfall 2 (+1.2°C, Oberfläche<0), Green (T_s>1°C)
  - G1-`GET /current`-Stub → Poller → GET /assessment/current → Assertion risk_level korrekt
  - Coverage integriert in --cov Report

---

### E-05 T2 Sicherheit & Betrieb  ·  M3

**Ziel:** Alarm-Quittierung, Audit-Trail (append-only), Schwellen-Config Endpoint (Laufzeit-Parametrierbarkeit), Historie. Soll-Prio für M2, Muss für M3.

**Anforderungen:** FA-10, FA-12, FA-11, NF-05

#### P4.3: Schwellen-Config (Laufzeit-Parametrierbarkeit)
> _Hinweis: Dies ist der Laufzeit-Config-ENDPUNKT (GET/POST /config). Der M2-Enabler für P2.4 ist die Config-Infrastruktur (thresholds.json + loader, Task P0.5 / Epic E-09) — nicht dieser Endpunkt._
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Anforderungen:** NF-05, FA-11
- **Abhängig von:** P2.4
- **Beschreibung:** Implementiere Config-Loading + -Endpoint. YAML/JSON (config/thresholds.json) mit allen Schwellen (T_s_green, T_s_orange, T_s_red, delta_T_feucht [Oberflächenfeuchte-Schwelle ΔT ≤ 1,0 °C; **kein** Luft-RH-Parameter, E-33], stale_timeout_s, etc.). GET /config, POST /config/{param}=value (authentifiziert, T3). Keine Hardcodes in Code.
- **DoD:**
  - config/thresholds.json mit ≥15 Schwellen-Parametern
  - src/config/loader.py liest config zur Startup
  - Config-Dependency-Injection in assessment() + validation()
  - GET /config (public) zeigt aktuelle Schwellen
  - Grep-Check: keine Literal-Schwellen (z.B. '> 1.0') in src/assessment/

#### P4.1: Alarm-Quittierung POST /alarms/{id}/ack
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Backend-Dev
- **Anforderungen:** FA-10, RB-01
- **Abhängig von:** P3.3
- **Beschreibung:** Implementiere Quittierungs-Endpoint: POST /alarms/{id}/ack mit {operator, note}. Erstelle acknowledgement-Eintrag (append-only, nicht delete). Alarm-State wechselt zu 'acknowledged'. Jede Quittierung ins Audit-Log.
- **DoD:**
  - POST /alarms/{id}/ack {operator: string, note: string} → 200
  - acknowledgements-Tabelle (append-only): id, alarm_id, operator, note, ts
  - alarm.state wechselt zu 'acknowledged'
  - Audit-Log-Eintrag: alarm_acknowledged, actor=operator, ts=now()

#### P4.2: Audit-Log (append-only Event-Log)
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** DB-Engineers (Andreas/Leon)
- **Anforderungen:** FA-12, NF-09
- **Abhängig von:** P2.2
- **Beschreibung:** Implementiere audit_log Tabelle + Logging-Decorator: {event_type, actor, ts, payload}. Event-Types: reading_ingested, assessment_generated, alarm_raised, alarm_acknowledged, config_changed. Append-only (kein UPDATE/DELETE auf audit_log). Indexe auf ts + event_type.
- **DoD:**
  - audit_log-Tabelle mit Constraints (NOT NULL, kein UPDATE/DELETE)
  - Logging-Utility-Funktion: log_event(event_type, actor, payload)
  - ≥4 Event-Types implementiert
  - Unit-Test: test_audit_log_append_only()

#### P4.4: Historie GET /readings?from=&to=
- **Typ / Prio / Schätzung:** Task · Medium · S
- **Owner (Empfehlung):** Hartling oder Ganter (einfacher Query-Endpoint)
- **Anforderungen:** FA-03
- **Abhängig von:** P2.2
- **Beschreibung:** Implementiere GET /readings?from=2026-06-21T00:00:00Z&to=2026-06-21T23:59:59Z [&limit=100]. Liefert gefilterte Messwerte im Zeitfenster. Pagination mit limit + offset.
- **DoD:**
  - GET /readings?from=ISO8601&to=ISO8601 → 200 + JSON Array
  - Query-Parameter: limit (default 100), offset (default 0)
  - Datenbank-Query mit WHERE ts BETWEEN ... ORDER BY ts DESC
  - Swagger-Docs zeigt Endpoint + Beispiel

#### P4.5: RB-01-Nachweis (Code-Review: kein Aktor-Endpoint)
- **Typ / Prio / Schätzung:** Task · Highest · S
- **Owner (Empfehlung):** Mohammadi oder Berger (QA/Review)
- **Anforderungen:** RB-01
- **Abhängig von:** P1.4
- **Beschreibung:** Führe Code-Review durch (oder Lint-Hook): Prüfe alle API-Endpoints auf Aktor-Keywords (unlock, freigabe, sperr, execute). RB-01 Garantie: System ändert nie Runway-Status. Dokumentation in README.md + Enforcement-Hook.
- **DoD:**
  - Lint-Hook pre-commit oder GitHub-Action prüft auf Aktor-Strings
  - README.md listet erlaubte Endpoints mit RB-01-Begründung
  - PR-Review-Kommentar + Approval: RB-01 bestätigt
  - Entscheidung E-15 'RB-01 Enforcement' ins Entscheidungslog

---

### E-06 Integration, Test & Demo  ·  M3

**Ziel:** E2E-Integration mit G1+G3, Testprotokoll (Abnahme-Checkliste), Entscheidungslogbuch finalisieren, Abschlusspräsentation, Reflexion.

**Anforderungen:** FA-06, FA-07, FA-08

#### P5.1: E2E-Integration mit G1 (echte/sim Sensordaten)
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Lucas Voehringer (Architekt + Backend, koordiniert mit G1-Lead)
- **Abhängig von:** P3.7, P4.3
- **Beschreibung:** Integriere Backend mit G1-Datenstrom. Poller zieht reale oder simulierte Messwerte aus G1s `GET /current`, durchlauf komplette Pipeline (Validierung → Bewertung → Alarm). Teste beide Vorfälle + Normalfall. Live-Demo möglich.
- **DoD:**
  - G1-Schnittstelle (Poller gegen G1 `GET /current` + `GET /health`) angebunden
  - ≥10 Snapshots pro Scenario (Vorfall 1, Vorfall 2, Normalbedingungen) fließen E2E
  - Logs zeigen jede Stage (Ingest → Bewertung → Alarm)
  - Live-Demo funzioniert

#### P5.2: E2E-Integration mit G3 (Frontend konsumiert API)
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Lucas Voehringer (Architekt, koordiniert mit G3-Lead)
- **Abhängig von:** P4.1, P1.4
- **Beschreibung:** Integriere Backend-API mit G3-Frontend. GET /assessment/current, GET /alarms, POST /alarms/{id}/ack fließen zu Frontend-Darstellung. Teste UI-Anzeige für alle 4 Risk-Levels (GRÜN/GELB/ORANGE/ROT).
- **DoD:**
  - G3 konsumiert GET /assessment/current korrekt
  - Frontend zeigt risk_level, driving_factor, Zeitstempel
  - Alarm-Quittierung über POST /alarms/{id}/ack funktioniert
  - Live-Demo: UI zeigt alle 4 Zustände

#### P5.3: Testprotokoll (Abnahme-Checkliste)
- **Typ / Prio / Schätzung:** Story · Highest · M
- **Owner (Empfehlung):** Mohammadi + Berger (Test & QA)
- **Abhängig von:** P3.7, P5.1, P5.2
- **Beschreibung:** Dokumentiere Abnahmetest-Checkliste aus Schwellenwerte.md §3 + NFA. Testfälle: Vorfall 1 (trocken −2,1 °C → GELB), Vorfall 2 (Eisbildung +1,2 °C → ROT), Green (T_s > 1 °C), Alarm bei ORANGE, Quittierung, Audit-Log-Einträge, Fail-safe (Stale/Defekt).
- **DoD:**
  - docs/TESTPROTOKOLL.md mit ≥12 Testfällen
  - Jeder Test: Vorbedingung, Schritt, Erwartetes Ergebnis, Status (Pass/Fail)
  - Beide Vorfälle als grüne Tests bestätigt
  - Coverage-Report angehängt (≥80% für assessment/)
  - Unterschrift/Approval durch Test-Team

#### P5.4: Entscheidungslogbuch finalisieren
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Reisi + Ilchyshyn (Doku) + alle Teamitglieder (Individualleistung 40%)
- **Anforderungen:** Prüfungsleistung 40%
- **Abhängig von:** Alle früheren Phasen
- **Beschreibung:** Dokumentiere alle getätigten Entscheidungen (E-08 Stack, E-15 RB-01, AE-01 lokal vs. Cloud, AE-02 Fernzugriff, weitere Architektur-Entscheidungen). Jedes Teamitglied hat ≥1 Entscheidung reflektiert (4–6 Seiten). Keine KI-geschriebenen Reflexionen.
- **DoD:**
  - Entscheidungslog-Datei(en) mit ≥6 E-Einträgen
  - Jeder Eintrag: Entscheidung, Alternativen, Begründung, Trade-offs, gewählte Lösung
  - ≥5 unterschiedliche Personen als Autoren
  - Jeder Mensch hat eigene Reflexion geschrieben (keine KI)
  - Commit ins Repo mit 'P5.4: Entscheidungslogbuch final'

#### P5.5: Abschlusspräsentation + Demo-Skript
- **Typ / Prio / Schätzung:** Story · High · M
- **Owner (Empfehlung):** Reisi + Ilchyshyn (Doku) + alle
- **Abhängig von:** P5.1, P5.2, P5.3
- **Beschreibung:** Bereite Live-Demo vor: (1) G1-`GET /current`-Stub liefert Testdaten (beide Vorfälle), Poller zieht sie, (2) GET /assessment/current zeigt Bewertung, (3) Frontend (G3) zeigt Visualisierung, (4) Alarm-Quittierung. Schreibe Demo-Skript (Abläufe, Timing, fallback-Szenarien).
- **DoD:**
  - Demo-Skript in docs/DEMO_SCRIPT.md: Schritte, erwartete Outputs, Timing
  - Live-Demo läuft ohne Fehler (≥2 volle Durchläufe getestet)
  - Presentation-Folien (z.B. PowerPoint oder PDF) mit Backend-Architektur + Learnings
  - Alle Zwischenergebnisse (API-Spec, Testprotokoll, Code) verlinkt

#### P5.6: Reflexion (Methodenvergleich Wasserfall vs. Scrum)
- **Typ / Prio / Schätzung:** Task · Medium · S
- **Owner (Empfehlung):** Reisi oder alle (Gruppen-Reflexion)
- **Abhängig von:** P5.1, P5.2, P5.3
- **Beschreibung:** Schreibe Reflexion über Backend-Arbeitsmethodik (Wasserfall für G2) im Vergleich zu G3 (Scrum). Was hat gut geklappt, was nicht? Wie würde man es wiederholen? Learnings für zukünftige Projekte.
- **DoD:**
  - docs/REFLEXION.md mit ≥3 Seiten
  - Abschnitte: Wasserfall-Phasen (P0–P6), Seam-Sync-Erfahrungen, Entscheidungslogbuch-Nutzen, Fehler/Learnings
  - Vergleich zu Scrum-Ansatz (Beobachtungen von G3)
  - Fazit + Empfehlungen

---

### E-07 Schwellenwerte-Parametrierung (Config/Environment)  ·  M2

**Ziel:** Alle Schwellenwerte aus config/ laden, kein Hardcode. Enabler für G1-Finalwert-Integration ohne Code-Änderung.

**Anforderungen:** FA-11, NF-05

#### Config-Infrastructure: thresholds.json + Loader
- **Typ / Prio / Schätzung:** Task · Highest · M
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Abhängig von:** P0.2
- **Beschreibung:** Erstelle config/thresholds.json mit Dummy-Werten (aus Schwellenwerte.md §2): T_s_gruen, T_s_orange, T_s_red, Delta_T_feucht (Oberflächenfeuchte-Schwelle ΔT ≤ 1,0 °C; **kein** Luft-RH-Feuchte-Parameter mehr, E-33), stale_timeout_s, flatline_min_minutes, jump_threshold_c_per_min, on_delay_s, hold_min_minutes. Loader in src/config/loader.py liest YAML/JSON + gibt Config-Objekt zurück.
- **DoD:**
  - config/thresholds.json YAML oder JSON mit ≥15 Schwellen-Parametern
  - src/config/loader.py mit load_config() → ConfigModel Pydantic
  - ConfigModel als Dependency in assessment() + validation()
  - Unit-Test: test_config_loading()

#### Enforce No-Hardcode Rule (Lint + PR-Template)
- **Typ / Prio / Schätzung:** Task · High · S
- **Owner (Empfehlung):** Petzold
- **Abhängig von:** P0.4
- **Beschreibung:** Schreibe Pre-Commit-Hook oder GitHub-Action, die auf Literal-Schwellen in Code prüft. Regex: keine Strings wie '> 1.0', '< 0.0', 'delta_t <= 1' (ΔT-Feuchteschwelle) ohne config-Referenz. Warnung im PR-Template: 'Bitte keine Hard-codierten Schwellen verwenden'.
- **DoD:**
  - Pre-Commit-Hook oder GitHub-Action .github/workflows/lint-config.yml vorhanden
  - Hook prüft auf verdächtige Strings ('>\s*[0-9.]', 'delta_?t\s*[<>]', 'T_s\s*[<>]')
  - PR-Template warnt: 'Schwellenwerte immer über config/ laden'

---

### E-08 Testing & CI/CD Pipeline  ·  M2

**Ziel:** Automatisierte Tests (pytest, coverage ≥80%), CI/CD-Enforcement vor Merge auf main.

#### CI/CD-Setup (.github/workflows/test.yml)
- **Typ / Prio / Schätzung:** Task · High · M
- **Owner (Empfehlung):** Petzold oder Backend-Dev
- **Abhängig von:** P0.4
- **Beschreibung:** Richte GitHub Actions auf: auf Push/PR → pytest --cov=src --cov-report=term-missing --cov-fail-under=80 ausführen. Branch-Protection: main erfordert 'test.yml' grün vor Merge. Workflows: test.yml, lint.yml (optional), security-scan.yml (optional).
- **DoD:**
  - test.yml existiert in .github/workflows/
  - Trigger: on: [push, pull_request]
  - Befehl: pytest --cov --cov-fail-under=80
  - Branch-Schutzregel: 'Require status checks to pass before merging'

#### pytest-Konfiguration + Fixtures
- **Typ / Prio / Schätzung:** Task · High · S
- **Owner (Empfehlung):** Mohammadi oder Berger (Test-Setup)
- **Abhängig von:** P0.2
- **Beschreibung:** Erstelle pytest.ini oder pyproject.toml [tool.pytest]: testpaths=tests, addopts=--cov=src, markers=integration. Schreibe conftest.py mit Fixtures: config_fixture (Dummy-Schwellen), db_fixture (In-Memory-Fake-Repository, DB-frei), reading_factory (Test-Daten).
- **DoD:**
  - pyproject.toml [tool.pytest] oder pytest.ini vorhanden
  - conftest.py mit ≥3 Fixtures (config, db, reading_factory)
  - Alle Tests können mit 'pytest' ausgeführt werden

---

## 9. Nachträge aus Verifikation (zusätzlich einplanen)

#### P0.5: Config-Grundstruktur anlegen (thresholds.json + loader.py)  ·  [E-07-Config]  ·  M2 (Voraussetzung fuer P2.4, Woche 2 Mo/Di)
- **Owner (Empfehlung):** Petzold (mittel, kann eigenstaendig, entlastet Lucas-Engpass)
- **Beschreibung:** Erstelle config/thresholds.json mit Dummy-Schwellenwerten aus Schwellenwerte.md §2 (T_s_gruen=1.0, T_s_orange=0.0, delta_T_feucht=1.0 [Oberflächenfeuchte-Schwelle ΔT ≤ 1,0 °C; **kein** RH_feucht/Luft-RH-Parameter mehr, E-33], stale_timeout_s=180, on_delay_s=60, hold_min_minutes=5, flatline_min_minutes=15, jump_threshold_c_per_min=5.0). Implementiere src/config/loader.py mit load_config() -> ConfigModel (Pydantic). Dies ist ENABLER fuer P2.4 — assessment() darf keine Hardcodes enthalten. Muss VOR P2.4 abgeschlossen sein.
- **DoD:**
  - config/thresholds.json mit mindestens 10 Parametern aus Schwellenwerte.md §2 vorhanden
  - src/config/loader.py mit load_config() -> ConfigModel (Pydantic BaseModel)
  - Unit-Test: test_config_loading() prueft, dass alle Pflichtfelder geladen werden
  - Kein Literal-Schwellenwert (z.B. '> 1.0') in src/assessment/ — grep-Check im PR-Template
  - PR gemergt auf main vor Beginn von P2.4

#### P0.6: pytest-Setup + .github/workflows/test.yml (CI-Gate)  ·  [E-08-TestCI]  ·  M2 (heute 2026-06-21, Blocker fuer alle weiteren PRs)
- **Owner (Empfehlung):** Petzold (15-30 Min Aufwand, eigenstaendig moeglich)
- **Beschreibung:** Erstelle pyproject.toml mit [tool.pytest.ini_options] (testpaths=['tests'], addopts='--cov=src'). Erstelle tests/conftest.py mit Fixtures: config_fixture (laedt Dummy-Config), db_fixture (In-Memory-Fake-Repository, DB-frei). Erstelle .github/workflows/test.yml: auf push/PR -> pytest --cov=src --cov-fail-under=80. Branch-Schutzregel empfehlen (test.yml muss gruen sein vor Merge auf main). Ohne diesen Task laufen alle Tests nur manuell.
- **DoD:**
  - pyproject.toml oder pytest.ini mit testpaths=tests vorhanden
  - tests/conftest.py mit mindestens 2 Fixtures (config_fixture, db_fixture)
  - .github/workflows/test.yml mit pytest --cov --cov-fail-under=80
  - Workflow laeuft erfolgreich auf einem leeren tests/-Ordner (0 Tests = kein Fehler)
  - PR gemergt vor erstem Feature-Branch

#### P2.4b: Einfache 30-min-Trendprognose als Teil des Bewertungsmoduls (FA-06 minimal)  ·  [E-03-T0Vertical]  ·  M3 (kann nach M2 als eigenstaendiger Branch gemergt werden, entkoppelt von P2.4-Kern)
- **Owner (Empfehlung):** Lucas Voehringer (muss in P2.4 integriert werden, gleicher Owner) oder Petzold als separater Branch
- **Beschreibung:** Implementiere eine einfache Lineare-Regression ueber die letzten N T_s-Messwerte, um T_s in 30 Minuten zu schaetzen. Wenn prognostizierter T_s <= 0°C fuer eine Oberflaechentemperatur, die aktuell noch > 0°C ist, setze risk_level auf GELB (Vorwarnung). Funktion in src/forecast/trend.py: predict_surface_temp_30min(readings: List[Reading], config: ForecastConfig) -> float. Schwellenwert (Prognosehorizont, min. Messwerte) aus config/ geladen. Diese minimale Implementierung erfuellt FA-06 fuer den Prototyp ohne ARIMA oder komplexe Methoden.
- **DoD:**
  - src/forecast/trend.py mit predict_surface_temp_30min() als reine Funktion
  - Lineare Regression ueber letzten 5-10 Messwerte (konfigurierbar)
  - Integration in assessment/core.py: wenn Prognose T_s<=0 in 30 min -> GELB-Flag in Assessment-Output
  - Unit-Tests: test_trend_rising(), test_trend_falling_to_zero(), test_insufficient_data() -> None
  - GET /assessment/current Antwort um Feld 'forecast_risk' und 'forecast_horizon_min' erweitern
  - Coverage src/forecast/ >= 80%

#### AE-01/NF-02: Betriebsmodell und Latenz-Zielwert festlegen (Entscheidungslog E-29 + E-30)  ·  [E-02-Contract]  ·  M2 (bis Di 2026-06-24, Teil von P1.3 Seam-Sync)
- **Owner (Empfehlung):** Lucas Voehringer (Architekt, DRI Entscheidungslogbuch)
- **Beschreibung:** Trifft zwei offene Entscheidungen: (1) AE-01: Lokal (Raspberry Pi) als T0-Betriebsmodell bestaetigen oder verwerfen. Begruendung ins Entscheidungslogbuch (E-29). (2) NF-02: Messintervall (Ziel: <=60s, laut Schwellenwerte.md §3) und max. Latenz Sensor->Anzeige (Ziel: <5s) als verbindliche Zielwerte festlegen. Diese Zielwerte beeinflussen Stale-Timeout-Config (180s = 3x60s), Testprotokoll-Kriterien und Demo-Setup. Seam-Sync P1.3 klaert NF-02 mit G1.
- **DoD:**
  - Entscheidungslog E-29: AE-01 mit Begruendung abgeschlossen (Lokal/Pi oder Cloud + Warum)
  - Entscheidungslog E-30: NF-02 Zielwert (Messintervall=60s, Latenz<5s) dokumentiert
  - config/thresholds.json: stale_timeout_s=180 als abgeleiteter Wert aus NF-02 kommentiert
  - Seam-Sync-Protokoll bestaetigt NF-02-Zielwert mit G1

#### Individual-Reflexionen: Entscheidungs-Owner-Zuweisung (40% Pruefungsleistung)  ·  [E-06-Integration]  ·  M3 (Zuweisung JETZT, Abgabe Ende Woche 3)
- **Owner (Empfehlung):** Lucas Voehringer (PM-Rolle, koordiniert mit Teilprojektleitung)
- **Beschreibung:** Verteile die 11 Personen des Teams auf je eine Entscheidung aus dem Entscheidungslogbuch fuer die individuelle Reflexion (4-6 Seiten, 40% der Note). Erstelle eine Zuordnungsliste (z.B. in 02-Arbeitsdokumente/Individualreflexionen-Zuordnung.md): Person X -> Entscheidung E-XX -> Abgabe-Deadline M3. Keine Person darf die Reflexion einer anderen Person oder einer KI ueberlassen. Sicherstellt, dass alle 11 Personen eine bewertungsrelevante Entscheidung haben, die sie selbst dokumentieren koennen.
- **DoD:**
  - 02-Arbeitsdokumente/Individualreflexionen-Zuordnung.md mit 11 Zeilen (Person, Entscheidung-ID, Abgabe-Deadline)
  - Alle 11 Personen haben eine Entscheidung zugewiesen, die einen wesentlichen Projekteinfluss hatte
  - Entscheidungen abdecken: Architektur (E-04..E-15), Organisation (E-19..E-22), Technik (E-08, E-09), Anforderungen (E-10..E-14)
  - Commit mit 'Individualreflexion-Zuweisung: alle 11 Personen zugewiesen' von Lucas als PM

#### ADR E-29: Fail-safe Multi-Layer Architektur-Entscheidung dokumentieren  ·  [E-04-T1Core]  ·  M2 (Voraussetzung fuer P3.1/P3.2, bis Mi 2026-06-25)
- **Owner (Empfehlung):** Lucas Voehringer (Systemarchitekt, DRI NF-01)
- **Beschreibung:** Dokumentiere die Architektur-Entscheidung, welche Schicht den sicheren Zustand (GELB bei Ausfall) erzwingt: (1) Ingest (P2.1): Plausibilitaets-Gate fuer Bereichscheck -> 400 BadRequest bei ungueltigen Werten. (2) Storage (P2.2+P3.1): Stale-Detection beim Read -> if last_reading.ts < now()-180s -> assessment.risk=GELB. (3) Assessment (P2.4+P3.2): Sensor-Defekt-Check (Flatline/Sprung) vor Schwellwert-Logik -> if defect_detected -> risk=GELB. Ohne diese ADR werden P3.1/P3.2 implementiert ohne gemeinsames Verstaendnis der Ownership.
- **DoD:**
  - Entscheidungslog-Eintrag E-29 in Entscheidungslog-Lucas-Systemarchitektur.md
  - Eintrag beschreibt: welche Schicht welchen Fail-safe erzwingt, warum Multi-Layer, Alternative (Single-Layer in Assessment), Begruendung (Defense-in-Depth)
  - Python-Pseudocode-Stub in Eintrag zeigt die drei Pruefpunkte
  - Commit vor Beginn von P3.1/P3.2
