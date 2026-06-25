# Entscheidungslog — Lucas (Systemarchitektur)

> **Zweck:** Nachvollziehbare Dokumentation der getroffenen Entscheidungen (Architektur, Organisation,
> Vorgehen) aus Sicht des Systemarchitekten — Pflichtdeliverable „Entscheidungslogbuch" und Grundlage
> für die Bewertung (Kriterium *Nachvollziehbarkeit technischer Entscheidungen*).
> **Format:** je Eintrag *Entscheidung · Begründung · verworfene Alternative · Bezug*. Lebendes Dokument.
> **Stand:** 23.06.2026 · **Bezug:** `Backend-Konzept.md`, `Schwellenwerte.md`, `Tasks+Projektplan.md`, `Usecase-quick.md`, `Surprise Anforderungen.txt`.

---

## A. Repository & Tooling

**E-01 — Ein konsolidiertes Arbeitsrepo (`Alarmsystem-Dev`, Org `Entwicklerteam-WI2-0`)**
- *Entscheidung:* Doku **und** Code in einem Team-Repo; frühere Ordner/Remotes (`technology-engeneering`, `Backend Sensor POC`) abgelöst.
- *Begründung:* Mehrere lokale Ordner auf wechselnde Remotes führten zu Push-Problemen und Divergenz (versehentlich vertauschter `.git`-Ordner). **Ein Repo = eine Wahrheit.**
- *Alternative:* getrennte Doku-/Code-Repos — verworfen: zu viel Sync-Overhead für 3 Wochen + unerfahrenes Team.

**E-02 — Ordnerstruktur `01-quellen / 02-Arbeitsdokumente / 03-abgaben`**
- *Begründung:* Read-only-Quellen, lebende Arbeitsdokumente und abgabefertige Stände sauber trennen → weniger „welche Datei gilt?".

**E-03 — Git-Workflow: Feature-Branch → PR → Review → `main`; `main` immer lauffähig; `CLAUDE.md`/`AGENTS.md` gitignored**
- *Begründung:* Reviewbarkeit + stabiler Hauptzweig; Agent-Instruktionsdateien sind lokal/tool-spezifisch, gehören nicht in die geteilte Historie.

**E-38 — Test-CI: Python-Matrix (3.12 + 3.14) gegen Syntax-Drift + `test`-Aggregator-Job für Branch-Protection-Kompatibilität**
- *Kontext/Task:* **DTB-11 (Test-CI, M2)** · **DTB-11b (Follow-up)** · schließt an **PR #50** (Basis-CI) an · betrifft `.github/workflows/test.yml` + Branch-Protection `required_status_checks` auf `main`. *Auslöser (zwei):* **(1)** Code-Review-Finding zu PR #50 — die Suite lief nur gegen Python **3.12** (Floor laut `pyproject.toml` `requires-python>=3.12` + `ruff target-version=py312`), aber lokale Dev-Maschinen laufen teils auf 3.13/3.14 (belegt durch `src/**/__pycache__`-Artefakte `cpython-313`/`cpython-314`). 3.13+-only-Syntax würde **lokal grün** und in **CI rot** (SyntaxError) durchgehen — ein klassisches „works on my machine". **(2)** Nach Einführung der Matrix blockierte der PR: die Branch-Protection verlangte den Check-Namen **`test`** (alter Einzel-Job-Name aus #50/#51), die Matrix erzeugt aber **`test (3.12)`/`test (3.14)`** → GitHub wartete ewig auf `test` („Waiting for status to be reported"), PR blieb trotz grüner Runs gesperrt.
- *Entscheidung (zwei Teile):*
  1. **Python-Matrix `["3.12", "3.14"]`** mit **`fail-fast: false`** — Floor + aktuelle Dev-Version; 3.14 fängt Syntax-Drift deterministisch ab. `fail-fast:false`, damit ein Vorfall auf der einen Version den anderen Run nicht abwürget (sonst sieht man den eigentlichen Fehler nicht).
  2. **Aggregator-Job `name: test` (job-id `test_status`)** statt Branch-Protection anzupassen: er wartet via `needs: [test]` auf die Matrix und wird **genau dann grün, wenn 3.12 UND 3.14 grün** waren (`if: always()` + explizite `needs.test.result`-Prüfung → bei Matrix-Fehlern **verlässlich rot statt skipped**, sonst würde der Required-Check nie erfüllt). Stellt den Check-Namen `test` wieder her, den die Protection verlangt.
- *Begründung (Entwurf — von Lucas zu prüfen/formulieren):* Die Matrix schließt die Lücke zwischen Dev-Umgebung (3.13/3.14) und CI-Floor (3.12) — Syntax, die nur neuere Pythons akzeptieren, fällt sonst erst in CI auf. **Der Aggregator statt der Protection-Anpassung**, damit der Workflow **self-contained** bleibt: eine externe Settings-Abhängigkeit (Protection-Checkliste bei jedem neuen Check-Namen manuell nachziehen) würde im Anfängerteam erfahrungsgemäß vergessen → ein Workflow-Fix ist robuster gegen künftige CI-Änderungen. `if: always()` + Exit-Logik statt bloßem `needs:`, weil ein *skipped* Required-Check in der Branch-Protection teils blockt — der Gate muss verlässlich grün **oder** rot reporten.
- *Alternativen (verworfen):*
  - **Branch-Protection anpassen** (`test` entfernen, `test (3.12)` + `test (3.14)` als required setzen) — GitHub-idiomatisch, aber externe Settings-Abhängigkeit, die bei jeder künftigen Workflow-Änderung (neuer Check-Name) manuell nachgezogen werden muss; verworfen zugunsten des self-contained Workflows.
  - **Matrix zurückbauen auf nur 3.12** — Check hieße wieder `test`, Protection passt sofort, aber der Syntax-Drift-Schutz (der eigentliche Zweck) entfiele; verworfen.
  - **`continue-on-error` für 3.14** (nicht-blockierend) — verworfen: würde den Drift-Schutz entwaffnen (3.14-Fehler blockt nicht → kein echter Schutz, nur Information).
- *Ergebnis/Status:* umgesetzt in **PR #52** (Commit `03d0500` Matrix + `ac39f4c` Aggregator), gemerged nach `main` (`3540998`, 23.06.2026). **Live validiert:** alle 4 Checks grün — `test` (Aggregator) 4 s, `test (3.12)` 17 s, `test (3.14)` 17 s, `claude-review` 1m48s. **3.14 grün = aktuell kein Syntax-Drift** im Codebase (die Matrix hat keinen versteckten Bruch aufgedeckt, schützt aber künftig). PR #51 (enum-guard) parallel gemerged.
- *Bezug:* DTB-11 / DTB-11b; **PR #50** (Basis-CI), **PR #52** (Matrix + Aggregator); `pyproject.toml` (`requires-python>=3.12`, `target-version=py312`); Branch-Protection `required_status_checks.contexts=["test"]`; **E-03** (Git-Workflow/CI-Gate, `main` lauffähig).

## B. Architektur (Backend, G2)

**E-04 — 3-Schichten-Architektur; API/Datenmodell ist die *einzige* Naht und G2-Verantwortung**
- *Begründung:* Eine klar definierte Schnittstelle entkoppelt G1/G2/G3; laut Zeitplan bis Ende Woche 2 final.

**E-05 — Backend-Konzept strikt auf G2 begrenzt**
- *Begründung:* Ein früherer Entwurf konzipierte Sensorik (G1) und Frontend (G3) mit → Scope-Verwässerung. Jede Gruppe verantwortet ihren Teil; wir definieren nur den Vertrag.

