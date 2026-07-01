# Fact-Forcing-Gate deaktiviert (2026-06-30)

> Persönliche Config-Notiz von Lucas — kein Team-OS-Pflichtdokument.

## Was wurde gemacht

Das Fact-Forcing-Gate (Hook `uni:pre:bash:fact-force`, Team-OS G2 §6.2) ist in der
Kimi-Code-Config **deaktiviert** worden, indem die entsprechenden `[[hooks]]`-Einträge
aus `~/.kimi-code/config.toml` entfernt wurden.

- **Config-Datei:** `C:/Users/LucasVöhringer/.kimi-code/config.toml`
- **Entfernt:** 4 `[[hooks]]`-Blöcke, die auf
  `node "C:/Users/LucasVöhringer/.kimi-code/hooks/fact-forcing-gate.js"` zeigten
  (jeweils 2× `PreToolUse` Matcher `Bash`, 2× Matcher `Edit|Write|MultiEdit`).
- **Backup:** `~/.kimi-code/config.toml.<Zeitstempel>.bak` (z. B.
  `config.toml.20260630-XXXXXX.bak`) — liegt neben der Config.
- **Übrig geblieben:** die 5 anderen Hooks (AGENTS-Loader, mneme Session-/Compact-Hooks).
- `kimi doctor config` war grün (exit 0).

## So reaktiviert man das Gate wieder

**Option A — sauber über das Team-OS (empfohlen):**
Setup/Update aus `devteam-vibecodes` erneut laufen lassen. Das trägt die Hooks
automatisch wieder in die Config ein (Quelle: `~/.kimi-code/AGENTS.md` §6.2).

**Option B — händisch in `~/.kimi-code/config.toml` anhängen:**
```toml
[[hooks]]
event = "PreToolUse"
matcher = "Bash"
command = "node \"C:/Users/LucasVöhringer/.kimi-code/hooks/fact-forcing-gate.js\""
timeout = 5

[[hooks]]
event = "PreToolUse"
matcher = "Edit|Write|MultiEdit"
command = "node \"C:/Users/LucasVöhringer/.kimi-code/hooks/fact-forcing-gate.js\""
timeout = 5
```
Danach `/reload` im TUI (Idle). Mit `kimi doctor config` prüfen.

## Temporär (ohne Config-Änderung)

Das Gate lässt sich auch pro Session abschalten, ohne die Config zu verändern:
- `UNI_GATE_OFF=off` setzen, oder
- `UNI_DISABLED_HOOKS=uni:pre:bash:fact-force` setzen.
