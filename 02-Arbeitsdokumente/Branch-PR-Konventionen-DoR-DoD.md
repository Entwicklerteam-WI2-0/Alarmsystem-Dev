# Branch/PR-Konventionen + Definition of Ready/Done

> **Ticket:** DTB-52 · **Phase:** P0.4 · **Scope:** Backend-Gruppe G2 (`Alarmsystem-Dev`)  
> **Zweck:** Einheitlicher Git-Workflow, klare Qualitätsgates und ein gemeinsames Verständnis davon, wann eine Task *startbereit* (DoR) und wann *fertig* (DoD) ist.  
> **Geltungsbereich:** Alle Code-Arbeiten im Backend-Repo (`04-Source-code/`). Ausnahme `erinnerung/` siehe §7.  
> **Sprache:** Deutsch (wie alle Projektartefakte).  
> **Stand:** 2026-06-23

---

## 1. Git-Branching-Modell

Wir arbeiten mit einem einfachen, aber strengen **Feature-Branch-Workflow**:

```text
main (geschützt, immer lauffähig)
  ↑
  └── feat/<ticket>-<kurzbeschreibung>
  └── fix/<ticket>-<kurzbeschreibung>
  └── docs/<ticket>-<kurzbeschreibung>
  └── test/<ticket>-<kurzbeschreibung>
```

- **`main` ist geschützt.** Kein direkter Push auf `main`.
- Jede Änderung läuft über einen **Feature-Branch** und einen **Pull Request**.
- Der Branch wird nach erfolgreichem Review in `main` gemergt.
- **`main` bleibt immer lauffähig** — ein roter `main` ist ein Blocker für alle.

### 1.1 Branch-Namen

| Präfix | Verwendung | Beispiel |
|---|---|---|
| `feat/` | Neue Features | `feat/dtb-19-openapi-v1` |
| `fix/` | Bugfixes / Fail-safe-Korrekturen | `fix/ingest-poller-failsafe-optional` |
| `docs/` | Reine Dokumentation | `docs/dtb-35-contract-freeze` |
| `test/` | Tests, Guards, CI-Erweiterungen | `test/dtb-19-enum-sync-guard` |
| `ci/` | CI/CD-Workflows | `ci/python-matrix` |
| `refactor/` | Interne Umstrukturierung ohne Verhaltensänderung | `refactor/dtb-38-assessment-kaskade` |

**Regeln:**
- Kleinbuchstaben, Bindestriche statt Unterstriche.
- Ticket-ID immer mitführen (`dtb-XX`).
- Kurz und sprechend (max. 4–5 Wörter).

### 1.2 Commit-Konventionen

Jede Commit-Message beginnt mit einem Typ-Präfix:

| Präfix | Verwendung |
|---|---|
| `feat:` | Neues Feature |
| `fix:` | Bugfix oder Fail-safe-Korrektur |
| `docs:` | Dokumentation (auch README, OpenAPI) |
| `test:` | Tests hinzufügen/erweitern |
| `refactor:` | Code umstrukturieren, Verhalten gleich |
| `chore:` | Wartung, Tooling, Abhängigkeiten |
| `ci:` | CI/CD-Workflows |

**Beispiele:**

```text
feat(config): thresholds.json + validierender Loader (DTB-15)
fix(ingest): pressure_hpa Fail-safe + Validierungs-Tests (DTB-12)
docs(api): OpenAPI v1 Spec gegen eingefrorenen Contract (DTB-19)
test(api): Guard gegen Enum-Drift Spec<->Modell (DTB-19)
ci: Python-Matrix (3.12 + 3.14) fuer Test-Workflow (DTB-11b)
```

- Ticket-ID und Anforderungs-ID (z. B. `FA-01`, `NF-01`, `RB-01`) mitführen.
- commits sinnvoll gestückelt — ein Commit = eine in sich geschlossene Einheit.

---

## 2. Workflow Schritt-für-Schritt

### 2.1 Vor der Arbeit: Definition of Ready prüfen

Siehe §4. Ist die Task nicht ready, wird sie nicht begonnen.

### 2.2 Branch anlegen

```bash
git checkout main
git pull origin main
git checkout -b feat/dtb-XX-kurzbeschreibung
```

> **Nie auf `main` arbeiten.**

### 2.3 TDD: RED → GREEN → REFACTOR

Besonders bei der **Vereisungsbewertungslogik** (kritischer Pfad):

1. **RED:** Test für das gewünschte Verhalten schreiben und ausführen — er muss rot sein.
2. **GREEN:** Minimaler Code, damit der Test grün wird.
3. **REFACTOR:** Aufräumen, ohne Tests rot werden zu lassen.

Beispiel-Testfälle (müssen benannt und grün sein):

- `test_vorfall_1_kalt_trocken_ohne_fehlalarm()` → GELB
- `test_vorfall_2_eis_bei_positiver_lufttemperatur()` → ROT
- `test_fail_safe_stale_daten_nie_gruen()` → `unknown` / GELB

