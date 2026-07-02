# Architekturdiagramm — Vereisungserkennung ANR (G2 Backend)

> **Zweck:** Einziges verbindliches, nachzeichnungsfähiges Architekturdiagramm für Präsentation,
> Doku und Onboarding. Ersetzt die ASCII-Skizze aus `Backend-Konzept.md` §2 und das WhatsApp-Photo
> in `assets/` durch eine versionierbare, auf GitHub nativ gerenderte Mermaid-Darstellung.
>
> **Quellen (belegbasiert, nichts erfunden):**
> `Backend-Konzept.md` §1–§9 · `04-Source-code/README.md` (Datenfluss, Naht) ·
> `04-Source-code/docs/API_FROZEN_v1.md` · `Schwellenwerte.md` ·
> Entscheidungslog E-29/E-31/E-35/E-36/E-37/E-44.
>
> **Scope:** G2 = Backend (dieses Repo). G1 (Sensorik) und G3 (Frontend) nur als Naht-Partner
> gezeigt — nicht mitkonzipiert. Für Folien: Mermaid-Block als Screenshot oder via
> `mermaid-cli` (`mmdc -i ... -o ...png`) exportieren.

---

## 1. Systemkontext — Gruppen, Nähte, Datenrichtung

Drei Gruppen, **zwei Nähte** — beide gehören fachlich G2. G1 wird **gepollt** (G2 = Client),
G3 wird **bespielt** (G2 = Server).

```mermaid
flowchart LR
    subgraph G1["G1 — Sensorik (Wasserfall)"]
        G1H["Sensor-Hardware<br/>ESP32 / Pi + BME280 / DS18B20 / STEMMA-Soil"]
        G1API["G1-API<br/>GET /current · GET /health"]
        G1H --> G1API
    end

    subgraph G2["G2 — Backend (Wasserfall, dieses Repo)"]
        G2CORE["FastAPI-Service<br/>Ingest → Bewertung → Persistenz → API"]
    end

    subgraph G3["G3 — Frontend (Scrum)"]
        G3UI["Web-UI<br/>Ampel · Alarme · Historie"]
    end

    DB[("MariaDB / MySQL<br/>schema.sql")]

    G1API -. "HTTP-Pull<br/>alle 30 s (E-31)" .-> G2CORE
    G2CORE --> DB
    G2CORE -. "REST + SSE-Push<br/>/v1/ (E-36, E-37)" .-> G3UI

    classDef g1 fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    classDef g2 fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    classDef g3 fill:#fff3e0,stroke:#f57c00,color:#e65100
    classDef db fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c
    class G1,G1H,G1API g1
    class G2,G2CORE g2
    class G3,G3UI g3
    class DB db
```

**Methoden-Vergleich (Kursziel):** G1 & G2 arbeiten nach **Wasserfall** (Sequence: Anforderung →
Design → Implementierung → Test), G3 nach **Scrum** (Sprints, Daily Standup). Diese bewusste
Parallelität ist Teil der Lernaufgabe und in der Präsentation als Teamorganisations-Kriterium
zu zeigen.

---

## 2. Backend-Intern — Modul-Fluss und kritischer Pfad

Die Innenstruktur von G2. **Kritischer Pfad** (rot): Ingest → Persistenz → Bewertung → Serving
→ Alarm → Ack, end-to-end verifiziert (`erinnerung/architektur-tiefenaudit-2026-06-30.md`).

```mermaid
flowchart TB
    ING["Ingest / Poller<br/>src/ingest/poller.py<br/>── GET /current + /health alle 30 s"]
    VAL["Validierung & Plausibilität<br/>Stale > 120 s · Flatline · Sprung-Guard<br/>── NF-01 Fail-safe"]
    READ[("reading")]
    ASSESS["Bewertung<br/>src/assessment/core.py<br/>── 4-Stufen 🟢🟡🟠🔴<br/>aus T_s · T_d · ΔT · RH<br/>Schwellenwerte.md §2"]
    FORE["Prognose 30 min<br/>src/forecast/trend.py"]
    ALARM["Alarm-Generierung<br/>src/alarm/<br/>── Severity · Hysterese"]
    ASR[("assessment")]
    ALR[("alarm")]
    ACKR[("acknowledgement")]
    AUD[("audit_log · append-only")]
    THR[("threshold_set<br/>parametrierbar NF-05")]
    CFG["Config<br/>src/config/ · config/thresholds.json"]
    API["API /v1/ <br/>src/api/v1.py<br/>── REST + SSE"]

    ING --> VAL
    VAL -->|"gültig"| READ
    VAL -.->|"stale/defekt<br/>→ unknown"| ASSESS
    READ --> ASSESS
    CFG --> ASSESS
    THR -.->|"lädt"| CFG
    ASSESS --> ASR
    ASSESS -->|"orange/red"| ALARM
    ALARM --> ALR
    READ --> FORE
    FORE -.->|"GELB vorab"| ASSESS
    ASR --> API
    ALR --> API
    READ --> API
    API --> ACKR
    API --> AUD

    classDef store fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c
    classDef core fill:#ffebee,stroke:#c62828,color:#b71c1c,stroke-width:2px
    classDef aux fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    class READ,ASR,ALR,ACKR,AUD,THR store
    class ASSESS,ALARM,API core
    class ING,VAL,FORE,CFG aux
```

