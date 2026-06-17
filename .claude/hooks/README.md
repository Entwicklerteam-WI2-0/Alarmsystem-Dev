# .claude/hooks — Standards als Hooks (erzwungen, nicht erhofft)

Standalone-Skripte, die von `.claude/settings.json` referenziert werden. **Standalone**, damit sie
portabel bleiben (z. B. nach Codex mit reiner Config-Übersetzung). Pflegt: Lucas (Systemarchitekt).

## Geplante Pflicht-Hooks (Phase 2 — noch zu bauen)
| Hook | Typ | Zweck |
|---|---|---|
| `rb01-guard` | PreToolUse (Write/Edit) | blockt Routen mit `release\|freigabe\|sperr\|aktor\|control` → **RB-01** automatisch |
| `secret-scan` | PreToolUse / PreCommit | verhindert Secrets an der Quelle |
| `size-guard` | PreToolUse (Write) | Dateigröße < 800 Z., Funktion < 50 Z. |
| `german-check` | PostToolUse | Artefakte auf Deutsch |
| `format-lint` | PostToolUse (Write/Edit) | `uv run ruff format` + `uv run ruff check --fix` |
| `openapi-diff` | Stop / CI | meldet Änderungen am eingefrorenen Contract |
| `test-gate` | Stop | `uv run pytest` muss grün sein |

> Stand jetzt: nur ein harmloser **SessionStart-Hinweis** in `settings.json` aktiv. Die obigen
> Enforcement-Hooks werden erst verdrahtet, **nachdem** die uv-Umgebung bei allen steht (sonst
> laufen sie ins Leere). Ergänzend serverseitig: GitHub **Branch Protection** (PR-Pflicht, kein `main`-Push).
