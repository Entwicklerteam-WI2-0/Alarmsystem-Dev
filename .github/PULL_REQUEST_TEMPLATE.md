<!-- DTB-22: Dieses Template fuellt jede neue PR-Beschreibung vor. -->

## Was & warum
<!-- Kurz: Was aendert dieser PR und warum? -->


## Bezug
- Jira-Ticket: DTB-
- Anforderungs-ID(s): <!-- z. B. FA-03, NF-01, RB-01 -->

## ⚠️ Schwellenwerte
> **Bitte keine Hard-codierten Schwellen verwenden — Schwellenwerte immer über `config/` laden.**
> Vereisungs-/Prognose-Schwellen kommen aus `config/thresholds.json` (via `src/config/loader.py`),
> nie als Literal im Code. Die finalen G1-Messwerte stehen noch aus und müssen ohne Code-Änderung
> austauschbar bleiben. Der Guard `tools/check_hardcoded_thresholds.py` (CI: *lint-config*) prüft das.
>
> **Grenzen des Guards (selbst mitprüfen):**
> - Er scannt nur `SCAN_DIRS` (`src/assessment`, `src/forecast`, `src/ingest`). Legst du Schwellen-Vergleiche in
>   ein **neues** Modul (z. B. `src/ingest`, `src/api`), musst du `SCAN_DIRS` dort ergänzen — sonst
>   bleibt das Gate still grün.
> - Indirekte Vergleiche erkennt er nur als `operator.gt(...)`/`math.isclose(...)`; **Alias-/bare-Import**
>   (`import operator as op` → `op.gt(...)`, `from operator import gt`) wird **nicht** erfasst.
> - Begründete Ausnahme via `# noqa: hardcoded-threshold`: bei **mehrzeiligem** Vergleich gehört der
>   Marker auf die **Vergleichszeile selbst** (Zeile des linken Operanden, z. B. `    t_s > 1.0  # noqa…`),
>   **nicht** auf die öffnende `if (`-Zeile — sonst meldet der Guard trotz Marker einen Verstoß.

## RB-01
> **Kein Aktor:** Dieser PR darf keinen Endpoint enthalten, der die Startbahn freigibt, sperrt,
> entsperrt oder ausfuehrt/steuert. Der Guard `tools/check_rb01_no_actor_endpoints.py`
> prueft FastAPI-Routen und `docs/api/v1/openapi.yaml` auf `unlock`, `freigabe`, `sperr`,
> `execute` (CI: *lint-config*). Review trotzdem bewusst machen: `ack` ist nur UI-/Audit-
> Quittierung, kein Runway-Status.

## Checkliste (DoD)
- [ ] Tests grün (`pytest`) und Coverage gehalten (Bewertungslogik ≥ 80 %)
- [ ] `ruff check .` sauber
- [ ] **Keine hartcodierten Schwellen** — Werte aus `config/` geladen (CI *lint-config* grün)
- [ ] **RB-01 bestätigt:** keine Freigabe-/Sperr-/Aktor-Endpoints (CI *lint-config* grün)
- [ ] Anforderungs-ID (FA/NF/RB) oben referenziert
- [ ] Getroffene Entscheidung(en) im Entscheidungslogbuch festgehalten
- [ ] `main` bleibt nach Merge lauffähig

## Testnachweis
<!-- Kurzer Beleg: Befehl + Ergebnis (z. B. "62 passed", Coverage-Wert). -->
