# ONBOARDING — 3-Schritt-Schnellstart (G2 Backend)

> Schneller Einstieg in das Backend-Repo der Gruppe 2 (Vereisungserkennung ANR).
> Vollständige Details: `README.md` (Root) und `04-Source-code/README.md`.

## 1. Kontext lesen (Pflicht, in dieser Reihenfolge)
1. `erinnerung/stand.md` — aktueller Gesamtstand + offene Punkte.
2. `erinnerung/task-prioritaet-nach-audit-2026-06-26.md` — Task-Priorität/Reihenfolge nach Tiefenaudit.
3. `02-Arbeitsdokumente/Backend-Konzept.md` (Architektur, §9 = G1→G2-Contract) ·
   `Schwellenwerte.md` (4-Stufen-Logik) · `Usecase-quick.md` (FA/NF/RB).
4. `04-Source-code/docs/API_FROZEN_v1.md` — eingefrorener API-Vertrag v1.0 (einhalten, nicht „verbessern").

## 2. Umgebung aufsetzen
```bash
cd 04-Source-code
py -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
# MariaDB: native — Pi via SSH-Tunnel ODER lokale Installation (kein Docker -> E-35);
# Zugang via .env (Vorlage: .env.example), nie committen.
uvicorn src.main:app --reload                # -> http://127.0.0.1:8000
```

## 3. Entwickeln nach Workflow
- Tests zuerst (TDD), dann Implementierung; `pytest --cov=src` (Bewertungslogik >= 80 %).
- Feature-Branch -> PR -> Review -> Merge. `main` ist geschützt, bleibt lauffähig.
- Schwellen NIE hardcoden — ausschließlich über `config/` (NF-05); G1-Finalwerte ersetzen die Dummies.
- Stack (gesetzt, E-29/E-35): Python 3.12+ · FastAPI · Pydantic · **MySQL/MariaDB** über rohes PyMySQL (kein ORM/Alembic/Docker).

**Fragen?** Architektur -> Lucas V. · Status -> Standup.
