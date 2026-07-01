# Faktenblatt — Naht-Umstellung (Pull) + 3-Faktor-Bewertung

> **Stand:** 2026-06-22 · **Zweck:** **Single Source of Truth** für die zwei am 22.06. beschlossenen
> Änderungen + **Change-Map** für die Spiegel-Dokumente (Phase B). Dient zugleich als Grundlage für den
> Team-Sync mit G1. **Bezug:** Entscheidungslog **E-31** (Pull) + **E-32** (Niederschlag-Streichung),
> `Backend-Konzept.md`, `Schwellenwerte.md`. **Quelle gewinnt** bei Konflikt: dieses Blatt + E-31/E-32.

---

## Teil 1 — Kanonische Definitionen (so gilt es jetzt)

### A) Datennaht G1 → G2 = **Pull** (ersetzt Push `POST /readings`)

- **G1 stellt bereit** (G1 = Server, G2 = Client an dieser Naht):
  - **`GET /current`** — liefert **alle aktuellen Messwerte als _einen_ Snapshot** mit **_einem_ gemeinsamen
    Mess-Zeitstempel `measured_at`** (UTC/ISO-8601). **Kein** Aufsplitten in Einzel-Endpoints.
  - **`GET /health`** — Verfügbarkeit (200 = ok / 503 = fault).
- **G2 baut** einen **Poller/HTTP-Client**, der `GET /current` in einem **selbst bestimmten Intervall
  (≤ 60 s)** abruft, `GET /health` als Erreichbarkeits-Check nutzt, validiert (Bereich, Stale, Defekt),
  persistiert, bewertet.
- **Fail-safe (NF-01):** Erreichbarkeit (`/health`/Timeout) **getrennt** von Datenaktualität
  (`measured_at` älter als der Stale-Timeout `120 s` → stale) prüfen → bei beidem **nie GRÜN**, sondern
  GELB/„unbekannt".
- **Kein** von G2 gehosteter `POST /readings`-Endpoint mehr.

**Referenz-Payload `GET /current` (Feldnamen final im Team-Sync):**
```json
{
  "measured_at": "2026-06-22T14:03:05Z",
  "sensor_id": "anr-rwy-01",
  "surface_temp_c": -0.4,
  "air_temp_c": 1.2,
  "humidity_pct": 96,
  "pressure_hpa": 1013,
  "status": "ok"
}
```

### B) Bewertung = **3 Faktoren** (Niederschlag gestrichen, Customer-Scope)

Faktoren: **Oberflächentemperatur `T_s` + Taupunkt-Abstand `ΔT` + Feuchte `RH`**. `T_a`/`T_d`/`p` bleiben
Kontext/Prognose. Geänderte Regeln in `Schwellenwerte.md §2`:

| | Neu (gilt) |
|---|---|
| **🔴 ROT** | `T_s ≤ 0 °C` **und** `ΔT ≤ 0 °C` |
| **„Feuchte vorhanden"** | `ΔT ≤ 1,0 °C` (Oberflächennähe zum Taupunkt; Luft-`RH`-Schwelle entfernt → **E-33**) |

GRÜN/GELB/ORANGE unverändert. Beide Pflicht-Vorfälle bleiben grün (liefen nie über Niederschlag).
Schwellen (0 °C / 1,0 °C) sind **projektfinal**, parametrierbar (NF-05) — G1-Finalwerte nicht mehr zu erwarten, aus Datenblatt/Standort plausibilisiert.

### C) Datenmodell-Delta

- `reading`: Feld **`precip_type` entfernt**; `ts(UTC)` = G1s `measured_at`. Sonst unverändert.

---

## Teil 2 — Change-Map für Phase B (Spiegel nachziehen)

> **Schon erledigt (Phase A — Kern):** `Schwellenwerte.md`, `Backend-Konzept.md`,
> `Entscheidungslog` (E-10/E-30/E-31/E-32). **Journal `erinnerung/` bleibt append-only — NICHT ändern.**

Jeder Agent: gegen dieses Faktenblatt arbeiten, in der Zieldatei nach den Mustern **greppen** (nicht nur die
genannten Zeilen), konsistent ersetzen, **keine** Use-Case-Werte erfinden.

| Datei | Push → Pull | Niederschlag raus | bekannte Stellen |
|---|---|---|---|
| `README.md` | ✅ `POST /readings`-Diagramm/Scope/Tech-Stack → `GET /current` Pull + `/health` | ✅ Niederschlag aus Scope/Logik | Z99, Z120, Z228, Z355-356 + Niederschlag-Treffer |
| `02-Arbeitsdokumente/Tasks+Projektplan.md` | ✅ P2.1 „Ingest `POST /readings`" → „Poller `GET /current`" | ✅ Niederschlag-Tasks/Erwähnungen | Z38 + Niederschlag-Treffer |
| `02-Arbeitsdokumente/Projektplan-Jira-Backlog-G2.md` | ✅ **massiv**: alle `POST /readings`, P1.x/P2.x, DTB-Tasks, Payload-Felder | ✅ `precip_type`, Niederschlag-Pflichtfelder | viele (grep `POST /readings`, `precip`, `Niederschlag`) |
| `02-Arbeitsdokumente/Usecase-quick.md` | ✅ FA-Schnittstelle (FA-09) auf Pull | ✅ FA/Erwähnung Niederschlag prüfen/streichen | grep `Niederschlag`, `POST`, `FA-09` |
| `Agents-gpt-gemini.md` | ✅ „G1 pusht dagegen" → Pull | ✅ Niederschlag-Erwähnung | Z41 + Niederschlag-Treffer |
| `04-Source-code/README.md` | ✅ `src/ingest/` „REST-Ingest `POST /readings`" → Poller | ✅ falls Niederschlag genannt | Z7 |
| `04-Source-code/config/README.md` | — | ✅ falls Niederschlag-Parameter gelistet | grep `Niederschlag`/`precip` |

**Vorsicht / niedrige Prio (Instruktionsdateien, ggf. gitignored — nur auf explizite Ansage):**
Root `CLAUDE.md` / `AGENTS.md` nennen Niederschlag(-sart) in der Hintergrund-/Designbeschreibung. Nicht
automatisch mit-ändern.

**Nach Phase B:** Konsistenz-Review (kein `POST /readings` mehr außerhalb historischer E-30-Notiz; kein
„Niederschlag" als aktiver Faktor/Feld); `Fortschrittslog.md` §2 + `erinnerung/stand.md` (kein Journal!)
mit einem neuen Eintrag nachziehen.
