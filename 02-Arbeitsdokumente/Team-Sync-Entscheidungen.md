# Team-Sync-Entscheidungen — API/Datenmodell-Naht (DTB-26 / P1.3 → P1.4)

> **Zweck:** Ergebnis-Dokument des Team-Syncs. Hält die **getroffenen Entscheidungen** zur Naht
> G1 → G2 → G3 fest (die Antworten, nicht mehr die Fragen). Friert die G2-Seite des Contracts ein (**P1.4**).
> **Stand:** 2026-06-23 · **Bezug:** DTB-26 (P1.3), Entscheidungslog **E-36** (baut auf **E-31** Pull-Naht),
> `src/model/schemas.py` (Reading/Assessment), `Umstellung-Pull-3Faktor-Faktenblatt.md`.
> **Status:** **Contract beidseitig eingefroren (P1.4, 2026-06-23)** — G1- und G3-Lead haben den Vertrag bestätigt. Entblockt DTB-19, DTB-28, DTB-38.

---

## 1. Naht G1 → G2 (Pull, E-31)

G2 ist an dieser Naht **Client**: G2 pollt G1, G1 liefert nur Rohwerte.

- **G1 stellt bereit:** `GET /current` (ein Snapshot, ein gemeinsamer Mess-Zeitstempel) + `GET /health`.
- **G1 `GET /current` — Feld-Freeze** (deckt sich 1:1 mit der `Reading`-Schema, DTB-12):

  | Feld | Typ | Bedeutung |
  |---|---|---|
  | `sensor_id` | str | Sensor-Kennung (z. B. `anr-rwy-01`) |
  | `measured_at` | ISO-8601 / UTC | Mess-Zeitstempel (Pflicht, für alle Werte gemeinsam) |
  | `surface_temp_c` | float °C | Oberflächentemperatur `T_s` |
  | `air_temp_c` | float °C | Lufttemperatur `T_a` (Kontext) |
  | `humidity_pct` | float % | **Luftfeuchte** (von G1 zu bestätigen) |
  | `pressure_hpa` | float | Luftdruck (optional/Kontext) |
  | `status` | `ok` \| `fault` | Sensor-/Lieferstatus |

- **G2 berechnet selbst** — **G1 liefert KEINEN `ice_indicator` und KEINEN Taupunkt/`ΔT`.**
  G2 rechnet `dew_point_c` (Magnus aus `air_temp_c` + `humidity_pct`), daraus `ΔT = surface_temp_c − dew_point_c`.
  Die Vereisungsbewertung bleibt vollständig G2-Hoheit (RB-01, kritischer Pfad).

## 2. Naht G2 → G3 (API)

- **Versioning (AE-03):** alle G2-Endpoints unter Pfad-Präfix **`/v1/`** (eine API, ein Endpoint-Satz).
  `/v2/` entsteht nur, falls je ein Breaking Change nötig wird, und läuft dann neben `/v1/` weiter.
