# DTB-Backlog Übersicht — persönlich für Lucas

> Stand: **Do 25.06.2026** · Quelle: Live-Abgleich Jira-Projekt **DTB** (archidox-devs, 59 Vorgänge) + Git/PRs (`Alarmsystem-Dev`) + `erinnerung/stand.md`.
> Diese Datei liegt nur auf deinem Desktop und ist **nicht** Teil des Repos.
> Vorgängerschnappschuss war der 23.06. — der ist hier vollständig eingearbeitet/überholt.

---

## Aktuelle Lage auf einen Blick

- **M1 (Setup & Fundament): faktisch durch.** Stack, Repo-Struktur, `GET /health`, CI/CD-Gate, pytest, Config-Loader, Branch/PR-Konventionen sind alle ✅. **Nur Status-Hygiene offen:** Epic **DTB-1** steht in Jira noch auf „Zu erledigen", obwohl alle Kinder erledigt sind.
- **M2-Naht: ERLEDIGT.** 🎉 **API-Contract v1.0 ist eingefroren** (DTB-35 ✅, beidseitiges Sign-off G1/Nils + G3-Lead). OpenAPI v1 (DTB-19 ✅) und Seam-Sync (DTB-26 ✅) liegen auf `main`. **Rest rein mechanisch:** Git-Tag `api-v1.0` setzen + Versandkopie an G3 raus.
- **M2 verbleibend = der T0-Vertical-Slice.** Genau hier liegt jetzt der **kritische Pfad**: DB-Persistenz (in Review) → **Bewertungsmodul DTB-38 (noch NICHT begonnen, `assessment/` ist leer)** → `GET /assessment/current`. Das ist deine eigentliche Baustelle ab heute.
- **⚠️ PR-Stau: 9 offene PRs.** Davon 7 grün/mergebar, **2 mit Konflikt/Dublette zum Schließen** (#62 DTB-19-Dublette, #63 Connection-Helper-Fork ohne Tests). Außerdem **3 Branches für denselben PyMySQL-Connection-Helper** (#58/#61/#63) → Konsolidierung nötig. **PR-Triage ist Aufgabe #1 heute** (siehe eigener Abschnitt unten).
- **Lucas’ Rollen:** Systemarchitekt, DRI Datenmodell/Contract, Bewertungslogik, PM/Koordination. DB-Setup ist **delegiert** (Leon H / Andi / Ganter) — nur noch überwachen + mergen.

---

## ⚡ PR-Triage — Aufgabe #1 (heute) — *Stand 25.06., Git/CI live*

> Du hattest recht mit dem Ärger: mehrere PRs wurden ohne vorherigen `fetch`/Rebase aufgemacht, daher Konflikte und teils gar keine aktive Testpipeline. Hier die Live-Auflösung. **Merge/Close = deine Entscheidung** (ausgehende Git-Aktion, Freigabe nötig); ich habe nur den Status gezogen und eine Empfehlung dazugeschrieben.

| PR | Branch / Thema | Ticket | CI | Mergebar? | Empfehlung |
|---|---|---|---|---|---|
| **#67** | API-Contract v1.0 Freeze + Stand/Journal | DTB-35 | ✅ grün | ✅ | **Mergen** (deine aktuelle Branch; schließt den Contract-Doku-Teil) |
| **#66** | Poller: `dew_point_c` berechnen | DTB-60 | ✅ grün | ✅ | **Mergen** (Ganter) |
| **#65** | Entscheidungslog Taupunkt | DTB-32 | ✅ grün | ✅ | **Mergen** (Ganter, Doku) |
| **#64** | Taupunkt-Berechnung (Magnus) | DTB-32 | ✅ grün | ✅ | **Mergen** — entblockt Vorarbeit für DTB-38 |
| **#61** | PyMySQL Connection-Helper (rebased) | DTB-28/55 | ✅ grün | ✅ | **Mergen** — die saubere, rebasete Variante; **entblockt DTB-28** |
| **#59** | schema.sql Apply + append-only-Grants | DTB-54 | ✅ (skip+success) | ✅ | **Mergen** (Leon H) — DB-Schema einspielbar |
| **#58** | „Hartling-Entscheidungslog.md" (auf dtb-55-Branch) | DTB-55 | ✅ (skip+success) | ✅ | **Prüfen** — Inhalt vs. #61 abgrenzen; ggf. nur Doku übernehmen |
| **#63** | PyMySQL Connection-Helper (Andi-**Fork**) | DTB-55 | ❌ keine Checks | 🔴 Konflikt | **Schließen** — durch #61 (rebased) abgelöst; klassischer „kein fetch"-Fall |
| **#62** | OpenAPI v1 (Dublette) | DTB-19 | ⚠️ cancelled | 🔴 Konflikt | **Schließen** — DTB-19 ist bereits via **#48** auf `main` |

**Konsolidierungs-Knoten:** #58, #61, #63 berühren alle denselben Connection-Helper. Klare Linie: **#61 mergen**, **#63 schließen**, **#58 auf reinen Doku-Anteil reduzieren**. Danach ist DTB-55 sauber „Erledigt" und DTB-28 startklar.

**Reihenfolge zum Konfliktvermeiden:** erst die DB-Kette (#59 → #61), dann #64/#66 (Taupunkt/Poller), dann Doku (#65/#67). Nach jedem Merge die noch offenen Branches gegen `main` rebasen lassen.

---

## Meilenstein-Roadmap

| Meilenstein | Woche | Ziel | Status |
|---|---|---|---|
| **M1** | Woche 1 | Setup & Fundament (Stack, Repo, Health, CI, Config, Konventionen) | ✅ faktisch durch — nur Epic-Status DTB-1 in Jira nachziehen |
| **M2-Naht** | Woche 2 | API/Datenmodell **final eingefroren** | ✅ **erledigt** (DTB-35/19/26) — Rest: Tag + G3-Versand |
| **M2-Slice** | Woche 2 | T0-Vertical-Slice lauffähig (Poller→DB→Bewertung→API) | 🔴 **kritisch** — Persistenz in Review, **DTB-38 offen** |
| **M3** | Woche 3 | Prototyp, Live-Demo, Reflexionen, Testprotokoll | 🟠 viel Papierkram + Restfunktionen |

---

## Was sich seit 23.06. geändert hat (Delta)

| Ticket | Vorher (23.06.) | Jetzt (25.06., Jira live) | Bedeutung |
|---|---|---|---|
| **DTB-35** Contract v1 einfrieren | 🔵 Wird überprüft | ✅ **Erledigt** | **M2-Naht steht** — Sign-off G1+G3 |
| **DTB-19** OpenAPI v1 | 🟡 In Arbeit | ✅ **Erledigt** (#48) | Naht-Spez auf `main` |
| **DTB-11** CI/CD-Setup | ⬜ offen | ✅ **Erledigt** (Petzold) | Test-Gate aktiv („Require status checks") |
| **DTB-25** pytest-Setup | ⬜ offen | ✅ **Erledigt** | saubere PRs möglich |
| **DTB-52** Branch/PR-Konventionen | ⬜ offen | ✅ **Erledigt** (#55) | DoR/DoD steht |
| **DTB-53** Dev-DB-Zugang | ✅ (Delta 23.) | ✅ **Erledigt** (Leon H) | DB-Enabler steht |
| **DTB-54** schema.sql einspielen | 🟡 In Arbeit | 🔵 **Wird überprüft** (Leon H, PR #59) | fast durch |
| **DTB-55** Connection-Helper | 🟡 In Arbeit | 🔵 **Wird überprüft** (Leon H, PR #58/#61) | **entblockt DTB-28** nach Merge |
| **DTB-32** Taupunkt (Magnus) | ⬜ (Petzold) | 🔵 **Wird überprüft** (**Ganter**, PR #64) | Owner gewechselt; Vorarbeit DTB-38 |
| **DTB-22** No-Hardcode-Rule | ⬜ offen | 🟡 **In Arbeit** (Petzold) | Lint/PR-Template |
| **DTB-39** Betriebsmodell+Latenz | ⬜ offen | 🟡 **In Arbeit** (Lucas) | Entscheidungslog E-30/31 |
| **DTB-33** 30-min-Trendprognose | ⬜ offen | 🟡 **In Arbeit** (Lucas) | FA-06 minimal |
| **DTB-48** Fail-safe-ADR | „E-32" | ⬜ offen, jetzt **ADR E-39** | E-Nummer korrigiert (E-32 = „Niederschlag gestrichen") |

**Neu in Jira (waren im 23.06.-Dok nicht):**
- **DTB-58** Poller: Stale-Erkennung für G1-Snapshots (**>120 s** — Contract-Wert, war fälschlich „180 s") — *Ganter, offen*
- **DTB-59** Poller: `GET /health` von G1 abfragen + auswerten — *Lucas, offen*
- **DTB-60** Poller: `dew_point_c` aus `air_temp_c`+`humidity_pct` berechnen — *Ganter, in Review (PR #66)*
- **DTB-61** API: SSE-Alarm-Stream `GET /v1/alarms/stream` (Push, E-37) — *Petzold, offen (High)* — **neu erstellt 25.06.**; schließt Contract-Lücke (Push-Komponente; Poll/Resync/Ack = DTB-31/24)
- **DTB-62** API: `GET /v1/thresholds` (Schwellenwerte lesen, NF-07) — *Arash, offen (Medium)* — **neu erstellt 25.06.**; Arashs erste Task (einfach, RB-01-neutral; Ändern → später NF-07)

---

## Epics & Tasks hierarchisch (Live-Stand 25.06.)

### DTB-1 — E-01 Setup & Repo-Scaffolding *(M1, P0)* — **faktisch fertig, Epic-Status nachziehen**
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-2 | P0.1 Stack-Entscheidung + Begründung | ✅ Erledigt | Lucas | MySQL/PyMySQL final (E-35) |
| DTB-50 | P0.2 Repo-Struktur (`src/ tests/ config/`) | ✅ Erledigt | Lucas | Backend-Root = `04-Source-code/` |
| DTB-51 | P0.3 Grundgerüst `GET /v1/health` | ✅ Erledigt | Lucas | Test grün auf `main` |
| DTB-52 | P0.4 Branch/PR-Konventionen + DoR/DoD | ✅ Erledigt | Lucas | #55 gemergt |
| DTB-53 | Setup: Dev-DB-Zugang (native MariaDB) | ✅ Erledigt | Leon H | DB-Enabler steht |
| DTB-54 | Setup: schema.sql gegen MariaDB einspielen | 🔵 Wird überprüft | Leon H | **PR #59** |
| DTB-55 | Setup: PyMySQL-Connection-Helper + Env-Config | 🔵 Wird überprüft | Leon H | **PR #58/#61** — blockt DTB-28 |
| DTB-56 | PyMySQL in pyproject + Entscheidungslog (E-35) | ⬜ Zu erledigen | Leon H | nach #61 |
| DTB-16 | P0.5 Config-Grundstruktur (Duplikat zu DTB-15) | ✅ Erledigt | Lucas | ignorieren |

### DTB-6 — E-07 Schwellenwerte-Parametrierung *(M1)*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-15 | thresholds.json + validierender Loader | ✅ Erledigt | Petzold | **Enabler DTB-38**; DUMMY-Werte, parametrierbar |
| DTB-22 | No-Hardcode-Rule (Lint + PR-Template) | 🟡 In Arbeit | Petzold | vor Assessment-Code abschließen |

### DTB-7 — E-02 API/Datenmodell-Naht (Contract-First) *(M2)* — **NAHT EINGEFROREN ✅**
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-12 | P1.1 Datenmodell-Schema festzurren | ✅ Erledigt | Lucas | 6 Pydantic-Modelle + schema.sql |
| DTB-19 | P1.2 OpenAPI-Spez v1 | ✅ Erledigt | Ganter | #48 gemergt |
| DTB-26 | P1.3 Seam-Sync G1+G3 | ✅ Erledigt | Ganter | beidseitiges Sign-off |
| DTB-35 | P1.4 Contract v1 einfrieren + kommunizieren | ✅ Erledigt | Lucas | **v1.0 EINGEFROREN** — Rest: Tag + G3-Versand |

### DTB-8 — E-03 T0 Vertical Slice *(M2)* — **🔴 KRITISCHER PFAD**
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-18 | P2.1 Poller-Client gegen G1 `/current` + Validierung | ✅ Erledigt | Andi | auf `main` |
| DTB-32 | P2.3 Taupunkt-Berechnung (Magnus) | 🔵 Wird überprüft | Ganter | **PR #64** — Vorarbeit DTB-38 |
| DTB-28 | P2.2 Persistenz (Repository-Pattern) | ⬜ Zu erledigen | Lucas | **wartet auf #61-Merge** |
| DTB-38 | P2.4 Bewertungsmodul — 4-Stufen-Logik | ⬜ **Zu erledigen** | **Lucas** | **KRITISCHER PFAD — noch nicht begonnen, `assessment/` leer** |
| DTB-43 | P2.5 `GET /v1/assessment/current` Endpoint | ⬜ Zu erledigen | **— (kein Owner!)** | hängt von **DTB-38** ab; **Owner setzen** |
| DTB-46 | P2.6 Unit-Tests Bewertung (≥80 % Coverage) | ⬜ Zu erledigen | Petzold | hängt von DTB-38 |

### DTB-4 — E-08 Testing & CI/CD Pipeline *(M2)*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-11 | CI/CD-Setup (`test.yml`) | ✅ Erledigt | Petzold | Gate aktiv (3.12/3.14-Matrix) |
| DTB-25 | P0.6 pytest-Setup + CI-Gate | ✅ Erledigt | Lucas | — |
| DTB-21 | pytest-Konfiguration + Fixtures | ⬜ Zu erledigen | Petzold | DB-Test-Strategie offen |
| DTB-57 | Pi-Betrieb: Retention/Rotation | ⬜ Zu erledigen | Petzold | Optional/T3 |

### DTB-5 — E-04 T1 Kernfunktion *(M3)*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-13 | P3.1 Plausibilität + Stale-Erkennung | ⬜ Zu erledigen | Andi | M3 |
| DTB-20 | P3.2 Sensor-Defekt-Erkennung | ⬜ Zu erledigen | Leon H | M3 |
| DTB-27 | P3.3 Alarm-Generierung + Hysterese | ⬜ Zu erledigen | Lucas | M3 |
| DTB-31 | P3.4 `GET /v1/alarms` Endpoint | ⬜ Zu erledigen | Lucas | kann parallel laufen |
| DTB-37 | P3.5 Restliche Messgrößen (RH, Druck) | ⬜ Zu erledigen | Lucas | Schema da |
| DTB-41 | P3.6 Integrationstest Ingest→Bewertung→API | ⬜ Zu erledigen | Lucas | M3 |
| DTB-49 | P3.7 Fail-safe-Test (Stale/Defekt → nie GRÜN) | ⬜ Zu erledigen | Petzold | M3 — hängt an DTB-38/48 |
| DTB-58 | Poller: Stale-Erkennung (**>120 s**) | ⬜ Zu erledigen | Ganter | **neu** — gehört zu Fail-safe; Contract = 120 s (war falsch „180 s") |
| DTB-59 | Poller: G1 `GET /health` auswerten | ⬜ Zu erledigen | Lucas | **neu** — gehört zu Fail-safe |

### DTB-9 — E-05 T2 Sicherheit & Betrieb *(M3)* — *Epic-Owner: Ganter*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-24 | P4.1 Alarm-Quittierung `POST /v1/alarms/{id}/ack` | ⬜ Zu erledigen | Lucas | M3 |
| DTB-29 | P4.2 Audit-Log (append-only Event-Log) | ⬜ Zu erledigen | Leon H | M3 |
| DTB-34 | P4.4 Historie `GET /v1/readings?from=&to=` | ⬜ Zu erledigen | Petzold | M3, niedrige Prio |
| DTB-42 | P4.5 RB-01-Nachweis (kein Aktor-Endpoint) | ⬜ Zu erledigen | Arash | **wichtig (Sicherheit)** |

### DTB-3 — E-09 Korrekturen & Nachträge *(M3)*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-33 | P2.4b Einfache 30-min-Trendprognose | 🟡 In Arbeit | Lucas | FA-06 Muss; entkoppelbar |
| DTB-39 | AE-01/NF-02 Betriebsmodell + Latenz-Zielwert | 🟡 In Arbeit | Lucas | Entscheidungslog E-30/E-31 |
| DTB-45 | P5.4b Individuelle Entscheidungsreflexionen (40 %) | ⬜ Zu erledigen | **— (kein Owner!)** | **11 Personen zuweisen** (Koordination Lucas) |
| DTB-48 | ADR **E-39** Fail-safe Multi-Layer | ⬜ Zu erledigen | **Lucas** | **vor DTB-38/13/20** |

### DTB-10 — E-06 Integration, Test & Demo *(M3)*
| Ticket | Titel | Status | Owner | Bemerkung |
|---|---|---|---|---|
| DTB-17 | P5.1 E2E-Integration mit G1 | ⬜ Zu erledigen | Lucas | M3 |
| DTB-23 | P5.2 E2E-Integration mit G3 | ⬜ Zu erledigen | Lucas | M3 |
| DTB-30 | P5.3 Testprotokoll (Abnahme-Checkliste) | ⬜ Zu erledigen | Amelie Berger | **Highest Prio M3** |
| DTB-36 | P5.4a Gruppen-Entscheidungslogbuch finalisieren | ⬜ Zu erledigen | Petzold | kanonische E-Einträge |
| DTB-40 | P5.4b Individuelle Reflexion je Person | ✅ Erledigt (Jira) | jede Person | ⚠️ **inhaltlich NICHT erledigt** — echter Tracker ist DTB-45 |
| DTB-44 | P5.5 Abschlusspräsentation + Demo-Skript | ⬜ Zu erledigen | Lucas Landmann | M3 |
| DTB-47 | P5.6 Reflexion Wasserfall vs. Scrum | ⬜ Zu erledigen | Lucas Landmann | M3 |

---

## Lucas’ persönliche Prioritätenliste — ab heute (25.06.)

> Reihenfolge nach kritischem Pfad / Blockerwirkung. Die alte DB-Setup-Top-3 ist **erledigt/delegiert** und entfällt.

### Sofort (heute, Do 25.06.)
1. **PR-Triage** (siehe Abschnitt oben): DB-Kette mergen (#59 → #61), Taupunkt/Poller (#64/#66), Doku (#65/#67); **#62 + #63 schließen**. → räumt den Stau und entblockt DTB-28.
2. **DTB-48 — ADR E-39 „Fail-safe Multi-Layer"** schreiben. Reine Doku/Entscheidung, **entkoppelt**, muss aber **vor DTB-38** stehen (Logik baut darauf auf).
3. **Contract abschließen (mechanisch):** Git-Tag `api-v1.0` setzen + Versandkopie `G2-API-v1-openapi.yaml` an G3 + G3-Lead-Name im Bestätigungsblock nachtragen.

### Diese Woche (M2-Druck — der eigentliche kritische Pfad)
4. **DTB-38 — Bewertungsmodul 4-Stufen (TDD).** **RED zuerst:** die zwei dokumentierten Vorfälle (Fehlalarm trockene Kälte −2,1 °C / übersehene Eisbildung +1,2 °C) **und** den Fail-safe-Fall als benannte Testfälle. Gegen **Config (DTB-15 ✅)** + Repository-**Interface** bauen — **nicht** auf die DB warten. Schwellen **parametrierbar**, nichts hardcoden (G1-Finalwerte kommen noch).
5. **DTB-28 — Persistenz (Repository-Pattern)** starten, **sobald #61 gemergt** ist (mit Andi/Arash).
6. **DTB-43 — `GET /v1/assessment/current`** (hängt an DTB-38) → schließt den **T0-Vertical-Slice**. ⚠️ **Owner ist noch leer — setzen** (du oder Hartling/Ganter).
7. **Live-Durchstich testen:** Poller → DB → Bewertung → `/assessment/current` wirklich starten (nicht „sieht korrekt aus").
8. **DTB-39 + DTB-33** abschließen (beide „In Arbeit"): Betriebsmodell/Latenz (E-30/31) und 30-min-Trendprognose minimal.

### Koordination / Delegation (nur anstoßen, nicht selbst bauen)
9. **DTB-46** Unit-Tests Bewertung ≥80 % → Petzold, parallel zu DTB-38.
10. **DTB-45** — Zuordnung der 11 individuellen Reflexionen (Owner setzen, nur koordinieren — 40 % ist Einzelleistung).
11. **DTB-30** Testprotokoll → Amelie; **DTB-42** RB-01-Nachweis → Arash; **DTB-58/59** Poller-Fail-safe ggf. an Andi/Ganter geben.
12. **Status-Hygiene Jira:** Epic **DTB-1** auf „Erledigt"; nach den Merges DTB-32/54/55/60 schließen.

---

## Wichtige Abhängigkeiten & kritischer Pfad (T0-Slice, Epic DTB-8)

```
DTB-18 (Poller) ✅ ─────────────► DTB-28 (Persistenz) ──┐  (wartet auf #61-Merge)
DTB-55 (Conn-Helper) 🔵 #61 ──────┘                      │
                                                         ▼
DTB-15 (Config) ✅ ──────────────►  DTB-38 (Bewertung 4-Stufen) ──► DTB-43 (/assessment/current) ──► T0-Slice ✔
DTB-32 (Taupunkt) 🔵 #64 ────────►        ▲                                │
DTB-48 (Fail-safe-ADR E-39) ⬜ ──────────►┘                                ▼
                                                                    DTB-46 (Unit-Tests ≥80 %)
```

**Engpass:** Alles läuft auf **DTB-38** zu, und das ist **noch nicht angefangen** (`assessment/`-Modul leer). Vorarbeiten (Config ✅, Taupunkt #64, Fail-safe-ADR) sind klein/in Reichweite — sobald die durch sind, ist DTB-38 der einzige echte Blocker für den lauffähigen M2-Slice.

---

## Hinweise & Stolpersteine

- **DTB-40 vs. DTB-45:** DTB-40 steht in Jira auf „Erledigt", die individuellen Reflexionen sind inhaltlich aber **nicht** geschrieben. Der echte offene Tracker ist **DTB-45** (noch ohne Owner). Für M3 fest einplanen — und denk an die Klarstellung: die **40 % sind reines Prüfungs-Notengewicht**, kein Grund, technische Entscheidungen zurückzudelegieren.
- **DTB-48 = ADR E-39** (nicht mehr E-32 — E-32 wurde „Niederschlag gestrichen / Customer-Scope"). Beim Schreiben die E-Nummer konsistent halten.
- **„Kein-fetch"-PRs:** #62 (DTB-19-Dublette, bereits via #48 auf `main`) und #63 (Connection-Helper-Fork ohne aktive Checks) sind genau die Fälle, die dich genervt haben → **schließen**. Künftig in der PR-Vorlage (DTB-52/DoR) „vor Branch: `git fetch && rebase auf main`" als Pflichtpunkt aufnehmen.
- **3 Connection-Helper-Branches** (#58/#61/#63) für DTB-55 → **#61 ist die saubere Konsolidierung**. Vor weiteren Storage-Tasks vereinheitlichen, sonst Doppelstruktur.
- **`/v1`-Router fehlt noch:** Backend bedient bisher nur `/v1/health`; die fachlichen Router (`/v1/assessment`, `/v1/alarms`, `/v1/readings`) + CORS-Middleware + Fail-safe-Durchsetzung in `assessment/` entstehen mit DTB-38/DTB-28.
- **Personaldecke M2:** im Kern weiterhin v. a. Lucas auf dem kritischen Pfad (DTB-38/28/43). Taupunkt (Ganter) und DB-Kette (Leon H) sind gut delegiert — halte den Rest des Teams an klar abgegrenzten T1/M3-Tasks beschäftigt, damit der kritische Pfad frei bleibt.

---

*Quelle: Jira-Projekt DTB (archidox-devs, 59 Vorgänge) + Git/PRs `Alarmsystem-Dev` + `erinnerung/stand.md`. Live-Abgleich 25.06.2026. — architekt*
