# Aktueller Stand

> Stand: 2026-06-22 · Pflege: primär Lucas (Architekt); Team pflegt zusätzlich ein (s. `erinnerung/README.md`). Beim Sitzungsstart von `uni:start` gelesen.

## Woran wir gerade arbeiten
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
  fail-loud `ConfigError`) + `test_config_loading.py` (**12 Tests, 100 % Line+Branch-Cov**, ruff sauber).
  **Enabler für DTB-38.**
- **Scope bewusst begrenzt:** nur echte Schwellen; `taupunkt_magnus`/`hysterese`/`datenstatus`/Prognosehorizont
  **nicht** aufgenommen (gehören zu DTB-32/-27/-18/-33, in Jira **unzugewiesen**; Magnus = physikal. Konstanten).
- **PR gegen `main` offen** (Branch gepusht; Review Arezo/Amelie, Merge Lucas). Selbstreview WP5
  (quality-gate/python-review/test-coverage) durch. 3 Einträge im persönlichen `Petzold-Entscheidungslog`.
- **Neu offen:** (1) **DTB-11-Unstimmigkeit** in `04-Source-code/requirements.txt`: `sqlalchemy`/`alembic`
  vs. E-35-Vorgabe „PyMySQL, kein SQLAlchemy" → Klärung mit Lucas vor PR-#18-Merge (Jira-Kommentar an DTB-11
  gesetzt). (2) vorbestehender ruff-Fehler `src/ingest/__init__.py:1` (E501, Scaffolding-Code).
