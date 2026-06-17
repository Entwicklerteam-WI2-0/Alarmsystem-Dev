# Aktueller Stand

> Stand: 2026-06-17 · Pflege: Lucas. Beim Sitzungsstart von `/start` gelesen.

## Woran wir gerade arbeiten
- **Team-OS / Onboarding** (Branch `feat/agenten-onboarding`): Bootstrap-Schicht angelegt
  (`setup.sh`/`setup.ps1`, `pyproject.toml`, `claude-sync.md`, `.claude/`, `ONBOARDING.md`).
- Entschieden: **Claude Code + Claude Pro** als Standard (Detail: Entscheidungslog **E-24…E-27**).

## Als Nächstes
1. Bootstrap testen (klonen → `setup` → `claude` → `/start`) und Branch via PR mergen.
2. Phase 2: die Workflow-Skills (Repo-Arbeit, Convention-Kontrolle, Entwickler-Aufsicht) + Enforcement-Hooks bauen.
3. Backend: **Contract-first** (API + Datenmodell als Naht, P1) einfrieren — kritischer Pfad.

## Offene Punkte / Blocker
- Dev 2: ChatGPT **Go** oder **Plus**? (entscheidet Codex-Fallback vs. Claude Pro)
- Tracked `CLAUDE.md`/`AGENTS.md` noch per `git rm --cached` aus der Versionierung nehmen (E-03 jetzt in `.gitignore`).
- Stack final bestätigen (T0-Empfehlung: FastAPI + SQLite + HTTP).
