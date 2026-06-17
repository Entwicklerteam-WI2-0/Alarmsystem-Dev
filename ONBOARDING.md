# Onboarding — In 3 Schritten startklar (G2)

> Ziel: vom blanken Rechner zur fertig konfigurierten Agenten-Umgebung — **ohne** manuelles Gefummel.
> Funktioniert auf **macOS** und **Windows**.

## Schritt 1 — Claude Code installieren (einmalig)
Folge der offiziellen Anleitung für die Claude-Code-CLI. Test: `claude --version` zeigt eine Version.

## Schritt 2 — Repo klonen
```bash
git clone <REPO-URL-von-Lucas>
cd Alarmsystem-Dev
```

## Schritt 3 — Setup ausführen
**macOS:**
```bash
bash setup.sh
```
**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```
Das Skript installiert `uv` (falls nötig), baut die Python-Umgebung und legt deine lokale `CLAUDE.md` an.

## Danach — arbeiten
1. Ordner in **VS Code** öffnen.
2. Im integrierten Terminal **`claude`** starten.
3. Beim ersten Mal **„Projekt vertrauen"** bestätigen.
4. **`/start`** tippen → Kontext, aktueller Stand und Regeln werden geladen.

Die Skills, Befehle und Standard-Checks kommen **automatisch aus dem Repo** — du musst nichts einzeln einrichten.

---

### Wenn etwas klemmt
- **`uv: command not found`** → neues Terminal öffnen (PATH neu laden) und Setup erneut starten.
- **`claude` kennt `/start` nicht** → du bist im falschen Ordner; ins geklonte `Alarmsystem-Dev` wechseln.
- **Sonst:** Lucas fragen — nicht raten.