**E-06 — Contract-first: API + Datenmodell zuerst einfrieren**
- *Begründung:* Der Vertrag entblockt G1 (Ingest) und G3 (Konsum) gleichzeitig und erlaubt paralleles Arbeiten — **kritischer Pfad**. Wird er spät fertig, blockiert er das Gesamtprojekt.

**E-07 — Ausbaustufen T0–T3; Vertical Slice (T0) zuerst end-to-end**
- *Begründung:* Den durchgehenden Faden (Sensor→Backend→Anzeige) früh beweisen — genau das, woran Studi-Projekte sonst in Woche 3 scheitern.

**E-08 — Technologiestack bewusst OFFEN; T0-Empfehlung FastAPI + SQLite + HTTP** *(Status: DB-Teil am 22.06.2026 extern entschieden → E-29; SQLite-Empfehlung damit überholt)*
- *Begründung:* Projektregel verlangt eine begründete Stack-Wahl statt Vorwegnahme; finale Wahl hängt an der Team-Kompetenz. SQLite/HTTP sind minimal genug für den Prototyp, FastAPI bietet schnelle REST + Validierung.
- *Alternative:* sofortige Festlegung — vertagt (s. Abschnitt G).

**E-29 — Datenhaltung: MySQL durch GL vorgegeben → Umsetzung MySQL/MariaDB durchgängig ab T0 (dev = prod)**
- *Kontext/Task:* P0.1 · E-08 · Vorgabe der Geschäftsleitung (`02-Arbeitsdokumente/Surprise Anforderungen.txt`, 22.06.2026). Die DB-Wahl ist damit **nicht mehr frei**, sondern extern gesetzt (MySQL). *Meine* Architektenentscheidung betrifft die **Umsetzungsvariante**.
- *Entscheidung:* MySQL 8 / MariaDB als **einzige** DB **durchgängig ab T0** (dev = prod via Docker-Compose); Persistenz DB-agnostisch über SQLAlchemy + Repository-Pattern; Alembic-Migrationen.
- *Begründung:* Die Geschäftsleitung gewichtet langfristige Wartbarkeit und zuverlässigen Betrieb höher als die Einführung neuer Technologien und gibt MySQL verbindlich vor; da für die erwartete Last eines Regional-Flughafen-Prototyps (moderate Sensordatenrate) **kein schwerwiegender technischer Gegengrund** gegen MySQL/MariaDB besteht (Analyse §6a), nehme ich die Vorgabe an, statt sie anzufechten. Innerhalb der Vorgabe wähle ich die Variante **„eine DB durchgängig, dev = prod"**: Entwicklung, Tests und Betrieb laufen alle gegen MySQL/MariaDB (lokal via Docker-Compose bereitgestellt). Das vermeidet den **SQL-Dialekt-Drift**, der bei der Alternative „SQLite im Dev, MySQL erst im Betrieb" typischerweise erst spät und teuer auffällt (AUTO_INCREMENT, JSON-Typ, DATETIME-Semantik). Die Umsetzungskosten bleiben gering, weil die Persistenz ohnehin hinter dem **Repository-Pattern** (E-04, §7) gekapselt und über SQLAlchemy DB-agnostisch ist; die sicherheitskritische **Bewertungslogik bleibt eine reine, DB-freie Funktion** und ist vom DB-Wechsel nicht betroffen (kritischer Pfad und ≥ 80 % Coverage unberührt). Den einzigen relevanten Nachteil — die **Docker-/MariaDB-Einstiegshürde** für ein 2.-Semester-Team — nehme ich bewusst in Kauf und mildere ihn durch ein fertiges `docker compose up db` samt Kurzanleitung; der Gewinn an Realitätsnähe (dev = prod, kein Migrationsbruch mitten im 3-Wochen-Projekt) wiegt schwerer.
- *Alternativen (verworfen):*
  - **SQLite durchgängig** — widerspricht der GL-Vorgabe; nicht für Server-/Mehrbenutzerbetrieb gedacht.
  - **SQLite-dev + MySQL-prod (gekapselt)** — pragmatisch, aber Dialekt-Drift-Risiko; weicht von „grundsätzlich MySQL" ab.
  - **PostgreSQL/TimescaleDB** — technisch stark bei Zeitreihen, aber im Haus nicht etabliert (GL-Kriterium „bestehende Kompetenz wiederverwenden").
- *Ergebnis/Status:* vollständig umgesetzt in `Backend-Konzept.md §6/§6a`, `README.md`, `Tasks+Projektplan.md` P0.1 und `Raspberry-Pi-Hosting-Anleitung.md` (22.06.2026, PR #21). G1-Schwellen/reale Last bei Verfügbarkeit gegen §6a plausibilisieren.
- *Bezug:* E-08 (DB-Teil überholt), `Surprise Anforderungen.txt`, NF-01 (Fail-safe bei DB-Ausfall), Backend-Konzept §6a. **Umsetzungs-Teile (Persistenz-Tooling SQLAlchemy/Alembic + Docker-Bereitstellung) am 23.06.2026 revidiert → E-35; DB-Mandat MySQL/MariaDB bleibt.**

**E-35 — Persistenz ohne ORM (rohes PyMySQL + `schema.sql`); kein Docker (native MariaDB) — revidiert die Umsetzung von E-29**
- *Kontext/Task:* Review der Persistenz-/Setup-Tooling-Wahl (23.06.2026) auf der Naht-Task DTB-12 · betrifft DTB-2/12/28 und DTB-53/54/55/56 · revidiert die **Umsetzungs-Teile** von E-29 (Persistenz-Tooling + DB-Bereitstellung). **DB-Mandat MySQL/MariaDB (GL) bleibt unberührt.** *Auslöser:* Team-Kritik auf DTB-12 — SQLAlchemy + Docker zu schwer für ein 3-Wochen-Anfängerteam.
- *Entscheidung:* (1) **Persistenz über rohes PyMySQL** hinter dem Repository-Pattern — **kein SQLAlchemy**; **parametrisierte Queries verpflichtend** (Injection-Schutz). (2) **Schema als handgeschriebenes `schema.sql` (DDL)** statt ORM-Modelle — **kein Alembic**. (3) **Keine Docker-Pflicht:** DB-Bereitstellung über **native MariaDB** (geteilte Pi-Instanz via Tunnel ODER lokale native MariaDB); `docker-compose.yml` entfällt.
- *Begründung:* Für ~6 simple Tabellen in einem 3-Wochen-Prototyp eines ~2.-Semester-Teams ist ein ORM + Migrationsframework Overkill; rohes, **parametrisiertes** SQL + `schema.sql` ist verständlicher und hat weniger bewegliche Teile. Die Docker-Parität (E-29-Ziel „dev = prod") ist **ohne Docker erreichbar**, weil bereits eine **echte native MariaDB auf dem Pi** läuft — die Einstiegshürde Docker fällt damit ersatzlos weg. Es bleibt durchgängig MySQL/MariaDB (kein Dialekt-Drift, E-29-Kern erhalten); nur die Umsetzung ändert sich.
- *Guardrails (nicht verhandelbar):* parametrisierte Queries (nie String-Formatierung), Repository-Pattern bleibt (Bewertungslogik DB-frei → kritischer Pfad/≥80 % Coverage unberührt), MariaDB bleibt (GL), Verbindung config-/`.env`-gesteuert (NF-05/NF-07).
- *Alternativen (verworfen):*
  - **SQLAlchemy ORM** — Overkill + Lernkurve für 3 Wochen.
  - **SQLAlchemy Core** (Kompromiss: Injection-Schutz ohne ORM-Last) — verworfen zugunsten maximaler Einfachheit; Injection-Schutz stattdessen per Disziplin (parametrisierte Queries) + Review.
  - **Docker-Compose-MariaDB** — Einstiegshürde (Windows/WSL2) ohne Mehrwert, da native Pi-MariaDB existiert.
  - **Alembic** — Migrationsframework unnötig bei stabilem `schema.sql` für 6 Tabellen.
- *Konsequenz/offen:* **CI-DB-Bereitstellung** mit DB-Engineer/Johannes klären (MySQL-`service`-Container im Actions-Workflow vs. Coverage-Gate nur auf DB-freien Assessment-Tests). Storage-Integrationstests brauchen eine echte MariaDB (Pi/lokal). Spätere Schema-Änderungen ohne Migrationstool = manuelle `schema.sql`-Pflege (für Prototyp-Scope bewusst akzeptiert).
- *Bezug:* revidiert **E-29** (Umsetzung); DTB-2/12/28; DTB-53/54/55/56; Backend-Konzept §6/§6a/§7; `Stack-Entscheidung-P0.1.md`.

**E-09 — Sensorik-Pragmatik: ein günstiger echter Sensor für die Kerngröße + Simulator-Feed hinter *einer* Ingest-Schnittstelle**
- *Begründung:* Reale Vorfeld-Sensorik ist in 3 Wochen unrealistisch und teuer (Konflikte K3/K4). So läuft die Demo zuverlässig; echte Sensoren ersetzen die Simulation später 1:1.

**E-30 — G1-Ingest-Naht: Push-Modell — G1 sendet an `POST /readings` (G2 hostet den Ingest-Endpoint)** · ⚠️ **REVIDIERT 22.06.2026 nach Seam-Sync mit G1 → abgelöst durch E-31 (Pull).** Eintrag bleibt als nachvollziehbarer Entscheidungsverlauf erhalten.
- *Kontext/Task:* P1.3 (Seam-Sync mit G1) · E-04/E-06 (API/Datenmodell = einzige Naht, G2-Verantwortung, contract-first) · FA Schnittstellen · NF-01 (Fail-safe). **Auslöser:** G1 formulierte „G2 baut die (GET-)Endpoints und stellt bereit, was wir brauchen" — damit war die Richtung der Naht G1→G2 nicht eindeutig.
- *Entscheidung:* Die Sensor→Backend-Naht läuft als **Push**: G1 schickt Messungen per `POST /readings` an einen von **G2 gehosteten** Ingest-Endpoint; G2 validiert am Eingang (Schema, Stale/Defekt) und persistiert. Begriffsklärung: **GET serviert Daten heraus** (an G3: `GET /assessment/current`, `GET /readings`), **POST nimmt Daten herein** (von G1) — beides baut G2, aber es sind zwei verschiedene Richtungen.
- *Begründung:* (1) **Contract-Hoheit am kritischen Punkt:** Wer den Ingest-Endpoint hostet, besitzt Schema- und Validierungshoheit über die Naht — genau die G2-Kernverantwortung (E-04). (2) **Fail-safe natürlich umsetzbar (NF-01):** Trifft eine Messung verspätet/defekt ein oder bleibt sie aus, erkennt G2 das direkt am Eingang und kann „nie GRÜN bei Stale/Ausfall" erzwingen; beim Pull müsste G2 aktiv pollen und „keine Antwort" mehrdeutig von „keine neuen Daten" trennen. (3) **Multi-Sensor-fähig (NF-11):** Mehrere Sensoren/Standorte senden unabhängig an denselben Endpoint, ohne dass G2 jede Quelle einzeln abfragt. (4) **Realistische Topologie:** G1 läuft auf Sensor-/Pi-Hardware, die nach außen senden kann, aber nicht zwingend einen dauerverfügbaren, abfragbaren Dienst bereitstellt — Push verlangt von G1 weniger Infrastruktur. (5) **Passt zum Datenmodell** (`reading`-Payload, Backend-Konzept §9).
- *Alternativen (verworfen):*
  - **Pull / G2 pollt einen GET-Endpoint bei G1** — verworfen: verschiebt Hosting- und Contract-Hoheit zu G1, macht Fail-safe-Erkennung mehrdeutig (Polling-Lücke vs. echter Ausfall), Poll-Intervall ↔ Datenaktualität als zusätzlicher Tradeoff, skaliert schlechter auf mehrere Sensoren.
  - **Wörtliche Auslegung „G2 baut nur GET-Endpoints, über die G1 liefert"** — verworfen: vermengt die zwei Richtungen; ein GET als Dateneingang ist semantisch falsch (GET ist seiteneffektfrei/idempotent, kein Ingest-Kanal).
- *Ergebnis/Status:* **empfohlen** (diese Session, mit Lucas erarbeitet); **mit G1 zu bestätigen** (P1.3) und mit **P1.4** einzufrieren. G2 liefert als Gegenstück einen **Referenz-Sender/Simulator** (E-09), damit Ingest unabhängig von realer G1-Hardware testbar ist.
- *Bezug:* E-04, E-06, E-09; P1.3/P1.4; FA Schnittstellen; NF-01/NF-11; Backend-Konzept §9.

**E-31 — G1-Naht revidiert: Pull-Snapshot statt Push — G1 stellt `GET /current` + `/health` bereit, G2 pollt**
- *Kontext/Task:* P1.3 (Seam-Sync mit G1, durchgeführt 22.06.2026) · **löst E-30 ab** · FA Schnittstellen · NF-01 (Fail-safe). **Auslöser:** Im realen Seam-Sync hat G1 bestätigt, **einen Abfrage-Endpoint bereitzustellen** (Messwerte + Health-Check), statt aktiv zu pushen.
- *Entscheidung:* Die Sensor→Backend-Naht läuft als **Pull**: **G1** stellt **`GET /current`** bereit — **alle aktuellen Messwerte als ein Snapshot mit *einem* gemeinsamen Mess-Zeitstempel (`measured_at`)** — plus **`GET /health`** für die Verfügbarkeit. **G2** baut einen **Poller/HTTP-Client**, der in einem **selbst bestimmten Intervall (≤ 60 s)** abruft, validiert (Bereich, Stale, Defekt) und persistiert. Kein von G2 gehosteter `POST /readings`-Endpoint mehr.
- *Begründung:* (1) **Realität schlägt Empfehlung:** G1 baut faktisch einen Pull-Endpoint — die in E-30 zentrale Annahme „G1-Hardware kann keinen dauerverfügbaren, abfragbaren Dienst bereitstellen" ist damit **widerlegt**; eine einseitig diktierte Push-Naht gegen einen Pull-bauenden Partner wäre nicht umsetzbar. (2) **Einheitliches mentales Modell:** G3 pollt G2, G2 pollt G1 — überall dasselbe Request/Response-Muster statt zweier Richtungen. (3) **Fail-safe bleibt erfüllbar (NF-01):** Der in E-30 befürchtete Mehrdeutigkeits-Nachteil („keine Antwort" vs. „keine neuen Daten") wird sauber aufgelöst, indem **Erreichbarkeit** (`GET /health`/Timeout) von **Datenaktualität** (`measured_at` zu alt → stale) **getrennt** geprüft wird — beide Signale liefert G1. (4) **G2 steuert das Timing** der 30-min-Prognose und der Stale-Grenze selbst, statt von G1s Sende-Takt abzuhängen. (5) **Snapshot statt Einzelwerte** sichert die Kohärenz: T_s, ΔT und RH stammen garantiert aus *einem* Messmoment (ein `measured_at`) — getrennte Einzel-Endpoints würden Werte aus verschiedenen Momenten mischen und die 4-Stufen-Logik verfälschen.
- *Alternativen (verworfen):*
  - **Push (E-30, `POST /readings`)** — durch die G1-Realität überholt; G1 stellt einen Abfrage-Endpoint bereit, hostet keinen Sender.
  - **Pull mit getrennten Einzel-Endpoints je Messgröße** — verworfen: „gleichzeitiger Abruf" garantiert keinen gemeinsamen Mess-Zeitpunkt; die Bewertung würde inkonsistente Snapshots mischen. Stattdessen **ein** Snapshot-Endpoint mit gemeinsamem `measured_at`.
- *Ergebnis/Status:* **entschieden (22.06.2026, mit G1 abgestimmt)**; Contract-Detail (Feldnamen/Einheiten) im Seam-Sync final, mit **P1.4** einzufrieren. **Contract-Hoheit-Tradeoff bewusst:** an der G1-Naht sind wir **Client** (G1 definiert den Endpoint-Shape); Datenmodell und G3-API bleiben in G2-Hoheit.
- *Bezug:* löst **E-30** ab; E-04, E-06; P1.3/P1.4; FA Schnittstellen; NF-01; Backend-Konzept §1/§2/§3/§9; Schwellenwerte §3/§4.

**E-36 — Seam-Sync P1.3 abgeschlossen: Contract (P1.4) eingefroren — Feldfreeze G1→G2, `GET /assessment/current`-Format (G2→G3), NF-02-Finalwerte, AE-03 (Versioning), Geoposition (FA-13)**
- *Kontext/Task:* **DTB-26 (P1.3 Seam-Sync mit G1+G3)** · setzt auf **E-31** (Pull-Naht) auf und **friert deren offene Contract-Details ein (P1.4)** · FA-09/FA-01/FA-03/FA-13 · NF-01/NF-02. **Auslöser:** Abstimmungstermin mit G1- und G3-Lead; die in E-31 als „im Seam-Sync final" markierten Feldnamen/Einheiten + die G3-seitige API mussten festgezurrt werden.
- *Entscheidung:*
  1. **G1 `GET /current` — Feld-Freeze** (G2 ist Client): `sensor_id` (str), `measured_at` (ISO-8601/UTC), `surface_temp_c` (float °C), `air_temp_c` (float °C), `humidity_pct` (float %), `pressure_hpa` (float, optional/Kontext), `status` (`ok`|`fault`). Deckt sich 1:1 mit der bereits implementierten `Reading`-Schema (DTB-12, `src/model/schemas.py`).
  2. **Bewertungsgrößen berechnet G2 selbst** — G1 liefert **keinen** `ice_indicator` und **keinen** Taupunkt/`ΔT`. G2 berechnet `dew_point_c` (Magnus aus `air_temp_c` + `humidity_pct`) und daraus `ΔT = surface_temp_c − dew_point_c`. Die Vereisungsbewertung bleibt vollständig G2-Hoheit (RB-01, kritischer Pfad).
  3. **`GET /assessment/current` (G2→G3) — Response-Format** (in G2-Hoheit; grounded auf `Assessment`-Schema): `risk_level` (`green|yellow|orange|red|unknown`), `driving_factor` (str|null), `explanation` (str|null), `surface_temp_c`, `dew_point_c`, `delta_t`, `humidity_pct`, `measured_at` (G1-Messzeit, UTC), `assessed_at` (G2-Bewertungszeit, UTC), `is_stale` (bool), `sensor_status` (`ok|fault`). `unknown` + `is_stale=true` = Fail-safe-Signal für G3 (NF-01).
  4. **NF-02 Final-Zielwerte:** G2 pollt G1 `GET /current` im **Intervall 30 s**; **Stale-Timeout 120 s** (`measured_at` älter → Daten überaltert → nie GRÜN, `risk_level=unknown`). Erreichbarkeit (`/health`/Timeout) wird **getrennt** von Datenaktualität geprüft (E-31). Werte parametrierbar (`config/`, NF-05).
  5. **AE-03 — API-Versioning = URL-Pfad-Präfix `/v1/`** für alle von G2 bereitgestellten Endpoints (`GET /v1/assessment/current`, `GET /v1/health`, …). Genau **eine** API/ein Endpoint-Satz; `/v1/` ist nur ein Etikett. Ein `/v2/` entsteht **nur falls** je ein Breaking Change nötig wird und läuft dann **neben** `/v1/`, bis G3 umgestellt hat → schützt G3 vor unangekündigtem Bruch.
  6. **Geoposition (FA-13)** kommt **nicht** von den Sensoren (G1 liefert keine Position) → **ein** Standort fix in `config/` (ANR ≈ Coburg, lat/lon). KISS, da Single-Site.
- *Begründung:* Der Feld-Freeze entblockt G1 (Liefervertrag steht) und G3 (Konsumvertrag steht) gleichzeitig — der kritische Pfad für M2. Die Trennung „G1 liefert nur Rohwerte, G2 berechnet Taupunkt + Risiko" hält die sicherheitskritische Logik an einer Stelle (RB-01) und vermeidet doppelte/abweichende Vereisungs-Indikatoren. Das G3-Format spiegelt bewusst die persistierte `Assessment`-Schema plus die für die Fail-safe-Anzeige nötigen Felder (`is_stale`, `sensor_status`), statt G3 zu zwingen, den Stale-Zustand selbst herzuleiten. 30 s/120 s ist für die langsame Wetterdynamik reaktiv genug bei moderater Pi-Last (Stale = 4× Intervall). `/v1/` kostet ein Präfix und ist die billigste Versicherung gegen Breaking-Change-Bruch kurz vor der Demo.
- *Alternativen (verworfen):* **G1 liefert `ice_indicator`** — verworfen, doppelte Bewertungshoheit + Encoding-Streit, widerspricht RB-01. **Header-basiertes Versioning** — für G3 umständlicher zu testen als ein sichtbares Pfad-Präfix. **Kein Versioning (YAGNI)** — verworfen: ein Format-Bruch ohne Pfad-Trennung träfe G3 unangekündigt. **Geoposition pro Snapshot von G1 / separate Stammdaten** — Overkill bei einem einzigen Standort.
- *Ergebnis/Status:* **G2-Seite des Contracts festgelegt (23.06.2026).** **Offen (DoD DTB-26):** schriftliche Bestätigung der Feldnamen/Formate durch **G1-Lead** und **G3-Lead** (E-Mail oder GitHub-Issue mit Label `seam-sync-confirmed`) — erst danach gilt der Contract als beidseitig eingefroren. `humidity_pct` = Luftfeuchte (von G1 zu bestätigen).
- *Bezug:* schließt **DTB-26 (P1.3)** ab, friert **P1.4** ein; baut auf **E-31**; AE-03 (neu, ersetzt offenen AE-Platzhalter); NF-02 (Finalwerte); FA-13; `src/model/schemas.py` (Reading/Assessment); `Umstellung-Pull-3Faktor-Faktenblatt.md`; DTB-19 (OpenAPI), DTB-28 (Persistenz), DTB-38 (Bewertungskern).

**E-37 — Alarm-Auslieferung an G3: Push via SSE (Event), `GET /v1/alarms` nur als Zustands-Resync — kein Poll-Scan**
- *Kontext/Task:* Folgeentscheidung zum Contract (**E-36**, DTB-35) · G2→G3-Naht · FA-Alarmierung · NF-01 (Fail-safe) · RB-01. *Auslöser:* Architektur-Review (Lucas) — Alarme sind globale System-**Events**; sie per Polling „abzuscannen" ist semantisch falsch und verzögert sicherheitskritische Meldungen.
- *Entscheidung:* Alarme werden als **Events gepusht**, nicht gepollt. **`GET /v1/alarms/stream`** als **Server-Sent-Events**-Endpoint: G3 hält **eine** Dauerverbindung, G2 pusht neue Alarme sofort. **`GET /v1/alarms`** bleibt — **nicht** als Entdeckungs-/Poll-Mechanismus, sondern als **Zustands-Abfrage** (aktiv beim Laden + Resync nach Verbindungsabriss). G2 bleibt **Server** (G3 hostet nichts); `ack` reine Audit-Aktion (RB-01).
- *Begründung:* Events gehören gepusht; Polling nach Alarmen ist verschwenderisch und latenzbehaftet. SSE liefert echten Push, ohne dass G3 einen Endpoint hostet (G3 abonniert *unseren* Stream → wir bleiben Server). Für ein **Sicherheitssystem** ist reiner Push allein fragil (Event-Verlust bei Disconnect → übersehener Alarm), daher der **`GET /v1/alarms`-Zustands-Backstop** für Initial-Load und Resync. So sind Sofort-Meldung **und** Robustheit erfüllt.
- *Alternativen (verworfen):* **Reines Polling `GET /alarms`** (bisheriger Doku-Stand) — semantisch falsch für Events, latenzbehaftet. **Echtes Push per Webhook (G2 ruft G3)** — verlangt, dass G3 einen Endpoint hostet, widerspricht „G2 = Server". **WebSocket** — für unidirektionale Alarme Overkill; SSE genügt.
- *Konsequenz/offen:* SSE-Implementierung ist **T2** (FastAPI `StreamingResponse` / `sse-starlette`); `GET /v1/alarms` (Zustand) kann früher stehen. Doku nachgezogen: Backend-Konzept §9.2, README (Datenfluss), Source-README, `API_FROZEN_v1.md`, `Team-Sync-Entscheidungen.md`.
- *Bezug:* ergänzt **E-36**; FA-Alarmierung; NF-01; RB-01; **DTB-19** (OpenAPI muss `/v1/alarms/stream` + `/v1/alarms` führen), DTB-35.

## C. Vereisungs-Entscheidungslogik & Schwellenwerte

**E-10 — Bewertung über Oberflächentemperatur + Taupunkt-Abstand + Feuchte (+ Niederschlag, am 22.06.2026 gestrichen → E-32); Lufttemperatur nur Kontext**
- *Begründung:* **Beide dokumentierten Vorfälle** scheiterten an reiner Lufttemperatur — Fehlalarm bei −2,1 °C (kein Eis) und übersehenes Eis bei +1,2 °C (Oberfläche kälter als Luft). Kernfehler des Altsystems.
- *Status:* **Niederschlag als vierter Faktor am 22.06.2026 entfernt** (Customer braucht ihn nicht → **E-32**). Bewertung läuft seitdem auf **drei** Faktoren (T_s + ΔT + RH); beide Vorfälle bleiben korrekt aufgelöst (liefen nie über Niederschlag).

**E-32 — Niederschlag als Bewertungsfaktor gestrichen (Customer-Scope) → 3-Faktor-Bewertung (T_s + ΔT + RH)**
- *Kontext/Task:* Folge eines **Customer-/Product-Owner-Entscheids** (22.06.2026): Niederschlag(-sart) wird vom Kunden **nicht benötigt** und fällt komplett aus dem Scope. Präzisiert **E-10**. *(Scope-Entscheid des Customers — keine G2-eigene fachliche Wahl; G2 setzt die zwangsläufige Logik-Reduktion um.)*
- *Entscheidung:* Niederschlag entfällt als vierter Bewertungsfaktor **und** als Mess-/Datenmodell-Feld. Die Vereisungsbewertung läuft auf **drei Faktoren: Oberflächentemperatur `T_s` + Taupunkt-Abstand `ΔT` + Feuchte `RH`**. Konkret in `Schwellenwerte.md §2`: **🔴 ROT := `T_s ≤ 0 °C` und `ΔT ≤ 0 °C`** (zuvor zusätzlich „oder gefrierender Niederschlag"); **„Feuchte vorhanden" := `ΔT ≤ 1,0 °C`** (Oberflächennähe zum Taupunkt; der zuvor zusätzlich genannte Luft-`RH ≥ 90 %`-Term ist mit **E-33** entfernt — er reproduzierte Vorfall 1 fälschlich). Datenmodell `reading`: Feld `precip_type` entfernt.
- *Begründung:* Der Kunde verantwortet den Funktionsumfang; ohne Bedarf entfällt der Faktor. Die **Mindestanforderungen bleiben erfüllt**: Beide dokumentierten Vorfälle hingen nie an Niederschlag — Vorfall 1 (−2,1 °C, trocken) → GELB über fehlende Feuchte; Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C, Reif) → ORANGE/ROT über `T_s` + `ΔT ≤ 0`. Die Schwellen selbst (0 °C, 1,0 °C, 90 %) bleiben unberührt; nur die **Struktur** der Regel wird reduziert.
- *Bewusste Konsequenz (ehrlich):* **Aktiver gefrierender Regen bei `T_s` knapp über 0 °C** lässt sich ohne Niederschlagssensor nicht mehr als eigenes Signal erkennen — nur noch indirekt über `T_s`/`ΔT`. Das ist mit dem Wegfall des Faktors bewusst in Kauf genommen (Customer-Entscheid).
- *Alternativen (verworfen):*
  - **Niederschlag behalten** — gegen den Customer-Scope; kein Bedarf, kein Sensor-Feed vorgesehen.
  - **Niederschlag durch einen Proxy ersetzen** (z. B. aus RH/ΔT herleiten) — verworfen: spekulativ, ohne Anforderung; würde Scheingenauigkeit vortäuschen.
- *Ergebnis/Status:* umgesetzt in `Schwellenwerte.md §1–§4` und `Backend-Konzept.md §4/§5/§10` (22.06.2026); Spiegel-Dokumente in Phase B nachzuziehen.
- *Bezug:* präzisiert **E-10**; FA Risikobewertung; `Schwellenwerte.md §2`; `Backend-Konzept.md §4/§5`.

**E-33 — Feuchte-Kriterium an die Oberfläche gebunden (`ΔT`), Luft-RH-Schwelle entfernt — behebt Vorfall-1-Fehlalarm**
- *Kontext/Task:* Review-Befund (22.06.2026) bei der 3-Faktor-Umstellung · FA-01 (Oberflächenfeuchte) · NF-01 · K1 (Fehlalarm-Vermeidung) · betrifft `Schwellenwerte.md §2`.
- *Auslöser:* Die Regel „Feuchte vorhanden" enthielt den Term `RH ≥ 90 %` mit `RH` = **Luft**feuchte (§1). Vorfall 1 (der zu vermeidende Fehlalarm) hat **92 % Luftfeuchte bei trockener Oberfläche** (`Hintergrundgeschichte`; `Usecase-quick` §1). Damit hätte die Logik Vorfall 1 als ORANGE/Fehlalarm klassifiziert — also genau den Fehlalarm reproduziert, den das System vermeiden soll. **Vorbestehender Bug, beim Review aufgedeckt** (nicht durch die Niederschlag-Streichung verursacht).
- *Entscheidung:* Den `RH ≥ 90 %`-Term aus „Feuchte vorhanden" **streichen**. „Feuchte vorhanden" := **`ΔT (T_s − T_d) ≤ 1,0 °C`** — das bindet das Kriterium an die **Oberfläche** (Nähe zum Taupunkt = reale Kondensations-/Reifgefahr). Luftfeuchte `RH` und Lufttemp `T_a` fließen weiter **indirekt** über den Taupunkt `T_d` (Magnus) in `ΔT` ein — nur der direkte Luft-RH-Kurzschluss entfällt. **Keine neue Messgröße nötig** (`ΔT` aus vorhandenen Größen berechnet).
- *Begründung:* FA-01 nennt **Oberflächen**feuchte als Entscheidungsgröße, nicht Luftfeuchte; Vorfall 1 zeigt exakt den Unterschied (feuchte Luft, trockene Oberfläche). `ΔT` ist der physikalisch korrekte, sensorlose Oberflächen-Feuchte-Proxy. Vorfall 1 → `ΔT > 1,0` → keine Feuchte → **GELB** ✓; Vorfall 2 (Reif) → `ΔT ≤ 0` → ROT ✓.
- *Alternativen (verworfen):* **(a)** separater Oberflächenfeuchte-Sensor — unnötig, `ΔT` genügt; zusätzliche Kosten/Sensorabhängigkeit. **(b)** `RH ≥ 90 %` belassen — reproduziert den Fehlalarm, verfehlt das Designziel (K1).
- *Konsequenz für die G1-Naht:* Das `humidity_pct` im `GET /current`-Snapshot ist als **Luft**feuchte ausreichend (Input für `T_d`); ein separater Oberflächenfeuchte-Wert ist **nicht** erforderlich. Im Seam-Sync klarstellen, dass `humidity_pct` = Luftfeuchte.
- *Ergebnis/Status:* umgesetzt in `Schwellenwerte.md §1/§2/§4` (22.06.2026). Schwellen bleiben parametrierbare Dummies (G1-Finalwerte ausstehend, NF-05).
- *Bezug:* FA-01; K1; NF-01; `Schwellenwerte.md §2`; präzisiert E-10/E-11.

**E-34 — Bewertung als priorisierte Kaskade kodieren: Klassifikationslücke geschlossen + ROT-Vorrang explizit + Fail-safe bei fehlendem `ΔT`**
- *Kontext/Task:* Review der 3-Faktor-Logik (22.06.2026, nach E-32/E-33) · betrifft `Schwellenwerte.md §2` · DTB-38 (Implementierung Bewertungskern) · NF-01 (Fail-safe) · K1.
- *Auslöser:* Die vier Stufen waren als **sich gegenseitig ausschließende** Bedingungen formuliert. Das erzeugte zwei Defekte: **(1) Klassifikationslücke** im Bereich `0 °C < T_s ≤ +1,0 °C` **mit** Oberflächenfeuchte (`ΔT ≤ 1,0`) — GRÜN verlangt `T_s > +1,0`, GELB verlangte *keine* Feuchte, ORANGE verlangt `T_s ≤ 0`: ein feuchter Wert wie `T_s = +0,5 °C` traf **keine** Stufe (undefiniert → Fail-safe-Verstoß, hätte je nach Default-Verhalten fälschlich GRÜN werden können). **(2) Überlappung ORANGE/ROT ohne Auswertungsreihenfolge:** jeder ROT-Fall (`ΔT ≤ 0`) erfüllt auch ORANGE (`ΔT ≤ 1,0`) — ohne dokumentierte Priorität ein Implementierungsfehler-Risiko (Anfängerteam, DTB-38).
- *Entscheidung:* §2 als **priorisierte Kaskade** formulieren — Stufen von der gefährlichsten abwärts prüfen, **erste zutreffende gewinnt** (ROT → ORANGE → GELB → GRÜN); **GELB wird Auffang** für „`T_s ≤ +1,0 °C`, aber nicht schon ORANGE/ROT". Zusätzlich Fail-safe-Regel: ist `ΔT` nicht berechenbar (`RH`/`T_a` defekt → `T_d` fehlt), gilt **Feuchte = wahr** (konservativ) ⇒ bei `T_s ≤ 0` mindestens ORANGE, sonst GELB, **nie GRÜN**. Als Pseudocode-Implementierungsvorgabe für DTB-38 hinterlegt.
- *Begründung:* **Keine Schwellenwerte geändert** (`0,0` / `+1,0` / `1,0 °C` unverändert) — nur die **Auswertungsstruktur** repariert. Die Kaskade ist die kanonische Form für hierarchische Alarmstufen (ISA-18.2: höchste zutreffende Stufe gewinnt) und macht „im Zweifel nie GRÜN" (NF-01) strukturell unverletzbar. Beide dokumentierten Vorfälle bleiben identisch aufgelöst (Vorfall 1 → GELB, Vorfall 2 → ORANGE/ROT).
- *Alternativen (verworfen):* **(a)** nur die GELB-Bedingung um die Lücke erweitern, Stufen aber disjunkt lassen — verworfen: flickt einen Sonderfall, die ORANGE/ROT-Überlappung und künftige Lücken blieben. **(b)** bei fehlendem `ΔT` auf GELB statt ORANGE — verworfen: bei `T_s ≤ 0` ist eine kondensierende Oberfläche zu wahrscheinlich; ORANGE ist der sicherere Default (Sicherheits-Bias K1/E-12).
- *Ergebnis/Status:* umgesetzt in `Schwellenwerte.md §2` (22.06.2026). Stufengrenzen bleiben parametrierbare Dummies (G1-Finalwerte ausstehend, NF-05); **am realen Datensatz validieren** — insbesondere die Vorfall-1-Auflösung hängt knapp an `ΔT > 1,0` (Sensortoleranzen `T_s ±0,3 °C`, `RH ±3 %` beachten).
- *Bezug:* präzisiert E-11/E-32/E-33; NF-01; K1; `Schwellenwerte.md §2`; DTB-38.

**E-11 — 4-Stufen-Risikomodell (🟢🟡🟠🔴) mit konkreten Schwellen + Hysterese/Entprellung**
- *Begründung:* Klare, parametrierbare Kategorien statt eines unscharfen Einzelwerts; Hysterese verhindert Alarm-Flattern (ISA-18.2). Beide Vorfälle werden korrekt aufgelöst.

**E-12 — Sicherheits-Bias: verpasste Vereisung (FN) = 0 % Designziel, vor Fehlalarm-Vermeidung (FP < 1 %)**
- *Begründung:* Zielkonflikt K1; Sicherheitsbeauftragte: „Lieber zehn Fehlalarme als ein vereistes Flugzeug". Schwellen daher konservativ.

**E-13 — Oberflächentemp-Genauigkeit ±0,3 °C statt ±0,1 °C**
- *Begründung:* Die Entscheidungsgrenze liegt bei 0 °C; ±0,1 °C ist mit günstiger T0-Sensorik (IR/Kontakt) nicht erreichbar. ±0,3 °C ist ehrlich und ausreichend (K4). Lieber realistisch als unhaltbar.

**E-14 — Alle Schwellen parametrierbar (Config, kein Hardcode)**
- *Begründung:* Der Betriebspunkt (K1) muss am Testdatensatz + den 2 Vorfällen justierbar sein (NF-05); Default sicherheitsbetont.

**E-15 — RB-01 architektonisch erzwungen: System hat keinen Freigabe-/Aktor-Endpoint**
- *Begründung:* Harte Randbedingung — der Mensch ist letzte Instanz. Nicht nur Policy, sondern in der API-Struktur verankert (per Design unmöglich).

## D. Anforderungs-Engineering

**E-16 — ID-Taxonomie FA/NF/RB/AE + Konfliktanalyse K1–K9**
- *Begründung:* Rückverfolgbarkeit (Bewertungskriterium); Zielkonflikte werden explizit gemacht statt versteckt.

**E-17 — Schwellenwerte zweispaltig: Referenzwert (Realbetrieb) ↔ Prototyp-Abnahmekriterium**
- *Begründung:* Industrie-/Normwerte (z. B. Verfügbarkeit, MTBF) sind in 3 Wochen nicht verifizierbar. Ehrliche, prüfbare Prototyp-Kriterien verhindern unhaltbare Versprechen.

**E-18 — Unverifizierte Quellen explizit als ⚠ markiert**
- *Begründung:* Keine erfundene Präzision ins Lastenheft (Belegpflicht); fragwürdige Zitate vor Übernahme prüfen.

## E. Projektorganisation

**E-19 — Rolle Lucas = Systemarchitekt (bewusst nicht Teamlead)**
- *Begründung:* Höchster technischer Hebel (die API/Datenmodell-Naht steuert das ganze System); schützt die individuelle Note (Architektur erzeugt genau die bewertete „Nachvollziehbarkeit"); Skill-Fit; entkoppelt von der People-Management-Lotterie eines 12er-Teams mit hohem Ausfallrisiko.

**E-20 — Kanban: 5 Epics nach Rollen; Spalten = Workflow-Zustände; jede Task mit Owner/DoD/Größe + WIP-Limit**
- *Begründung:* Vorstrukturierte, self-service-fähige Tasks reduzieren Abstimmungslähmung im unerfahrenen Team. Kategorien als Labels, nicht als Spalten (häufige Anfänger-Falle vermieden).

**E-21 — Phasen P0–P6 an M1–M3; Priorisierung Muss = P0–P3 + P5, Soll = P4, Kann = P6**
- *Begründung:* Definiert das benotete Minimum realistisch für 3 Wochen + ~45 % Non-Performer; T3-Erweiterungen sind Bonus, kein Risiko.

**E-22 — Non-Performer-Entkopplung: kritischen Pfad eng besetzen, abgegrenzte Tasks verteilen**
- *Begründung:* Contract (P1) und Kernlogik (P2.4) auf die verlässlichsten Köpfe; parallelisierbare Tasks an den Rest — ein Ausfall darf nie die Naht blockieren.

## F. KI-Einsatz im Team

**E-23 — KI-Onboarding-Dokument für ChatGPT/Gemini (`Agents-gpt-gemini.md`)**
- *Begründung:* Fremd-KIs erfinden sonst Schwellenwerte, konzipieren alle Gruppen mit oder antworten auf Englisch. Das Briefing setzt: Projektdokumente = Ground Truth, keine Halluzinationen, Scope- und Sprachdisziplin.

**E-24 — Einheitliches Agenten-Tool: Claude Code (Harness) für alle Rollen**
- *Entscheidung:* Ein Tool für Dev- und Reviewer-Rollen — Claude Code; gemeinsame `.claude/`-Config (Skills/Hooks) ins Repo committen.
- *Begründung:* Das kuratierte ECC-Toolkit (Skills/Hooks/Agents) ist Claude-Code-nativ; „Standards per Hook erzwingen" ist hier am reifsten. Ein Stack = zentral pflegbar, `git pull` = alle identisch.
- *Alternative:* Codex CLI / Kimi Code als Harness — verworfen: würden das gesamte Toolkit entwerten (Neubau nötig).
- *Bezug:* Toolkit-Detail-Log `Devteam-vibecodes/Entscheidungslog-Toolkit.md`.

**E-25 — Fuel über Abo statt API; Claude Pro = Standard; Modellstrategie Sonnet 4.6 / Opus 4.8 / Haiku 4.5**
- *Entscheidung:* Bezahlung ausschließlich via Abo (Pro Standard, Max optional). Default-Modell **Sonnet 4.6**; **Opus 4.8** für harte Aufgaben; **Haiku 4.5** für leichte Review-/Testarbeit.
- *Begründung:* API „lohnt nie mehr als Abos". Qualität schützt ~2.-Sem.-Anfänger (Opus 4.8 88,6 % SWE-bench Verified vs. GPT-5.5 82,6 %; Kimi bricht auf harten Tasks ein) — relevant für die 40 %-Einzelnote. Sonnet ~1 Punkt hinter Opus bei Bruchteil der Kosten → idealer Default.
- *Hinweis:* Claude Fable 5 (Bestmodell) seit 12.06.2026 per US-Exportkontrolle weltweit ausgesetzt (Direktive zielte auf *foreign nationals* = dieses Team) → nicht einplanen.
- *Alternative:* Kimi (~€17, größtes Kontingent) / Codex / Gemini als Standard — verworfen (Qualität, Kohärenz, Provider).

**E-26 — Einheitliche Arbeitsumgebung: VS Code + integriertes Terminal + Claude Code**
- *Begründung:* Für ~2.-Sem.-Niveau: vertrauter Editor + git-GUI + volle CLI-Power in *einer* Umgebung. Reine CLI ist abschreckend, Desktop-App schlecht repo-/terminal-integriert. Eine Umgebung dokumentieren/supporten.

**E-27 — Sanktionierte Fallback-Ökosysteme + Hook-Portabilität (Hedge)**
- *Entscheidung:* Kein Parallelstandard, aber zwei Ausnahmen: (a) vorhandenes ChatGPT-Plus → Codex CLI erlaubt; (b) Shared-Kimi-Allegretto (2× Reserve) als Null-Kosten-Netz für die Testerinnen. Hooks als standalone `.claude/hooks/`-Skripte.
- *Begründung:* „Niemanden zum Zahlen zwingen" — Fallbacks decken Nicht-Zahler ohne Mehrkosten. Standalone-Hooks portieren auf Codex (Config-Übersetzung) → Entscheidung reversibel.
- *Alternative:* strikt ein Tool ohne Ausnahmen — verworfen wegen Zahlungs-Freiwilligkeit; Gemini als Fallback — verworfen (schwächstes Coding, 4. Ökosystem).

---

## H. Tooling-Fixes ( nachvollziehbar für Wiederholung)

**E-28 — Atlassian MCP Server: korrekter Endpoint `…/v1/mcp/authv2` + `mcp-remote@latest`, Auth-Cache bei Account-Wechsel löschen**
- *Entscheidung:* Kimi spricht den Atlassian-MCP-Server nicht direkt als HTTP-Entry an, sondern über den Node.js-Proxy `mcp-remote@latest` mit der URL `https://mcp.atlassian.com/v1/mcp/authv2`.
- *Begründung:* Der ältere `/v1/mcp`-Endpoint ohne `/authv2` und ohne `@latest` führte zu „Internal Server Error" bzw. sofortigem `Connection closed` nach dem OAuth-Redirect. Die offizielle Atlassian-Doku für lokale Clients (Juni 2026) verlangt `/v1/mcp/authv2`.
- *Lösung:*
  1. `C:/Users/luceb/.kimi-code/mcp.json`:
     ```json
     "atlassian": {
       "command": "npx",
       "args": ["-y", "mcp-remote@latest", "https://mcp.atlassian.com/v1/mcp/authv2"]
     }
     ```
  2. Kimi neu starten → Browser öffnet OAuth-Einwilligung.
  3. Falls falscher Account/Zugriff nur auf „Steinzisterne": Kimi beenden, `~/.mcp-auth/mcp-remote-0.1.37/*` löschen, Kimi neu starten und im Browser den **richtigen Atlassian-Account** wählen.
- *Alternative:* direkter HTTP-Entry mit Kimi-internem OAuth — verworfen, lieferte bei diesem Setup reproduzierbar Fehler; API-Token-Auth — nur falls Admin es explizit freigibt.
- *Bezug:* Offizielle Doku https://github.com/atlassian/atlassian-mcp-server / Atlassian Support „Setting up IDEs".

## G. Offene Entscheidungen (bewusst vertagt)

| Offen | Bezug | Warum vertagt |
|---|---|---|
| Konkreter Stack (Sprache/Framework/Protokoll) | E-08, AE | hängt an Team-Kompetenz; T0-Empfehlung steht, finale Wahl folgt. **DB-Teil entschieden → E-29 (MySQL, GL-Vorgabe).** |
| Lokal vs. Cloud + Fernzugriff | AE-01/AE-02 | Quelle unentschieden; im Logbuch zu begründen |
| Eisindikator: Proxy vs. echter Sensor vs. Simulation | K3/K4 | Budget- und Messgüte-abhängig |
| Anbindung an das HS-gestellte zentrale Remote | E-01 | sobald die Hochschule es bereitstellt |
| Backend-Code-Root: `04-Source-code/` flach vs. `04-Source-code/source/` (Unterordner) | E-01, P0.2 | P0-Grundgerüst liegt in `04-Source-code/`, DB-Engineer legt `.env`/Datenmodell in `04-Source-code/source/` → **einen** Root festlegen vor dem P0-Push (sonst Doppelstruktur) |
| DB-Bereitstellung im Dev: Docker-Compose-MariaDB vs. native Pi-MariaDB | E-29 | E-29 wählte „dev = prod via Docker"; DB-Engineer richtete real eine **native** Pi-MariaDB (11.8) ein → vor Storage-Impl klären, ob Dev lokal Docker nutzt und der Pi die Prod-Instanz ist |

> **Pflege:** Bei jeder neuen Festlegung einen `E-xx`-Eintrag ergänzen; offene Punkte aus G nach Entscheidung
> nach oben überführen. So bleibt der rote Faden „Warum haben wir das so gebaut?" jederzeit nachvollziehbar.

---

## P. Projektplanung & Jira-Backlog (Session 2026-06-21)

> Diese **EP-Einträge** dokumentieren in dieser Session getroffene **Prozess-/Architektur-Entscheidungen**
> (KI-gestützt strukturiert, belegbasiert). Die **benotete persönliche Entscheidungsreflexion (40 %)
> formuliert der Mensch selbst** — siehe Jira-Tasks **DTB-40** (Individualreflexion je Person) und **DTB-45**
> (Zuordnung). Quelle/Begleitdokument: `02-Arbeitsdokumente/Projektplan-Jira-Backlog-G2.md`.

**EP-01 — Projektplan + Jira-Backlog (DTB) strukturiert angelegt (9 Epics, 43 Tasks)**
- *Entscheidung:* Phasen P0–P6, KPIs, Risiken und ein vollständiges Backlog (Epics E-01..E-09 → DTB-1..DTB-52) mit DoD je Task im Jira-Projekt DTB erstellt.
- *Begründung:* Mit nur einem echten Backend-Dev + Anfängerteam schafft ein abgegrenztes Backlog mit klaren DoD/Owner-Empfehlungen Steuerbarkeit und prüfbare Anforderungsabdeckung; Contract-first + Vertical-Slice-Reihenfolge sichert M2.
- *Alternative:* Tasks ad hoc/manuell pflegen — verworfen: keine prüfbare Abdeckung, Drift-Gefahr.
- *Bezug:* alle FA/NF/RB; `Tasks+Projektplan.md`; DTB-1..DTB-52.

**EP-02 — Owner als Empfehlung (kein harter Assignee), skill-bewusste Verteilung**
- *Entscheidung:* Owner-Vorschlag steht in der Task-Beschreibung. Lucas = kritischer Pfad; Petzold = Stories 2. Ordnung; Hartling/Ganter = kleine, unabhängige Endpoints; Arash/Andreas = Zuarbeit unter Anleitung (nie Story-Owner); Mohammadi/Berger = Test; Reisi/Ilchyshyn = Doku.
- *Begründung:* Reale Skill-Lage (nur ein echter Backend-Dev); harte Assignees wären verfrüht, das Backlog bleibt umverteilbar.
- *Alternative:* feste Assignees / Roster gleichverteilt — verworfen: überschätzt Team-Kompetenz, Fehlzuteilungsrisiko.
- *Bezug:* Owner-Realität (Vorgabe Session 2026-06-21).

**EP-03 — T0-Stack für den Task-Zuschnitt als gesetzt behandelt**
- *Entscheidung:* FastAPI + SQLite + HTTP-POST als Arbeitsannahme; formale Begründung in E-08 nachziehen (Task DTB-2 / P0.1).
- *Begründung:* `.venv` enthält FastAPI/SQLite/pytest seit 17.06 → faktisch gewählt; der „offen"-Status (E-08) widerspricht der installierten Umgebung.
- *Alternative:* Stack weiter offen halten — verworfen: blockiert den Bau; Korrektur durch CTO jederzeit möglich.
- *Bezug:* E-08; DTB-2.

**EP-04 — Korrekturen aus adversarialer Verifikation eingearbeitet**
- *Entscheidung:* Config als M1-Enabler vorgezogen (zirkuläre Abhängigkeit P4.3↔P2.4 aufgelöst → nur P2.4 hängt an Config); FA-06-Prognose von Stretch → M3/Muss (vereinfachte 3-Punkt-lineare Regression); P5.4 in Gruppen- + Individualreflexion gesplittet; Vorfall-2-Testfall auf ROT präzisiert.
- *Begründung:* Der Verifikations-Pass deckte echte Logik-/Abdeckungsfehler auf; FA-06 ist MUSS (nicht Stretch); die 40%-Einzelleistung erfordert Personen-Zuweisung.
- *Alternative:* Rohsynthese 1:1 übernehmen — verworfen: enthielt zirkuläre Abhängigkeit + MUSS-Lücke.
- *Bezug:* DTB-33, DTB-36, DTB-40, DTB-45; Epic E-09 (DTB-3).

**EP-05 — Abhängigkeiten als „Blocks"-Links in Jira abgebildet**
- *Entscheidung:* 43 dependsOn-Kanten als Jira-„Blocks"-Verknüpfungen angelegt; die zirkuläre Kante entfernt.
- *Begründung:* Kritischen Pfad und Reihenfolge tool-seitig sichtbar und steuerbar machen (über die Textangabe hinaus).
- *Alternative:* nur Textangabe in der Beschreibung — ergänzend belassen, Links zusätzlich.
- *Bezug:* Sequencing-Abschnitt im Projektplan-Dokument.

**EP-06 — Residuale Lücken offen dokumentiert (nicht stillschweigend gefüllt)**
- *Entscheidung:* Systemkontext-Diagramm (Pflicht-Deliverable W1), NF-07-Auth für `POST /config` und die Config-Redundanz (E-05/E-07/E-09) als offene Punkte markiert, nicht automatisch „gefixt".
- *Begründung:* Source-of-Truth + Team-Entscheidung; keine erfundenen Anforderungen, keine stillschweigende Lückenfüllung (claude-sync §2).
- *Bezug:* Review-Befund Session 2026-06-21.