> **Belegpflicht:** Schwellenwerte stammen ausschließlich aus `Schwellenwerte.md` — nichts dazuerfinden.

### 2.4 Quality-Gate vor jedem Commit

Unmittelbar vor jedem Commit (WP4):

1. **Formatter:**
   ```bash
   uv run ruff format .
   ```
2. **Linter (mit Auto-Fix):**
   ```bash
   uv run ruff check --fix .
   ```
   Verbleibende Warnungen erklären und beheben.
3. **Keine Secrets im Diff** prüfen (API-Keys, Tokens, Passwörter).
4. **Conventions prüfen:**
   - Datei < 800 Zeilen.
   - Funktion < 50 Zeilen.
   - Keine tiefe Verschachtelung (> 4).
   - Keine Magic Numbers — benannte Konstanten.
   - Explizites Error-Handling.
5. **Build/Import sauber:**
   ```bash
   uv run python -c "import src"
   ```

Erst wenn alles grün ist, committen.

### 2.5 Push & Pull Request

1. **Selbst-Review** des eigenen Diffs durchführen.
2. **Tests & Coverage** prüfen:
   ```bash
   uv run pytest -q
   uv run pytest --cov=src/assessment --cov-report=term-missing
   ```
3. Branch pushen:
   ```bash
   git push -u origin feat/dtb-XX-kurzbeschreibung
   ```
4. PR mit Beschreibung + Test-Plan erstellen.

> **Push, PR und Merge nur nach expliziter Freigabe durch Lucas.**

### 2.6 PR-Review

Jeder PR wird von der **Reviewer/Test-Abteilung** (Arezo / Amelie) oder einem Architekten geprüft.

**Geprüft wird:**

- DoD vollständig?
- Tests grün (`uv run pytest -q`)
- Coverage Bewertungslogik ≥ 80 %
- Beide Vorfälle + Fail-safe als benannte grüne Tests vorhanden
- Anforderungs-ID referenziert
- Entscheidung im Entscheidungslogbuch (falls zutreffend)
- Code-Review (`python-review`, `fastapi-review`)
- Sicherheits-Review: keine Secrets, keine Aktor-Endpoints (RB-01), Fail-safe greift
- Kritischer Pfad: `verification-loop` ggf. `santa-loop`

**Freigabe nur**, wenn keine offenen CRITICAL-/HIGH-Befunde bestehen.

---

## 3. Definition of Ready (DoR)

Eine Task gilt als *startbereit*, wenn alle folgenden Kriterien erfüllt sind:

| # | Kriterium | Erklärung |
|---|---|---|
| R1 | Ticket klar verstanden | Scope, Ziel und Abgrenzung sind bekannt. |
| R2 | Abhängigkeiten aufgelöst | Vorgänger-Tasks sind erledigt oder zumindest deren Interface bekannt. |
| R3 | Anforderungs-ID zugeordnet | Mindestens eine FA/NF/RB/AE aus `Usecase-quick.md` referenziert. |
| R4 | Technische Vorgaben bekannt | Datenmodell/API-Contract eingesehen (Backend-Konzept §9), falls relevant. |
| R5 | Schwellenwerte geklärt | Falls Bewertungslogik: Schwellenwerte aus `Schwellenwerte.md` bekannt (Dummies sind OK, aber markiert). |
| R6 | Aufwand geschätzt | S/M/L Schätzung vorhanden. |
| R7 | Owner / DRI klar | Eine Person ist verantwortlich. |

---

## 4. Definition of Done (DoD)

Eine Task gilt erst als *fertig*, wenn alle folgenden Kriterien erfüllt sind:

| # | Kriterium | Nachweis |
|---|---|---|
| D1 | Code im PR | Feature-Branch gegen `main` erstellt. |
| D2 | Review bestanden | Mindestens ein Approval durch Reviewer/Architekt. |
| D3 | In `main` gemergt | Merge ist erfolgt; `main` bleibt lauffähig. |
| D4 | Tests grün | `uv run pytest -q` erfolgreich. |
| D5 | Coverage ≥ 80 % | `uv run pytest --cov=src/assessment --cov-report=term-missing` zeigt ≥ 80 % für `assessment/`. |
| D6 | Kritische Testfälle vorhanden | Benannte Tests für Vorfall 1, Vorfall 2 und Fail-safe sind grün. |
| D7 | Anforderungs-ID referenziert | FA/NF/RB/AE in Commit-Message oder PR-Body genannt. |
| D8 | Schwellenwerte nicht hardcodiert | Schwellen kommen aus `config/`; keine Magic Numbers im Code. |
| D9 | RB-01 eingehalten | Kein Freigabe-/Sperr-/Aktor-Endpoint; ggf. Pre-Commit-Hook grün. |
| D10 | Entscheidung dokumentiert | Falls technische/architektonische Entscheidung getroffen: Eintrag im Entscheidungslogbuch. |
| D11 | Doku aktualisiert | README, API-Doku, OpenAPI, Testprotokoll etc. nachgezogen, falls relevant. |

---

## 5. Pull-Request-Template

Jeder PR muss folgende Struktur im Body haben:

