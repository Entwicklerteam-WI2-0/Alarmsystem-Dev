# Archiv: Env-/Gitignore-Vorlagen aus dem entfernten `04-Source-code/source/`

> **Stand:** 2026-06-22 · **Zweck:** Sicherung, bevor der versehentliche Ordner
> `04-Source-code/source/` aus dem Backend entfernt wurde. Der Ordner stammte aus
> PR #26 („add pi and maria db setup") und enthielt eine **abweichende**, NF-07-bewusste
> Vorlage neben der kanonischen Code-Root (`04-Source-code/.env.example` / `.gitignore`).
> Hier gesichert, damit die Inhalte nicht verloren gehen.

## ⚠️ Offener Punkt: DB-Naming inkonsistent (Team klären)

Die Code-Root-Vorlage (`04-Source-code/.env.example`, aus PR #27) nutzt generische
Namen, die `source/`-Vorlage projektpassende:

| Feld | Code-Root (#27, aktiv) | `source/` (#26, hier archiviert) |
|---|---|---|
| `DB_NAME` | `alarmsystem` | `vereisung` |
| `DB_USER` | `alarm` | `anr_app` |
| `DB_HOST` | `localhost` | `127.0.0.1` |

→ **Vor dem Scaffolding-Abschluss festlegen**, welches DB-Naming gilt, und es mit
`04-Source-code/docker-compose.yml` konsistent machen.

## Gesicherte Vorlage `.env.example` (NF-07)

```dotenv
# ── DB-Zugang (Vorlage) — NF-07 ───────────────────────────────
# Kopiere diese Datei zu `.env` und trage die echten Werte ein.
# Die echte `.env` ist gitignored und gehört NUR auf den Pi, nie ins Git.
#
#   cp .env.example .env   &&   $EDITOR .env
#
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=vereisung
DB_USER=anr_app
DB_PASSWORD=hier-echtes-passwort-einsetzen
```

## Gesicherte Vorlage `.gitignore` (Secrets-scoped)

```gitignore
# ── Secrets / Config (NF-07) — scoped auf den Code-Ordner ─────
# Reale DB-Zugangsdaten NIE committen. Vorlage = .env.example (Platzhalter).
.env
*.env
!.env.example
```
