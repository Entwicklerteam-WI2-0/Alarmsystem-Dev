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