```markdown
## Zusammenfassung
Kurze Beschreibung der Änderung.

## Ticket / Anforderung
- Jira: DTB-XX
- Anf-ID: FA-XX / NF-XX / RB-XX / AE-XX

## Geänderte Module
- [ ] ingest
- [ ] model
- [ ] assessment
- [ ] storage
- [ ] api
- [ ] config
- [ ] forecast
- [ ] docs
- [ ] ci

## Testplan
- [ ] `uv run pytest -q` lokal grün
- [ ] `uv run pytest --cov=src/assessment` ≥ 80 %
- [ ] Vorfall 1 / Vorfall 2 / Fail-safe als benannte Tests geprüft
- [ ] `uv run ruff format .` + `uv run ruff check --fix .` grün
- [ ] Keine Secrets im Diff

## Sicherheit
- [ ] Kein Aktor-/Freigabe-/Sperr-Endpoint (RB-01)
- [ ] Fail-safe-Verhalten geprüft

## Entscheidungslogbuch
- [ ] Nicht zutreffend
- [ ] Eintrag in `Entscheidungslog-[Name]/` hinzugefügt (E-XX)

## Offene Punkte / Hinweise für Reviewer
...
```

> **Ziel:** PR-Template in `.github/pull_request_template.md` hinterlegen.

---

## 6. RB-01- & Fail-safe-Checks

### 6.1 Keine automatische Freigabe (RB-01)

Das System gibt die Startbahn **nie** automatisch frei oder gesperrt. Im Code bedeutet das:

- Keine Endpoints wie `POST /runway/unlock`, `POST /runway/lock`, `POST /execute` etc.
- `POST /v1/alarms/{id}/ack` ist eine reine UI-/Audit-Aktion, kein Aktor.
- Pre-Commit-Hook prüft auf verdächtige Strings (`unlock`, `freigabe`, `sperr`, `execute`) in `src/api/`.

### 6.2 Fail-safe (NF-01)

Bei Ausfall, Stale-Daten oder Defekt **nie GRÜN**:

- Stale > 120 s → `unknown` oder GELB + Warnung.
- Sensor-Defekt → GELB/unknown + Warnung.
- DB-Fehler → GELB/unknown + Warnung.

Jeder PR am kritischen Pfad muss mindestens einen benannten Fail-safe-Test enthalten.

---

## 7. Ausnahme: `erinnerung/`

Dateien unter `erinnerung/` sind **kein Code** und dienen dem geteilten Team-Fortschritt.

- Branch → PR → Merge bleibt Pflicht (`main` ist geschützt).
- Kein inhaltlicher Review nötig — kleiner PR, Self-/Auto-Merge ohne Review.
- Schreibweise append-only, um Konflikte zu vermeiden.

---

## 8. Genehmigungspflichten

| Aktion | Genehmigung erforderlich |
|---|---|
| Branch anlegen | Nein |
| Committen auf Feature-Branch | Nein |
| Branch pushen | **Ja — Lucas** |
| PR erstellen | **Ja — Lucas** |
| PR mergen | **Ja — Lucas** |
| Force-Push | **Ja — Lucas** (nur wenn unbedingt nötig) |
| Destruktive Git-Aktionen (`reset --hard`, `branch -D` auf geteilten Branches) | **Ja — Lucas** |

---

## 9. Beispiele für Branch-Namen

| Branch | Typ |
|---|---|
| `feat/dtb-19-openapi-v1` | Feature |
| `fix/ingest-poller-failsafe-optional` | Fix |
| `feat/p1.1-datenmodell` | Feature |
| `test/dtb-19-enum-sync-guard` | Test |
| `ci/python-matrix` | CI |

> Aktuelle Branch- und PR-Status siehe GitHub (`github.com/Entwicklerteam-WI2-0/Alarmsystem-Dev`) bzw. Jira (Projekt DTB).

---

## 10. Verwandte Dokumente & Skills

- `Backend-Konzept.md` §7 (Code-Struktur), §9 (API-Vertrag)
- `Usecase-quick.md` (FA/NF/RB/AE)
- `Schwellenwerte.md` §2 (Bewertungslogik), §3 (Abnahme-Checkliste)
- `Projektplan-Jira-Backlog-G2.md` (Task-Details, P0.4)
- `Stack-Entscheidung-P0.1.md` (Stack E-35)
- Skills: `git-workflow`, `quality-gate`, `tdd-workflow`, `pr`, `review-pr`, `verification-loop`, `code-tour`

---

## 11. Offene Punkte / nächste Schritte

- [ ] PR-Template als `.github/pull_request_template.md` physisch anlegen.
- [ ] Pre-Commit-Hook für RB-01-Strings + No-Hardcode-Rule einrichten (siehe Projektplan-Jira-Backlog-G2.md, P0.5/P0.6).
- [ ] `.github/workflows/test.yml` aktivieren + Branch-Protection-Rule „Require status checks" (DTB-11).
- [ ] Dieses Dokument nach Einführung der CI-Hooks aktualisieren.