- **`GET /v1/assessment/current` — Response (G2-Hoheit, grounded auf `Assessment`-Schema):**

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
  "is_stale": false,             // true + unknown = Fail-safe griff
  "sensor_status": "ok"
}
```

  → G3 bekommt die **Ampel + die Roh-Messwerte** im selben Response (deckt Frage 1 ab).
- **Alarme = Push, kein Poll (E-37):** `GET /v1/alarms/stream` (SSE — G2 pusht Alarm-Events live) +
  `GET /v1/alarms` (Zustands-Abfrage/Resync, Sicherheits-Backstop). `POST /v1/alarms/{id}/ack` = reine Audit-Aktion (RB-01).

### Offene G3-Punkte (warten auf G3-Antwort, aus Luca Ganters Fragenkatalog DTB-26)

| # | Punkt | G2-Stand / Angebot |
|---|---|---|
| 1 | Ampel oder auch Messwerte | **Beides** wird mitgeliefert (s. oben) |
| 2 | Voller Datenabruf vs. nur Alarm+Prognose | v1 liefert mind. `GET /v1/assessment/current`; weitere Abruf-Endpoints je nach G3-Bedarf |
| 3 | **RB-01 — kein Auto-Freigabe-Knopf** | **Hart:** UI darf Alarm quittieren (Protokoll), aber **keine** automatische Bahn-Freigabe/-Sperre. **Schriftlich von G3 zu bestätigen.** |
| 4 | 30-min-Prognose: Ampel oder Werte | Platz im Vertrag reserviert; Entscheidung folgt (Feature später) |
| 5 | Schwellenwert-Menü | Lesen offen; **Ändern** später per Auth abgesichert (NF-07) |

## 3. Messintervall + Stale (NF-02, Final-Zielwerte)

- **Poll-Intervall:** G2 ruft G1 `GET /current` alle **30 s** ab.
- **Stale-Timeout:** **120 s** — ist `measured_at` älter, gelten die Daten als überaltert →
  `risk_level = unknown`, **nie GRÜN** (Fail-safe, NF-01). Erreichbarkeit (`/health`/Timeout) wird
  **getrennt** von Datenaktualität geprüft.
- Werte **parametrierbar** in `config/` (NF-05), nicht hardcoden.

## 4. Geoposition (FA-13)

- Sensoren liefern **keine** Position → **ein** Standort fix in `config/` (ANR ≈ Coburg, lat/lon).

## 5. Sicherheits-Randbedingung (RB-01)

- Das System ist reine **Entscheidungsunterstützung**: **kein** Freigabe-/Sperr-/Aktor-Endpoint,
  auch nicht „temporär". Gilt für G2 **und** für die G3-UI (kein automatisch schaltender Knopf).

---

## Erledigt — Sign-off 2026-06-23 (DoD DTB-26 erfüllt)

1. ✅ **G1-Lead** hat Feldnamen/Typen `GET /current`, `humidity_pct` = Luftfeuchte sowie Poll 30 s / Stale 120 s bestätigt.
2. ✅ **G3-Lead** hat Punkte 1–4 + **RB-01** (kein Auto-Freigabe-Knopf) bestätigt.
3. ✅ Bestätigung beidseitig erteilt (2026-06-23).
4. ✅ Contract **beidseitig eingefroren (P1.4)** → entblockt DTB-19 (OpenAPI), DTB-28 (Persistenz), DTB-38 (Bewertungskern).

> Die Versand-Vorlagen liegen jetzt im Repo: `02-Arbeitsdokumente/Anfrage-G1.md`, `02-Arbeitsdokumente/Anfrage-G3.md`.

---

## Post-Freeze-Team-Sync — Nachträge nach dem v1.0-Freeze (Stand 2026-06-27)

> Additive G2→G3-Erweiterungen NACH dem 2026-06-24-Freeze. Sie brechen den eingefrorenen Wire-Kern
> (oben) NICHT (`info.version` bleibt `1.0.0`). Maßgeblich: `04-Source-code/docs/api/v1/openapi.yaml`.

### 6. `GET /v1/thresholds` (DTB-62) — neuer lesender G2→G3-Endpoint
- Liefert die aktiven Vereisungs-Schwellen für das G3-Schwellenwert-Menü (rein lesend, RB-01-neutral).
- **⚠️ Offen: G3-Sign-off fehlt.** Dieser Endpoint kam NACH dem Freeze dazu und hat noch kein
  `team-sync-confirmed` von G3 (Nick).

### 7. DTB-33 (FA-06) — 30-min-Prognose erweitert `/v1/thresholds.prognose` (additiv, E-41)
- Neue Felder: `trend_window_min`, `horizon_min` (G3-Kalibrierwerte) + `min_points`, `max_readings_limit`
  (interne Tuning-/DB-Last-Knöpfe, NICHT fürs G3-Menü). Non-breaking — G3 ignoriert unbekannte Felder.
- G3 informiert + um Sign-off gebeten (Desktop-Nachricht 2026-06-27). **Offen: G3-Bestätigung.**

### 8. Alarm-Endpoints — Contract vollständig, Laufzeit noch nicht
- `GET /v1/alarms`, `GET /v1/alarms/stream` (SSE), `POST /v1/alarms/{id}/ack` (`operator`/`note`, `409`
  bei Double-Ack, RB-01) stehen vollständig im Contract (openapi). G3 entwickelt gegen die Spec.
- **⚠️ Noch nicht als Laufzeit-Route implementiert** (nur Alarm-Generierung DTB-27 läuft) — ein Live-Call
  liefert aktuell `404`. Offene Implementierungs-Tasks (Alarm-Serving).

### G3-Versandstand + offene Punkte für die nächste Team-Sync-Runde (2026-06-27)
- Versandfertig auf dem Desktop: `G2-API-v1-openapi.yaml` (aktuelle vollständige G2→G3-Spec = Repo-Stand)
  und `G1-API-Vertrag-G2-konsumiert.yaml` (was G2 von G1 abruft) + `G3-Nachricht-v1-thresholds-…txt`.
- **Offen:** (a) G3-Sign-off `/v1/thresholds` (Endpoint + 4 neue Felder); (b) Alarm-Serving implementieren;
  (c) finale G1-Schwellen — der `vereisung`-Block ist noch zu kalibrieren, `flatline_epsilon_c` ist
  bereits aus dem DS18B20-Datenblatt abgeleitet (DTB-20).
