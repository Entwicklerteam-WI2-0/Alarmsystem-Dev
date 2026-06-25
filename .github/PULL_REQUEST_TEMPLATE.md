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

## Checkliste (DoD)
- [ ] Tests grün (`pytest`) und Coverage gehalten (Bewertungslogik ≥ 80 %)
- [ ] `ruff check .` sauber
- [ ] **Keine hartcodierten Schwellen** — Werte aus `config/` geladen (CI *lint-config* grün)
- [ ] Anforderungs-ID (FA/NF/RB) oben referenziert
- [ ] Getroffene Entscheidung(en) im Entscheidungslogbuch festgehalten
- [ ] `main` bleibt nach Merge lauffähig

## Testnachweis
<!-- Kurzer Beleg: Befehl + Ergebnis (z. B. "62 passed", Coverage-Wert). -->
