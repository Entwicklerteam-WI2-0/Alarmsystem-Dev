# API Contract — FROZEN v1 (DTB-35 / P1.4)

> **Status:** ENTWURF — wird zu **EINGEFROREN**, sobald (1) G1- und G3-Lead schriftlich bestätigt haben
> (`seam-sync-confirmed`, DTB-26) **und** (2) die `openapi.yaml` (DTB-19) vorliegt. Erst dann Git-Tag `api-v1.0`.
> **Version:** v1 · **Stand:** 2026-06-23 · **Owner:** Lucas Vöhringer (Systemarchitekt, G2)
> **Quellen:** `02-Arbeitsdokumente/Team-Sync-Entscheidungen.md` (Begründung), Entscheidungslog **E-36**/**E-31**,
> `src/model/schemas.py` (Reading/Assessment). Bei Konflikt gewinnt diese Datei + `openapi.yaml` (DTB-19).

Dieser Vertrag ist die **einzige früh einzufrierende Naht** (G2-Verantwortung). Er entblockt G1 (Lieferung)
und G3 (Konsum) gleichzeitig (kritischer Pfad, M2).

---

## 1. Versionierung (AE-03)

- Alle von G2 bereitgestellten Endpoints liegen unter dem Pfad-Präfix **`/v1/`**
  (`GET /v1/assessment/current`, `GET /v1/health`, …). Genau **eine** API.
- Ein `/v2/` entsteht **nur**, falls je ein Breaking Change nötig wird, und läuft **neben** `/v1/`,
  bis G3 umgestellt hat. `/v1/` bricht dadurch nie unangekündigt.

## 2. Konsumierte Naht: G1 → G2 (Pull, E-31)

G2 ist hier **Client**. G1 stellt bereit, G2 pollt.

- **`GET /current`** — alle aktuellen Messwerte als **ein** Snapshot mit **einem** gemeinsamen
  Mess-Zeitstempel. **`GET /health`** — Verfügbarkeit (`200` ok / `503` fault).
- **Snapshot-Felder (Feld-Freeze, = `Reading`-Schema, DTB-12):**

  | Feld | Typ | Pflicht | Bedeutung |
  |---|---|:--:|---|
  | `sensor_id` | string | ja | Sensor-Kennung (z. B. `anr-rwy-01`) |
  | `measured_at` | string (ISO-8601, UTC) | ja | Mess-Zeitstempel, gemeinsam für alle Werte |
  | `surface_temp_c` | number (°C) | ja | Oberflächentemperatur `T_s` |
  | `air_temp_c` | number (°C) | ja | Lufttemperatur `T_a` (Kontext + Taupunkt-Berechnung) |
  | `humidity_pct` | number (%) | ja | **Luftfeuchte** (von G1 zu bestätigen) |
  | `pressure_hpa` | number (hPa) | nein | Luftdruck (Kontext) |
  | `status` | enum `ok` \| `fault` | ja | Sensor-/Lieferstatus |

- **G1 liefert NICHT:** keinen `ice_indicator`, keinen Taupunkt, kein `ΔT`. G2 berechnet `dew_point_c`
  (Magnus aus `air_temp_c` + `humidity_pct`) und `ΔT = surface_temp_c − dew_point_c` selbst. Die
  Vereisungsbewertung bleibt vollständig G2-Hoheit (**RB-01**, kritischer Pfad).

## 3. Bereitgestellte Naht: G2 → G3

### `GET /v1/assessment/current` — aktuelle Bewertung (Response 200)

```json
{
  "risk_level": "yellow",        // green | yellow | orange | red | unknown
  "driving_factor": "dew_point",
  "explanation": "ΔT ≤ 1,0 °C an der Oberfläche → Feuchte",
  "surface_temp_c": -0.4,
  "dew_point_c": -1.1,           // von G2 berechnet
  "delta_t": 0.7,                // T_s - T_d
  "humidity_pct": 96,
  "measured_at": "2026-06-22T14:03:05Z",   // G1-Messzeit (UTC)
  "assessed_at": "2026-06-22T14:03:30Z",   // G2-Bewertungszeit (UTC)
  "is_stale": false,             // true + risk_level=unknown = Fail-safe griff
  "sensor_status": "ok"          // ok | fault
}
```

- G3 erhält **Ampel + Roh-Messwerte** in einem Response.
- **`GET /v1/health`** — Verfügbarkeit von G2.
- **Fehler/Sonderfälle:** `400` bei ungültiger Anfrage; bei überalterten/fehlenden Daten **kein Fehler**,
  sondern `risk_level=unknown` + `is_stale=true` (Fail-safe, NF-01). (Detail-Codes in `openapi.yaml`, DTB-19.)

### Spätere Endpoints (Platz im Vertrag reserviert, T1/T2)
`GET /v1/alarms`, `GET /v1/readings`, `POST /v1/alarms/{id}/ack`. **`ack` ist reine UI-/Audit-Aktion,
kein Bahn-Freigabe-Aktor** (RB-01). Verbindliche Form folgt mit `openapi.yaml`.

## 4. Messintervall + Stale (NF-02, final)

- **Poll-Intervall:** 30 s. **Stale-Timeout:** 120 s (`measured_at` älter → `risk_level=unknown`, nie GRÜN).
- Erreichbarkeit (`/health`/Timeout) wird **getrennt** von Datenaktualität geprüft.
- Werte **parametrierbar** in `config/` (NF-05) — nicht hardcoden.

## 5. Geoposition (FA-13)

- Sensoren liefern keine Position → **ein** Standort fix in `config/` (ANR ≈ Coburg, lat/lon).

## 6. Sicherheits-Randbedingung (RB-01)

- Reine **Entscheidungsunterstützung**: kein Freigabe-/Sperr-/Aktor-Endpoint, auch nicht „temporär".
  Gilt für G2 **und** die G3-UI (kein automatisch schaltender Knopf).

---

## Freeze-Checkliste (DoD DTB-35)

- [x] Contract-Summary dokumentiert (diese Datei): G1 `GET /current`, `GET /v1/assessment/current`, Intervall, Versionierung
- [ ] `docs/api/v1/openapi.yaml` vorhanden (**DTB-19**, Luca Ganter)
- [ ] Schriftliche Bestätigung G1-Lead + G3-Lead (`seam-sync-confirmed`, **DTB-26**)
- [ ] Git-Tag **`api-v1.0`** + „P1.4"-Commit auf `main`
- [ ] E-Mail an G1/G3 mit Link zu `openapi.yaml` (Vorlagen: `Anfrage-G1.txt`/`Anfrage-G3.txt` auf dem Desktop)