---

## 3. API-Naht (eingefroren) — G2 stellt bereit, G3 konsumiert

Der **eingefrorene Contract v1.0** (DTB-26, P1.4). Wire-Form stabil; Breaking Changes laufen
nur über `/v2/`, nie über ein Brechen von `/v1/`. Source of Truth: `docs/API_FROZEN_v1.md` +
`docs/api/v1/openapi.yaml`.

```mermaid
flowchart LR
    subgraph G2S["G2 — Server (stellt bereit)"]
        H["GET /v1/health<br/>200 ok / 503"]
        AC["GET /v1/assessment/current<br/>flach, kein Envelope<br/>risk_level · Werte · is_stale"]
        STR["GET /v1/alarms/stream<br/>SSE text/event-stream<br/>Heartbeat ~15 s · Last-Event-ID"]
        AL["GET /v1/alarms<br/>Zustand + Resync-Backstop"]
        ACK["POST /v1/alarms/{id}/ack<br/>operator Pflicht · 409 bei Double-Ack"]
        RD["GET /v1/readings<br/>Historie (T1)"]
        TH["GET /v1/thresholds<br/>POST /v1/thresholds (Auth-gated)"]
    end

    G3C["G3 — Client<br/>(konsumiert nur GET + SSE,<br/>hostet nichts)"]

    H --> G3C
    AC --> G3C
    STR -.->|"Push live"| G3C
    AL --> G3C
    ACK --> G3C
    RD --> G3C
    TH --> G3C

    classDef srv fill:#e8f5e9,stroke:#388e3c,color:#1b5e20
    classDef cli fill:#fff3e0,stroke:#f57c00,color:#e65100
    class G2S,H,AC,STR,AL,ACK,RD,TH srv
    class G3C cli
```

**Fail-safe-Invarianten (NF-01, am Serving-Punkt hart durchgesetzt):**
`green` nur bei `is_stale=false` **und** `sensor_status=ok` · Stale **oder** `fault` → `unknown`
(nie GRÜN) · „keine Daten" → `503`, nicht `null`.

**RB-01:** `POST /v1/alarms/{id}/ack` ist reine UI-/Audit-Quittierung — **kein** Aktor, **keine**
Startbahn-Freigabe/Sperr-Endpoint existiert.

---

## 4. Deployment — Pi-Hosting

Betriebsmodell: **Raspberry Pi** als Host, native MariaDB (kein Docker → E-35), systemd-Service.
G1 im Echtbetrieb Sensor-Hardware, im Demo-Betrieb der G1-Simulator (`tools/g1_sim/`).

```mermaid
flowchart TB
    subgraph PI["Raspberry Pi (Produktiv-/Demo-Host)"]
        SVC["alarmsystem.service<br/>systemd · tools/"]
        APP["uvicorn src.main:app<br/>:8000"]
        DBPI[("MariaDB 11<br/>native, kein Docker")]
        SIM["G1-Simulator (Demo)<br/>tools/g1_sim/g1_sim.py<br/>:9101"]
    end

    DEV["Entwickler-Rechner<br/>(Windows, lokal)"]
    TUN["SSH-Tunnel<br/>ssh -L 8000:127.0.0.1:8000<br/>pi@192.168.1.102"]
    FEED["Demo-Feed<br/>tools/demo/g1_feed.py<br/>Live-Sim + Showcase"]

    SVC --> APP --> DBPI
    SIM -.-> APP
    DEV --> TUN --> APP
    FEED --> SIM

    classDef pi fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    classDef ext fill:#fff3e0,stroke:#f57c00,color:#e65100
    class PI,SVC,APP,DBPI,SIM pi
    class DEV,TUN,FEED ext
```

---

## 5. Technologie-Stack (Spalte pro Baustein)

| Baustein | Wahl | Begründung / ADR |
|---|---|---|
| Sprache / Framework | Python ≥ 3.12 · **FastAPI** · Pydantic | schnelle REST + Validierung (E-08) |
| DB | **MySQL / MariaDB** (native) | GL-Vorgabe (E-29); kein Docker (E-35) |
| DB-Zugriff | **rohes PyMySQL** + Repository-Pattern | kein ORM, parametrisierte Queries (E-35) |
| Migrationen | handgeschriebenes `schema.sql` | kein Alembic (E-35) |
| G1 → G2 | **HTTP-Pull** (30 s) | G2 = Client (E-31) |
| G2 → G3 | **REST + SSE** | Push für Alarme (E-37), eine API unter `/v1/` (E-36) |
| Testen | **pytest · ruff** | Bewertungslogik ≥ 80 % Coverage |

---

*Lebendes Dokument — bei Architektur-Änderung (neues Modul, neue Naht, Stack-Wechsel) dieses
Diagramm und die referenzierten Quellen (`Backend-Konzept.md`, `README.md`, `API_FROZEN_v1.md`)
gemeinsam nachziehen. Pflege: G2-Architekt.*
