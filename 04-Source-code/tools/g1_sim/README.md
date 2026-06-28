# G1-Sensor-Simulator (Test-Tool)

Steuerbarer Dummy-G1-Server für live-nahe Tests **ohne echte Sensor-Hardware**.
Bedient exakt den von G2 konsumierten G1-Contract (`docs/api/v1/g1-consumed.openapi.yaml`).

> **Nicht Teil des Produktiv-Builds.** Liegt unter `tools/`, wird von `src/` nicht importiert
> und nicht mit ausgeliefert. Reines Entwickler-/Test-Werkzeug.

## Was er bedient

| Endpoint | Antwort |
|---|---|
| `GET /health` | `200 {"status":"ok"}` — oder `503`, wenn `health_down: true` (G1-Ausfall) |
| `GET /current` | Snapshot: `sensor_id`, `measured_at` (ISO-UTC, `…Z`), Pflicht-Trias `surface_temp_c`/`air_temp_c`/`humidity_pct`, optional `pressure_hpa`, `status` (`ok`\|`fault`) |

`measured_at` wird bei jedem Request auf "jetzt" gesetzt (minus `age_s`), damit der Poll nicht
fälschlich als Stale verworfen wird.

## Starten

```bash
# aus 04-Source-code/
python tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
# (ohne --state laeuft er mit dem eingebauten Gruen-Default)
```

G2 dagegen laufen lassen (eigene Shell, gegen eure installierte MariaDB):

```bash
DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=alarmsystem DB_USER=alarm DB_PASSWORD=<dev-pw> \
G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true G2_API_KEY=dev-secret \
  uvicorn src.main:app --port 8000
```

Prüfen: `curl http://127.0.0.1:8000/v1/assessment/current`

## Szenario live umschalten

State-Datei (`g1_state.json`, Vorlage: `g1_state.example.json`) bearbeiten — der Sim liest sie bei
**jedem** Request neu, kein Neustart nötig. Felder:

| Feld | Typ | Wirkung |
|---|---|---|
| `surface_temp_c`/`air_temp_c`/`humidity_pct` | float | Messwerte (treiben die Ampel) |
| `pressure_hpa` | float\|null | Kontext (optional) |
| `status` | `ok`\|`fault` | `fault` → G2 verwirft Reading → `unknown` |
| `age_s` | int ≥ 0 | Sekunden, die `measured_at` zurückdatiert wird (Stale-Test). Negativ würde `measured_at` in die Zukunft setzen — nicht verwenden. |
| `health_down` | bool | `true` → `/health` 503 → G2 pollt nicht → `unknown` |

Erwartete G2-Reaktion (gegen aktuelle `config/thresholds.json`):

| Szenario | Beispiel-State | erwartete Ampel |
|---|---|---|
| GRÜN | `surface_temp_c:15, air_temp_c:16, humidity_pct:40` | `green` |
| ROT (Vereisung) | `surface_temp_c:-2, air_temp_c:-1, humidity_pct:98` | `red` + CRITICAL-Alarm |
| STALE | `age_s:300` | `unknown` (nie grün) |
| FAULT | `status:"fault"` | `unknown` (nie grün) |
| G1-DOWN | `health_down:true` | `unknown` (nie grün) |

> **Sprung-Guard beachten:** G2 verwirft Readings mit > 5 °C/min Sprung als Sensordefekt. Für einen
> sauberen GRÜN↔ROT-Wechsel G2 jeweils frisch starten (oder die Temperatur in kleinen Schritten ändern).

## MariaDB-Hinweise (für euer lokales Setup)

Vollständig in `docs/dev-db-setup.md`. Zwei Stolpersteine:
- `grants.sql` vergibt an `'alarm'@'localhost'` — bei TCP (`127.0.0.1`) `'alarm'@'%'` nötig, sonst `ERROR 1142`.
- Auf MariaDB 11.4.x werfen die REVOKE-Zeilen ein `1064` — mit `--force` einspielen, die GRANTs sitzen korrekt.
