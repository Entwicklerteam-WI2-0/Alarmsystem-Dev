# API Contract — FROZEN v1 (DTB-35 / P1.4)

> **Status:** ✅ **EINGEFROREN (v1.0)** — beide Nähte beidseitig bestätigt (`team-sync-confirmed`, DTB-26);
> `openapi.yaml` (DTB-19) liegt vor und ist gegen diese Datei geprüft. Wire-Form (Pfade/Felder/Typen) ist ab
> hier **stabil**; grundlegende Änderungen laufen über `/v2/`, nie über ein Brechen von `/v1/`.
> **Version:** v1.0 · **Eingefroren am:** 2026-06-24 · **Stand:** 2026-06-24 · **Owner:** Lucas Vöhringer (Systemarchitekt, G2)
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
  | `surface_moisture_pct` | number (%) | nein | Kalibrierte Oberflächenfeuchte (Kontext, Contract v1.1) — nur Speicher/Anzeige, **nicht** in der Bewertung |
  | `wind_speed_ms` | number (m/s) | nein | Windgeschwindigkeit (Kontext, Contract v1.1) — nur Speicher/Anzeige, **nicht** in der Bewertung |
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

### Alarme — Push via SSE, kein Poll-Scan (E-37)
- **`GET /v1/alarms/stream`** (Server-Sent Events): G3 hält **eine** Verbindung, G2 **pusht** Alarme live.
- **`GET /v1/alarms`**: Zustands-Abfrage aktiver Alarme (Initial-Load + Resync nach Disconnect —
  Sicherheits-Backstop, **kein** Entdeckungs-Poll).
- **`POST /v1/alarms/{id}/ack`**: Quittierung — reine UI-/Audit-Aktion, **kein** Bahn-Aktor (RB-01).

### Weitere Endpoints (reserviert, T1/T2)
`GET /v1/readings` (Historie). Verbindliche Form folgt mit `openapi.yaml` (DTB-19).

### Post-Freeze-Erweiterungen (nach v1.0-Freeze ergänzt — `openapi.yaml` maßgeblich)
> **Nicht Teil des 2026-06-24-Freeze.** Additive G2→G3-Erweiterungen, die den eingefrorenen
> Wire-Kern (oben) nicht ändern. Maßgeblich ist `docs/api/v1/openapi.yaml`.

- **`GET /v1/thresholds`** (DTB-62, NF-05): rein lesende Ausgabe der aktiven Vereisungs-Schwellen
  für das G3-Schwellenwert-Menü (RB-01-neutral, kein Aktor).
  - **DTB-33 (FA-06)** erweitert den `prognose`-Block **additiv** um `trend_window_min`, `horizon_min`,
    `min_points`, `max_readings_limit` (E-41). `t_s_grenz_c`/`trend_window_min`/`horizon_min` =
    G3-Kalibrierwerte; `min_points`/`max_readings_limit` = **interne** Tuning-/DB-Last-Knöpfe
    (kein Kalibrierwert fürs G3-Menü). Non-breaking — G3 ignoriert unbekannte Felder.

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
- [x] `docs/api/v1/openapi.yaml` vorhanden (**DTB-19**, Luca Ganter) — valide OpenAPI 3.0.3, gegen diese Datei geprüft (kein Drift)
- [x] Schriftliche Bestätigung G1-Lead + G3-Lead (`team-sync-confirmed`, **DTB-26**) — siehe Bestätigungs-Block unten
- [ ] Git-Tag **`api-v1.0`** + „P1.4"-Commit auf `main` — **letzter mechanischer Schritt, ausstehend (Freigabe Lucas)**
- [x] Vertrag an G1/G3 versandt (`Anfrage-G1`/`Anfrage-G3`) — Sign-off beidseitig erhalten (2026-06-23)

---

## Bestätigungen (`team-sync-confirmed`) — beidseitig eingefroren

Beide Nähte sind von der jeweiligen Gegenseite bestätigt. Die Einträge wurden **im Namen der bestätigenden
Leads durch den Systemarchitekten erfasst** (G1/G3 haben zugesagt); die ursprünglichen Sign-off-Vermerke
stehen in `02-Arbeitsdokumente/Anfrage-G1.md` / `Anfrage-G3.md` (Sign-off-Datum 2026-06-23).

| Naht | Gegenseite | Bestätigt durch | Datum | Kanal |
|---|---|---|---|---|
| **G1 → G2** (Sensordaten) | G1 (Sensorik & Daten) | Nils (G1-Lead) | 2026-06-23 | Zusage an G2-Architekt, hier dokumentiert |
| **G2 → G3** (API) | G3 (Frontend & Integration) | G3-Lead | 2026-06-23 | Zusage an G2-Architekt, hier dokumentiert |

Eingetragen/dokumentiert durch: **L. Vöhringer** (Systemarchitekt G2), 2026-06-24.

> **Nachvollziehbarkeit:** Für einen harten Audit-Trail kann die jeweilige Original-Bestätigung
> (Antwort-Mail bzw. GitHub-Issue mit Label `team-sync-confirmed`) nachgereicht und hier verlinkt werden.
> G3-Lead: **Nick**; G1-Lead: **Nils** (eingetragen 2026-06-25).

**Damit gilt der G1↔G2↔G3-Contract als beidseitig eingefroren (P1.4).** Entblockt: DTB-19, DTB-28, DTB-38.
