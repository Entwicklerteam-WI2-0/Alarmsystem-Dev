# Aktueller Stand

> Stand: 2026-06-25 · Pflege: primär Lucas (Architekt); Team pflegt zusätzlich ein (s. `erinnerung/README.md`). Beim Sitzungsstart von `uni:start` gelesen.

## Woran wir gerade arbeiten
- **DTB-54 (schema.sql einspielen, Andi & Leon):** Apply-Schritt + `migrations/grants.sql` (append-only
  via GRANT statt Trigger, NF-09) dokumentiert; santa-loop-reviewed; Commit `d2aa4bc` lokal auf
  `feat/dtb-54-schema-apply` (ungepusht). **Offen:** Init-Schritt (CREATE DB/USER) im README + DoD-Apply-Beweis
  bei Pi-MariaDB-Init. → Status „Wird überprüft".
- **G2 Backend (Alarmsystem ANR):** Woche 2. **Projektplan + Jira-Backlog (Projekt DTB)** steht:
  9 Epics / 43 Tasks (DTB-1..DTB-52) + 43 "Blocks"-Abhängigkeitslinks. Begleitdoc:
  `02-Arbeitsdokumente/Projektplan-Jira-Backlog-G2.md`.
- **Stack-Update MySQL (#20, Surprise-Vorgabe 22.06.):** Die Geschäftsleitung gibt **MySQL/MariaDB**
  verbindlich vor (`02-Arbeitsdokumente/Surprise Anforderungen.txt`) — **ersetzt SQLite** im bisherigen T0
  (FastAPI/HTTP bleiben; dev = prod via Docker-Compose). Dokumentiert in `Backend-Konzept.md §6/§6a`,
  `README.md` und Entscheidungslog **E-29**. Betrifft Datenmodell, requirements und CI; DB-Treiber nötig.
- **CI/CD-Setup (DTB-11):** Grundgerüst fertig & reviewed → **PR #18** (`feat/ci-base`), **auf Eis bis DTB-1**
  (CI wird erst mit `src/`+Tests grün). E-08 formal nachziehen → DTB-2.
- **P0-Grundgerüst gelegt** (`feat/p0-backend-grundgeruest`, Commit 80d5dd1, lokal/ungepusht): `src/`-Struktur
  (§7) + FastAPI `GET /health` (Test grün) + MariaDB-Compose + `pyproject`/`requirements`. ⚠️ **Repo-Root noch
  abzugleichen:** liegt in `04-Source-code/`, DB-Engineer-Artefakte in `04-Source-code/source/`.

## Als Nächstes (kritischer Pfad)
1. **P0/Scaffolding** (DTB-1: DTB-2/50/51/52) — `src/`-Struktur + erste Tests, jetzt inkl. MariaDB via
   Docker-Compose → macht CI grün-fähig.
2. **Contract-first**: API + Datenmodell (E-02 / DTB-7) + Seam-Sync mit G1+G3 bis Di → M2. **Jetzt MySQL/MariaDB statt SQLite.**
3. **T0 Vertical Slice** (E-03 / DTB-8): assessment-Kern + beide Vorfall-Tests + Fail-safe (≥80 % Coverage).
4. Danach: **PR #18 mergen** + Branch-Protection „Require status checks" (Check `test`); **MySQL-DB-Treiber** in requirements/CI ergänzen.

## Offene Punkte / Blocker
- **MySQL-Vorgabe vollständig eingearbeitet (22.06.):** Backend-Konzept §6/§6a, README, Entscheidungslog
  E-29 (Begründung ausformuliert), Tasks P0.1 und Pi-Anleitung konsistent nachgezogen. PR #21 (mergebar).
  G1-Schwellen/reale Last später gegen §6a plausibilisieren.
- **M2 (Ende Woche 2) kritisch:** nur 1 echter Backend-Dev (Lucas) auf 7 kritischen Tasks → Petzold früh
  einbinden, P3 bewusst nach Woche 3.
- **Echte Schwellenwerte von G1** ausstehend (~2 Tage) → `config/` parametrierbar halten, NIE hardcoden.
- **DB-Wechsel SQLite→MySQL (#20)** in Datenmodell, requirements und CI nachziehen.
- **⚠️ Repo-Root-Divergenz P0 (vor Push klären):** Grundgerüst in `04-Source-code/`, DB-Engineer legt
  `.env`/Datenmodell in `04-Source-code/source/` → **einen** Backend-Root festlegen, sonst Doppelstruktur.
- **⚠️ DB-Setup-Divergenz:** `docker-compose.yml` (MariaDB-Container, §6/E-29) vs. real **native** Pi-MariaDB
  (`feat/db-pi-setup`) → vor Storage-Impl abgleichen.
- **Branch-Cleanup offen:** abgearbeitete Branches entfernen, **`feat/ci-base` (Johannes) einfrieren/verschonen**;
  PR-Status noch abzurufen.
- **Review-Lücken (offen):** Systemkontext-Diagramm (Pflicht W1) ohne Task; NF-07-Auth für `POST /config`
  ohne Task; Config-Redundanz (E-05/E-07/E-09) konsolidieren.
- **Ruleset:** blockierte Feature-Branch-Pushes → Lucas beschränkt es auf `main` (Schutz für `main` bleibt).

## Update [22.06., ~18:35] — Jira-Board + Doku nachgezogen (architekt)
- **DTB-Board MySQL-überarbeitet** (20 Edits + 5 neue Tasks DTB-53–57 + 2 Links; Epic **E-04→M3**; Redundanzen aufgelöst). **Lucas = Assignee** auf Naht (DTB-12/19/26/35) + Bewertung **DTB-38**.
- **Repo-Root-Divergenz GEKLÄRT:** Backend-Root = **`04-Source-code/`**; README an Struktur + MySQL-Setup angepasst; neuer **`05-Fortschrittslog/`**. **PR #29 → main**.
- **Neu offen:** E-ID-Kollision im Entscheidungslog (E-29 mehrfach → Vorschlag E-30/31/32, Lucas im Doc auflösen); Jira-Pfad-Präzisierung + Redundanz-Tasks DTB-53/56 (Gerüst hat docker-compose/PyMySQL schon); DTB-16 Duplikat schließen; `Projektplan-Jira-Backlog-G2.md` noch SQLite.

## Update [22.06., ~23:45] — G1-Naht Pull + 3-Faktor + Feuchte-Fix gemergt (architekt)
- **G1-Naht Push→Pull (E-31):** G1 stellt `GET /current` (Snapshot + `measured_at`) + `GET /health` bereit;
  G2 baut Poller (Intervall ≤ 60 s, selbst bestimmt), **kein** G2-`POST /readings` mehr. E-30 (Push) als „revidiert" markiert.
- **Niederschlag gestrichen (E-32, Customer-Scope):** als Faktor **und** Feld `precip_type` raus → **3-Faktor-Bewertung** `T_s + ΔT + RH`.
- **Feuchte-Fix (E-33):** „Feuchte vorhanden" := `ΔT ≤ 1,0` (Oberfläche), **nicht** Luft-`RH ≥ 90 %` — behebt
  Vorfall-1-Fehlalarm (92 % Luftfeuchte/trockene Oberfläche → GELB). **Keine neue Messgröße.**
- Konsistent über Backend-Konzept/Schwellenwerte/README/Tasks/Jira/Usecase/Agents-gpt/ingest-Docstring
  + neues `Umstellung-Pull-3Faktor-Faktenblatt.md`. **PR #32 gemergt** (455d71f), main aktuell.
- **40%-Klarstellung** (nur Prüfungs-Notengewicht, KEINE Arbeits-/Architekturregel) in CLAUDE.md/AGENTS.md + global.
- **Branch-Cleanup erledigt:** 5 abgearbeitete Branches gelöscht, **`feat/ci-base` (#18) unberührt**, Remote geprunet.
- **Neu offen:** (1) 40%-Klarstellung in `Devteam-vibecodes`-Skill-Sources nachziehen. (2) **G1-Seam-Sync final**
  (`humidity_pct` = Luftfeuchte; Feldnamen + `measured_at` bestätigen; Contract **P1.4** einfrieren).
  (3) E-ID-Kollision E-29/E-30 (Altbestand, DRI Lucas).

## Update [23.06., ~00:10] — Kaskade-Fix Bewertungslogik (E-34) + Jira-Link-Cleanup (architekt)
- **Bewertungslogik gehärtet (E-34, PR #35 gemergt → 3c703b0):** `Schwellenwerte.md` §2 als **priorisierte
  Kaskade** (ROT→ORANGE→GELB→GRÜN, erste zutreffende gewinnt). Schließt **Klassifikationslücke**
  `0 °C < T_s ≤ +1,0 °C` mit Feuchte (war undefiniert) → **GELB-Auffang**; **ROT-Vorrang** explizit;
  **Fail-safe** bei nicht berechenbarem `ΔT` (konservativ Feuchte = wahr → nie GRÜN). **Keine Schwellen
  geändert**; beide Vorfälle unverändert aufgelöst. Pseudocode-Vorgabe für DTB-38 hinterlegt.
- **Jira DTB:** zirkulärer Link **10011** (DTB-14 ↔ DTB-38) erkannt; korrekt ist **DTB-15** (Link 10075,
  bereits vorhanden). MCP kann Links **nicht** löschen → DTB-14 + DTB-38 mit `----DELETE----`-Marker versehen.
- **Branch-Cleanup:** lokale verwaiste Branches entfernt; `main` ff auf 3c703b0; **PR #18 `feat/ci-base` verschont.**
- **Neu offen:** (1) **Jira-Link 10011 manuell löschen** (Jira-UI Papierkorb ODER REST
  `DELETE /rest/api/3/issueLink/10011`). (2) untracked `02-Arbeitsdokumente/Task-Zuweisungsvorschlag-G2.md`
  (nicht vom Architekt) — Ablage/Commit klären. (3) Hysterese-Begriff „untere Schwelle" in §2 präzisieren;
  `assess_ice_risk`-Signatur (RH redundant, da nur `T_d`-Input).

## Update [23.06., ~12:10] — DTB-15 Config-Loader fertig + PR offen (architekt/Petzold)
- **DTB-15 (Config-Infrastructure) umgesetzt** (`feat/config-thresholds-loader`, Commit b1a60ae):
  `04-Source-code/config/thresholds.json` (vereisung-Kaskade + Prognoseschwelle, DUMMY-Werte §2, DB-frei) +
  `src/config/loader.py` (`load_thresholds()` → typisiertes `frozen` `Thresholds`, validiert Struktur+Werte,
  fail-loud `ConfigError`) + `tests/test_config_loading.py` (**12 Tests, 100 % Line+Branch-Coverage**, ruff sauber).
  **Enabler für DTB-38.**
- **Scope bewusst begrenzt:** nur echte Schwellen; `taupunkt_magnus`/`hysterese`/`datenstatus`/Prognosehorizont
  **nicht** aufgenommen (gehören zu DTB-32/-27/-18/-33, in Jira **unzugewiesen**; Magnus = physikal. Konstanten).
- **PR gegen `main` offen** (Branch gepusht; Review Arezo/Amelie, Merge Lucas). Selbstreview WP5
  (quality-gate/python-review/test-coverage) durch. 3 Einträge im persönlichen `Petzold-Entscheidungslog`.
- **Neu offen:** (1) **DTB-11-Unstimmigkeit** in `04-Source-code/requirements.txt`: `sqlalchemy`/`alembic`
  vs. E-35-Vorgabe „PyMySQL, kein SQLAlchemy" → Klärung mit Lucas vor PR-#18-Merge (Jira-Kommentar an DTB-11
  gesetzt). (2) vorbestehender ruff-Fehler `src/ingest/__init__.py:1` (E501, Scaffolding-Code).

## Update [23.06., ~12:15] — Stack-Pivot E-35 (PyMySQL, kein Docker) + DTB-12 Datenmodell (architekt)
- **E-35 (revidiert E-29-Umsetzung; DB-Mandat MySQL/MariaDB bleibt):** **kein SQLAlchemy** → rohes PyMySQL
  hinter Repository-Pattern (parametrisierte Queries Pflicht); **kein Alembic** → handgeschriebenes
  `schema.sql`; **kein Docker** → native MariaDB (Pi via Tunnel / lokal). Doku: `Stack-Entscheidung-P0.1.md`,
  Entscheidungslog **E-35** (+ persönl. Lucas-Log). `requirements.txt` bereinigt (SQLAlchemy/Alembic raus).
- **DTB-12 (P1.1) fertig — PR #37 gemergt:** 6 Pydantic-Modelle + Enums (risk_level inkl. `unknown`/Fail-safe)
  + `migrations/schema.sql` (DATETIME(3) UTC, CHECK-Enums, FKs) + `tests/test_model.py` (**8 grün**).
  `reading` = G1-Block (kein `ice_indicator`); `assessment` mit Entscheidungs-Snapshot (audit-fest).
  **5/6 Entitäten fix; `reading` wartet auf G1-Feldnamen-Freeze (P1.4).**
- **Jira:** DTB-2/12/28/53/54/55/56 + DTB-11 auf E-35 umgeschrieben; DTB-51-Pfad korrigiert (`src/main.py`).
- **PR #38 offen:** Fortschrittslog + Lucas-Entscheidungslog (E-35) + README (E-35-Korrekturen, Datenfluss,
  neue G2→G3-Serving-Sektion).
- **Offen/weiter:** **Backend-Konzept §6/§7** echte E-35-Prosa (noch SQLAlchemy/Docker) + `docker-compose.yml`
  entfernen + `Projektplan-Jira-Backlog-G2.md` (SQLite) nachziehen. CI-DB-Bereitstellung (DTB-11) mit Johannes.
  Jira-Link 10011 (Altbestand) manuell löschen. G1-Seam-Sync (P1.4) → dann DTB-19 OpenAPI + DTB-28 Persistenz.

## Update [23.06., ~14:15] — API-Contract verankert + Backlog-Übersicht (architekt)
- **G1→G2 API-Vertrag final dokumentiert:** `Backend-Konzept.md` §9 enthält jetzt den verbindlichen
  JSON-Contract (`GET /current`, `GET /health`, Pflichtfelder, Verhandlungsposition). Ebenfalls in
  `04-Source-code/README.md`, `CLAUDE.md` und `AGENTS.md` als **Mandatory Read** verlinkt.
- **DTB-15 (Config-Loader)** auf `main` reviewed: Code + Tests passen zu `Schwellenwerte.md` §2; spätere
  Verknüpfung mit `ThresholdSet`-DB-Entity für DTB-38 vormerken.
- **P0.3 (DTB-51)** Code auf `main` verifiziert (`src/main.py` + `tests/test_health.py` grün); Jira-Status
  noch „In Arbeit" → Update ausstehend.
- **Persönliche Backlog-Übersicht** erstellt (`Desktop/DTB-Backlog-Uebersicht.md`): Epic-Hierarchie,
  Lucas-Prioritäten, Blocker/Abhängigkeiten.
- **main aktuell:** 57a2c5d "Add API contract FROZEN v1 (draft) (#44)".
- **Neu offen:** Jira-Status DTB-1/DTB-51 aktualisieren; DTB-53/54/55/56 (DB-Setup) angehen; DTB-35
  Contract an G1/G3 kommunizieren; Jira-Link 10011 löschen.

## Update [23.06., ~14:30] — Alarm-Push (E-37) + Doku-Drift-Fix (SQLAlchemy/Docker→E-35, `/v1/`) (architekt)
- **E-37 — Alarme = Push via SSE** (`GET /v1/alarms/stream`); `GET /v1/alarms` nur Zustands-Resync, **kein
  Poll-Scan**. Alarme sind Events → Polling semantisch falsch/latenzbehaftet; SSE = Push ohne dass G3 etwas
  hostet; `GET /alarms` als Sicherheits-Backstop (Disconnect-Resync). SSE-Impl = T2. Doku nachgezogen
  (Backend-Konzept §9.2, READMEs, `API_FROZEN_v1.md`, `Team-Sync-Entscheidungen.md`).
- **Doku-Drift bereinigt (E-35/E-36/AE-03):** Backend-Konzept §4/§6/§6a/§7/§9 + Root-README + AGENTS auf
  **rohes PyMySQL / native MariaDB / kein Docker / kein Alembic** + **`/v1/`**-Endpoints korrigiert (waren noch
  SQLAlchemy/Docker bzw. ohne Versionspräfix). `claude-sync.md` (geteilte Agent-Config) auf E-35-Stand.
- **Architektur-Klarstellung:** G2 = **Server** zu G3 (G3 konsumiert per GET; Alarme via SSE-Push),
  G2 = **Client** zu G1 (pollt `GET /current`). Grundstruktur war in den Docs **bereits korrekt** — Drift
  betraf nur Stack-Prosa + fehlendes `/v1/`.
- **⚠️ Parallel-Arbeit erkannt:** `API_FROZEN_v1.md` ist bereits via **#44 (57a2c5d)** auf `main` (DTB-35-Draft).
  Lokaler Branch `feat/dtb-35-contract-freeze-v1` enthält daher eine **Dublette** + zusätzlich die Drift-Fixes/E-37
  — **vor Push gegen aktuelles `main` (57a2c5d) rebasen/abgleichen**, sonst Konflikt/Doppelung. **Nichts gepusht.**
- **Offen/weiter:** Branch rebasen + Dublette auflösen; Drift-Fixes + E-37 als PR; `docker-compose.yml` physisch
  entfernen (E-35); DTB-19 `openapi.yaml` (Luca) muss `/v1/alarms/stream` + `/v1/alarms` führen; Tag `api-v1.0`
  erst nach G1/G3-Sign-off.

## Update [23.06., ~15:51] — DTB-19 OpenAPI v1 Spec fertig (backend-dev/Luca)
- **DTB-19 (P1.2) umgesetzt** (`feat/dtb-19-openapi-v1`, Commits fbadf02 + 778bf40, **lokal/ungepusht**):
  `04-Source-code/docs/api/v1/openapi.yaml` (G2-API, 6 Ops inkl. `/v1/alarms/stream` SSE + `/v1/alarms`
  Resync) + `g1-consumed.openapi.yaml` (konsumierter G1-Vertrag, 2 Ops). Formale Abschrift von
  `API_FROZEN_v1.md`; Fail-safe NF-01 + RB-01 explizit. `openapi-spec-validator` grün; **santa-loop**-Review
  (3 MEDIUM-Fixes eingearbeitet).
- **Operationszahl** „≥ 15" (alte DoD) durch Architekten-Vorlage (DRI) **überholt** → Lean-Set ~6+2 maßgeblich
  (im Datei-Header dokumentiert).
- **Neu offen:** (1) Branch pushen + PR (DTB-19). (2) **DTB-26 G3-Sign-off** (`seam-sync-confirmed`)
  einsammeln — **G1-Seite: Lucas**. (3) Tag `api-v1.0` erst nach G1/G3-Bestätigung. (4) LOW-Nice-to-haves
  (Health-`enum`, SSE-`$ref`, ack-State, `driving_factor`-enum).

## Update [23.06., ~16:08] — DTB-19 PR #48 Review-Findings eingearbeitet (backend-dev/Luca)
- **PR #48 review-fest gemacht** (Commit 18c3648, **gepusht/in sync**): `/v1/alarms/stream` → `503`;
  `POST /v1/alarms/{id}/ack` → `409` bei Double-Ack (NF-09, nicht idempotent); `AckRequest.operator`
  → `minLength: 1`; g1-`status` → Sync-Hinweis auf `SensorStatus`. Validator erneut grün; doppelter 503
  (Web-Fix 865de56 + Fix) konsolidiert. DTB-19 damit fertig & review-fest.
- **Neu offen:** (1) **PR #48 mergen** (Reviewer/Lucas). (2) **DTB-26 G3-Sign-off** (`seam-sync-confirmed`)
  — G1-Seite: Lucas. (3) Tag `api-v1.0` erst nach G1/G3-Bestätigung. (4) LOW-Nice-to-haves offen
  (Health-`enum`, SSE-`$ref`, ack-State, `driving_factor`-enum).

## Update [23.06., ~22:00] — DTB-11 Test-CI abgeschlossen + Poller-Fail-safe-Fix (Petzold)
- **DTB-11 (Test-CI) fertig & gemergt (#50):** `.github/workflows/test.yml` gegen das `04-Source-code/`-Layout
  (`pytest --cov` ≥ 80 % + `ruff`); veralteter PR #18/`feat/ci-base` abgelöst & geschlossen.
  **Branch-Schutzregel „Require status checks" mit Check `test` aktiv.** Python-Matrix 3.12/3.14 +
  Aggregator-Check `test` nachgezogen (DTB-11b, #52).
- **Poller-Fail-safe-Fix (DTB-12, #53/#54):** beim CI-Selbstreview entdeckter NF-01-Bug (defektes optionales
  `pressure_hpa` → Crash statt `None`) per TDD gefixt; `poller.py` 100 % Coverage. Im vertieften Review
  verfeinert: pressure **nicht-blockierend** (loggt + `None`, Reading bleibt), `status=fault`→Ablehnung,
  `measured_at` **UTC-only**, spezifische `RepositoryError`.
- **main grün:** 62 Tests, 100 % Coverage, ruff sauber (`d86e8d6`). Lokale Branches aufgeräumt, Remote sauber.
- **Entscheidungen:** 8 neue Einträge im persönlichen `Petzold-Entscheidungslog` (noch lokal/uncommittet).
- **Neu offen:** (1) Entscheidungslog-Edit committen/pushen (Doku-PR). (2) DTB-11/DTB-12 Jira-Status manuell.
  (3) Kritischer Pfad: DB-Setup (DTB-53–56) + Persistenz (DTB-28) → dann Bewertungsmodul DTB-38.

## Update [25.06., ~04:00] — DTB-32 Taupunkt-Funktion + DTB-60 Poller-Taupunkt (backend-dev/Luca)
- **DTB-32 (P2.3) fertig:** reine Funktion `calculate_dew_point` (Magnus a=17,62/b=243,12 aus
  `Schwellenwerte.md` §1) in `src/assessment/utils.py`; Guards (RH∈(0,100], `isfinite`, Magnus-Pol →
  `ValueError`); 20 Tests inkl. Frost-/Negativ-Referenzwerte; Coverage `assessment` 100 %. Branch
  `feat/dtb-32-taupunkt-magnus` **gepusht**.
- **DTB-60 (gestapelt auf DTB-32) fertig:** Poller berechnet + plausibilisiert `dew_point_c`, füllt `Reading`.
  Fail-safe: `ValueError` (RH=0) → `None`; **Ergebnis-Plausibilisierung** `T_d < MIN_TEMP_C` → `None` (schließt
  RH≈0-Gap, sonst stilles GRÜN). 4 neue Poller-Tests, volle Suite **86 grün**, `poller.py` 100 %. Branch
  `feat/dtb-60-poller-taupunkt` **gepusht**.
- Beide via **TDD + santa-loop** (je 2 Prüfer + Moderator; je 1 echter Fail-safe-Blocker gefunden & gefixt).
  Persönl. Entscheidungen (DTB-32 strikter Rechner; DTB-60 Ergebnis-Plausibilisierung) im
  `Ganter-Entscheidungslog` auf `docs/ganter-entscheidungslog-dtb-32` **gepusht**.
- **Neu offen:** (1) **Merge-Reihenfolge:** DTB-32 → `main` zuerst, dann DTB-60 (Base umstellen/rebasen),
  Log-PR unabhängig; PR/Merge = Lucas-Freigabe (§7). (2) **Folge-Ticket:** DTB-38 muss `dew_point_c=None`
  als „Feuchte vorhanden=wahr" behandeln (`Schwellenwerte.md` §2 → nie GRÜN); DTB-12 `dew_point_c: float|None`
  absichern. (3) 3 offene PR-Branches (DTB-32, DTB-60, Entscheidungslog) — Luca hat hier keinen PR-Zugriff.

## Update [25.06., ~11:10] — DTB-60 (#66) Review + Review-Fixes gepusht (architekt)
- **PR #66 (DTB-60) reviewt** (Code-Review + `python-review`): Magnus-Werte unabhaengig nachgerechnet ✓,
  Fail-safe NF-01 sauber, keine CRITICAL/HIGH. **Review-Fixes verhaltensneutral eingebaut & gepusht**
  (`00de4c9`): `_compute_dew_point()` extrahiert; Konstante `MIN_PLAUSIBLE_DEW_POINT_C`; §3-Begruendung
  praezisiert; Tests WARNING-Level + Grenzwert (strict `<`). **87 gruen, `poller.py` 100 %, ruff sauber.**
- **Neu offen / kritischer Pfad:** (1) Merge-Reihenfolge: DTB-32 (#64) → main, dann #66 rebasen
  (PR/Merge = Lucas-Freigabe). (2) **DTB-38 (#68)** muss `dew_point_c=None` als „Feuchte vorhanden=wahr"
  behandeln (nie GRUEN) — Folge-Abhaengigkeit (heute neue Commits auf #68). (3) Layering ingest→assessment
  (M2, offen, Architekten-Call).

## Update [25.06., ~12:34] — DTB-28 fertig + PR #70 lokal konfliktfrei (architekt)
- **Backlog-Review** gegen Anfrage-G1.md/G3.md + Team-Sync: CRITICAL-Fix — DTB-58 Stale-Timeout
  war 180 s statt Contract-Wert **120 s** gefixt. **DTB-61** (SSE `GET /v1/alarms/stream`, Petzold) +
  **DTB-62** (`GET /v1/thresholds`, Arash) neu im Backlog.
- **DTB-28 fertig** — `ReadingRepository` auf main's `get_connection()`-Contextmanager portiert. Branch
  `feat/dtb-28-persistenz`, 9 Tests (1 immer / 8 MariaDB-skip). 129 Tests gruen, 94 % Coverage.
  Commit `17c81ce` — **lokal, UNGEPUSHT**.
- **PR #70 Konflikte lokal geloest** (7 Dateien, Branch `fix/pr70-conflicts`, Commit `552d182`) —
  **UNGEPUSHT. GitHub zeigt PR #70 weiterhin als konfliktreich.**
- **Nächster Schritt (DRINGEND):**
  1. Push `fix/pr70-conflicts` → `origin/docs/session-2026-06-25-backend-dev` (PR #70 GitHub-Konflikte).
  2. Push `feat/dtb-28-persistenz` + PR oeffnen.
  3. DTB-28 Jira auf „In Review"; DTB-43 (`GET /v1/assessment/current`) unassigned.
