# Backend-Konzept — Gruppe 2 (Vereisungserkennung ANR)

> **Konzeptplan ausschließlich für die Backend-Gruppe (G2).** Bewusst eng geschnitten: nur **was G2
> baut**. Der frühere `Architektur-Stack-Konzept` war absichtlich breit (alle drei Gruppen) und wurde
> abgelöst — dieses Dokument ersetzt ihn für unseren Scope.
> Bezug: `Usecase-quick.md` (FA/NF/RB), `Schwellenwerte.md` (Bewertungslogik).

## 1. Scope & Abgrenzung

**G2 baut:** Daten-Ingest · Datenhaltung/Datenmodell · **Vereisungsbewertung** · Alarm-Generierung ·
Prognose · API · Logging/Audit · Konfiguration (Schwellen).

**G2 baut NICHT:**
- **Sensor-Hardware/Messung** → Gruppe 1 (G2 definiert nur, *welche* Daten in welchem Format reinkommen).
- **Visualisierung/UI** → Gruppe 3 (G2 liefert nur die Daten über die API).

**Die einzige Naht = API + Datenmodell — und die gehört uns.** Zur Sensorik (G1) holen **wir** die Messwerte per **Pull** ab (G1 stellt einen Abfrage-Endpoint bereit, wir pollen); zu G3 liefern wir über unsere API, G3 konsumiert sie.

## 2. Backend-Komponenten (Module)

```
   (G2 pollt G1, Intervall ≤60s selbst bestimmt)                    (an G3)
  G1: GET /current ◄─ poll ─ [Ingest/Poller] ─► [Validierung/Plausibilität] ─► [Persistenz]
   G1: GET /health  ◄─ check ─┘                  │  Stale/Defekt-Check         │
                                                 ▼                             ▼
                                           (sicherer Zustand)           [Bewertung] ──► [Alarm]
                                                                              │            │
                                                                              ▼            ▼
                                                                        [Persistenz]   [API: GET ...] ─► G3
                                          [Prognose 30 min] ◄── liest Zeitreihe ──┘
                                          [Config/Schwellen]  [Logging/Audit]  (querschnittlich)
```

| Modul | Aufgabe | Anf. |
|---|---|---|
| **Ingest** | Messwerte bei G1 **pollen** (`GET /current`, Intervall selbst bestimmt) + `GET /health`, Eingangsvalidierung | FA-Schnittstellen |
| **Validierung/Plausibilität** | Bereichscheck, Stale-Erkennung (>180 s), Sensor-Defekt (Flatline/Sprung/Timeout) | FA „veraltete Daten/defekte Sensoren", NF-01 |
| **Persistenz** | Speichern von Messwerten, Bewertungen, Alarmen, Quittierungen | FA Datenspeicherung, NF-09 |
| **Bewertung** | **Vereisungsrisiko** (4-Stufen-Logik) aus T_s/T_d/RH | FA Risikobewertung, `Schwellenwerte.md §2` |
| **Alarm** | Schwellüberschreitung → Alarm-Objekt + Schweregrad | FA Alarmierung, NF-08 |
| **Prognose** | 30-min-Trend (Extrapolation T_s, T_d, Drucktendenz) | FA 30-min-Vorlauf |
| **API** | Serving-Endpoints für G3 (aktueller Zustand, Historie, Alarme) — **kein** Ingest-Endpoint (Daten kommen per Pull von G1) | FA Schnittstellen |
| **Config** | Schwellen zur Laufzeit parametrierbar | FA/NF-05 |
| **Logging/Audit** | append-only Protokoll aller Mess-/Bewertungs-/Alarm-/Quittierungs-Events | FA Logging, NF-09 |

## 3. Interner Datenfluss

**Poller** holt `GET /current` bei G1 (Intervall ≤ 60 s, von G2 bestimmt; `GET /health` als Verfügbarkeits-Check) → **Validierung** (Bereich, Plausibilität, Stale/Defekt) → **DB `readings`** →
**Bewertung** (`Schwellenwerte.md §2`) → **`assessment`** (+ ggf. **`alarm`**) → **DB** →
`GET /assessment/current` → (G3). Querschnitt: jedes Event ins **Audit-Log**; Bewertung liest Config-Schwellen.

> **Fail-safe:** Bei Stale/Defekt/Ausfall **nicht** auf GRÜN gehen → mindestens GELB/„unbekannt" + Warnung (NF-01).

## 4. Datenmodell (Backend)

| Entität | Felder (Kern) |
|---|---|
| `reading` | id · sensor_id · ts(UTC, = G1 `measured_at`) · surface_temp_c · air_temp_c · humidity_pct · dew_point_c(berechnet) · pressure_hpa · status(G1) · ice_indicator(optional/G1/sim) · source(`real|sim`) · received_at |
| `assessment` | id · ts · reading_id · risk_level(`green|yellow|orange|red`) · driving_factor · threshold_set_id · explanation |
| `alarm` | id · assessment_id · severity · raised_at · state(`active|acknowledged`) |
| `acknowledgement` | id · alarm_id · operator · note · ts  *(append-only, NF-09)* |
| `threshold_set` | id · name · params(json) · valid_from · changed_by  *(NF-05)* |
| `audit_log` | append-only Event-Log |

> **Mapping G1 → `reading`:** Die Pflichtfelder aus G1s `GET /current` (`measured_at`, `sensor_id`, `surface_temp_c`, `air_temp_c`, `humidity_pct`) landen 1:1 in `reading`. `pressure_hpa` und `status` kommen ebenfalls aus G1, sind aber verhandelbar. `dew_point_c` berechnet G2 intern; `ice_indicator`, `source` und `received_at` sind G2-interne Ergänzungen.
>
> **DB-Typen (MySQL/MariaDB):** `id`→`BIGINT AUTO_INCREMENT`, Zeitstempel→`DATETIME(3)` (UTC),
> `params`→`JSON`, Enums→`VARCHAR`/`ENUM`. Schema als handgeschriebenes `schema.sql` (kein Alembic → E-35; s. §6/§6a).

## 5. Bewertungslogik (Kern-IP von G2)

Vollständig in **`Schwellenwerte.md §2`**: 4 Stufen 🟢🟡🟠🔴 aus **Oberflächentemperatur + Taupunkt-Abstand
+ Feuchte** (Niederschlag als Faktor gestrichen — Customer-Scope, → Entscheidungslog **E-32**), mit Hysterese gegen Chattering. Löst beide dokumentierten Vorfälle korrekt auf.
Betriebspunkt (Fehlalarm ↔ Auslassung, K1) **parametrierbar**, Default sicherheitsbetont.

## 6. Tech-Stack Backend (T0)

> **Datenbank ist nicht mehr offen:** Die Geschäftsleitung gibt **MySQL** verbindlich vor
> (`Surprise Anforderungen.txt`, 22.06.2026 — GL-Gründe: vorhandene IT-Kompetenz, etablierte
> Betriebs-/Backup-Prozesse, geringerer Wartungsaufwand, bewährte Verfügbarkeit). Die von der GL
> geforderte Alternativen-/Risiko-Analyse steht in **§6a**. Die übrigen Bausteine bleiben
> begründungspflichtig (Entscheidungslogbuch).

| Baustein | Optionen | Wahl/Empfehlung T0 |
|---|---|---|
| Sprache/Framework | Python **FastAPI** · Flask · Node/Express | FastAPI (schnelle REST + Validierung via Pydantic) |
| **Datenbank** | ~~SQLite · PostgreSQL · TimescaleDB~~ | **MySQL 8 / MariaDB — durch GL vorgegeben** (dev = prod, **native MariaDB**, kein Docker → E-35) |
| DB-Zugriff | ~~SQLAlchemy ORM~~ · raw SQL | **rohes PyMySQL + Repository-Pattern** (parametrisierte Queries Pflicht; **kein ORM** → E-35) |
| Migrationen | ~~Alembic~~ · SQL-Skripte | **handgeschriebenes `schema.sql`** (kein Alembic → E-35) |
| Datenabruf | **HTTP-Pull** (G2 pollt G1s `GET /current`) · MQTT (Skalierung) | HTTP-Pull |
| Bewertung | reine Funktion (testbar) + Config | als isolierbares Modul (Coverage ≥ 80 %) |

> **Dev-Setup (E-35):** Native MariaDB/MySQL für alle — geteilte Pi-Instanz via SSH-Tunnel ODER lokale
> Installation (**kein Docker**) — gleiche DB lokal wie im Betrieb, kein SQL-Dialekt-Drift. **MariaDB** ist der quelloffene, Drop-in-kompatible MySQL-Ersatz und auf dem
> Raspberry Pi (s. `Raspberry-Pi-Hosting-Anleitung.md`) die ressourcenschonendere Wahl. Die
> **Bewertungslogik bleibt DB-frei** (reine Funktion) — sie ist von der DB-Wahl nicht betroffen.
> Übrige Bausteine: Wahl nach **Team-Kompetenz** begründen — nicht vorwegnehmen.

## 6a. DB-Vorgabe MySQL — Alternativen, Vor-/Nachteile, Auswirkungen, Risiken

> Erfüllt die von der Geschäftsleitung geforderte Dokumentationspflicht (`Surprise Anforderungen.txt`):
> untersuchte Alternativen, Vor-/Nachteile, Auswirkungen auf Architektur/Implementierung und Risiken —
> vollständige fachliche Analyse. Werte/Annahmen gegen die finalen Vorgaben (G1-Schwellen, reale Last)
> plausibilisieren.

**(1) Untersuchte Alternativen**

| Option | Kurzcharakter |
|---|---|
| **MySQL 8 / MariaDB** (vorgegeben) | Server-RDBMS, im Haus etabliert |
| SQLite | Eingebettete Datei-DB, null Setup |
| PostgreSQL / TimescaleDB | Server-RDBMS, stark bei Zeitreihen |
| InfluxDB | Spezialisierte Zeitreihen-DB |

**(2) Vor-/Nachteile**

- **MySQL/MariaDB:** + im Unternehmen vorhandene Kompetenz, Backup/Betrieb etabliert, ausgereift, gute
  Treiber-Unterstützung, MariaDB Pi-tauglich. − braucht laufenden Server-Prozess (zusätzliche
  Betriebs-/Ausfallfläche), kein nativer Zeitreihen-Vorteil, Setup-Hürde im Dev.
- **SQLite:** + null Setup, ideal für schnellen Prototyp/Tests. − nicht für parallelen Server-/
  Mehrbenutzerbetrieb gedacht, widerspricht der GL-Vorgabe, späterer Migrationsaufwand.
- **PostgreSQL/TimescaleDB:** + technisch sehr stark für Sensorzeitreihen. − im Haus *nicht* etabliert →
  widerspricht dem GL-Kriterium „bestehende Kompetenz wiederverwenden".
- **InfluxDB:** + spezialisiert auf Zeitreihen. − Fremd-Stack, Overkill für Prototyp, gegen GL-Vorgabe.

**(3) Auswirkungen auf Architektur/Implementierung**

- Persistenz (`storage/`) strikt über **Repository-Pattern + rohes PyMySQL** (parametrisierte Queries
  Pflicht; **kein ORM** → E-35) → DB-Detail gekapselt; Ingest, Bewertung und API bleiben DB-agnostisch.
- **Native MariaDB** (Pi via Tunnel / lokal; **kein Docker** → E-35); Schema als **handgeschriebenes `schema.sql`** (kein Alembic).
- **Datentyp-Mapping** (§4): `id`→`BIGINT AUTO_INCREMENT`, `ts`/`received_at`→`DATETIME(3)` (UTC),
  `params(json)`→`JSON`, Enums (`risk_level`, `state`)→`VARCHAR`+CHECK bzw. `ENUM`.
- **Connection-Handling** über PyMySQL-Verbindungen (Repository-gekapselt) statt Datei-Handle; Zugangsdaten über **Env-Var/
  Secret**, nie im Code (Security/NF-07).
- Betrieb auf **Raspberry Pi**: MariaDB als Dienst, Datenverzeichnis auf stabilem Medium
  (SD-Karten-Verschleiß bei Dauerschreiblast bedenken).

**(4) Risiken / Einschränkungen**

- **Setup-Hürde Anfänger-Team** (native MariaDB) kann M2 verzögern → geteilte Pi-MariaDB + Kurzanleitung als
  Mitigation (kein Docker nötig → E-35).
- **Zusätzliche Ausfallfläche:** der DB-Prozess kann ausfallen → **Fail-safe NF-01 muss greifen** (bei
  DB-Fehler nie GRÜN, sondern GELB/„unbekannt" + Warnung).
- **Langsamere Tests** ggü. SQLite-in-memory → Bewertungslogik bleibt DB-frei testbar; Persistenz-Tests
  laufen gegen den Container.
- **Ressourcen/SD-Karte auf dem Pi** bei Dauerschreiblast (Sensordaten) → Retention/Rotation einplanen.

**Schwerwiegende technische Gegenargumente gegen MySQL?** Für die erwartete Last eines Regional-Flughafen-
Prototyps (moderate Sensordatenrate): **keine** — MySQL/MariaDB ist dafür ausreichend dimensioniert. Die
GL-Vorgabe wird daher **angenommen**, nicht angefochten. *(Vom Team zu bestätigen.)*

## 7. Vorschlag Code-/Repo-Struktur (`Alarmsystem-Dev`)

```
src/
  ingest/        # Poller (holt `GET /current` von G1) + Health-Check, Eingangsvalidierung
  model/         # Datenklassen / Schemas
  assessment/    # Vereisungslogik (Schwellenwerte) — Kernmodul, hohe Testabdeckung
  storage/       # DB-Zugriff (Repository-Pattern, rohes PyMySQL → MySQL/MariaDB; kein ORM, E-35)
  api/           # Serving-Endpoints für G3
  config/        # Schwellen/Parameter (parametrierbar)
  forecast/      # 30-min-Trend (T3)
migrations/      # handgeschriebenes schema.sql (DDL; kein Alembic, E-35)
tests/           # Unit-/Integrationstests, v. a. assessment
config/          # Default-Schwellenwerte (aus Schwellenwerte.md)
# native MariaDB (Pi via SSH-Tunnel / lokal; kein Docker, E-35)
```

## 8. Ausbaustufen (Backend-scoped)

- **T0 (Kern):** Poll (`GET /current` von G1) → speichern → Schwellwert-Bewertung → `GET /v1/assessment/current` → `GET /v1/health`.
- **T1:** Plausibilität/Stale/Defekt-Erkennung, Alarm-Generierung, alle Messgrößen.
- **T2:** Quittierung (FA-10), Audit-Trail, Schwellen-Config-Endpoint, Historie.
- **T3:** 30-min-Prognose, Multi-Sensor (NF-11), Fernwartung + Auth (NF-07).

## 9. Schnittstellen nach außen

### 9.1 von G1 (Sensorik) — G2 ist Client, G1 liefert folgenden Contract

G1 stellt eine **einzelne Sensor-API** bereit. G2 pollt sie im selbst gewählten Intervall (≤ 60 s).

**`GET /current`** — Snapshot aller aktuellen Messwerte mit gemeinsamem Zeitstempel:

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

- **`measured_at`** (ISO-8601 UTC): **PFLICHT** — ein Zeitstempel für alle Werte. Ohne dieses Feld kann G2 keine Stale-Erkennung betreiben.
- **`sensor_id`**: **PFLICHT** — eindeutige Sensor-Identifikation.
- **`surface_temp_c`**, **`air_temp_c`**, **`humidity_pct`**: **PFLICHT** — Trias für die Vereisungsbewertung.
- **`pressure_hpa`**: optional/Kontext.
- **`status`**: Sensor-Lebenszeichen (`ok` | `fault`).

**`GET /health`** — Verfügbarkeits-Check der G1-API:

- `200 OK` → G1 erreichbar.
- `503 Service Unavailable` → G1 nicht betriebsbereit / Fehlerzustand.

> **Verhandlungsposition gegenüber G1:** `measured_at` und `/health` sind **nicht verhandelbar**. Feldnamen, Einheiten und optionale Felder können synchronisiert werden (Seam-Sync), solange die Pflicht-Trias erhalten bleibt.

### 9.2 zu G3 (Frontend) — G2 ist Server, G3 konsumiert per `GET`

G2 baut die API, G3 ruft sie ab. Alle Endpoints unter Pfad-Präfix **`/v1/`** (Versionierung, AE-03 → E-36).

- **`GET /v1/assessment/current`** — aktuelle Bewertung: `risk_level` (`green|yellow|orange|red|unknown`),
  `driving_factor`, `explanation`, `surface_temp_c`, `dew_point_c`, `delta_t`, `humidity_pct`,
  `measured_at`, `assessed_at`, `is_stale`, `sensor_status`. (`unknown`+`is_stale` = Fail-safe, NF-01.)
- **`GET /v1/health`** — Verfügbarkeit von G2.
- **Alarme = Push-Events, kein Poll-Scan (E-37):** **`GET /v1/alarms/stream`** (Server-Sent Events) —
  G3 hält **eine** Verbindung, G2 **pusht** Alarme live. **`GET /v1/alarms`** bleibt als
  **Zustands-Abfrage** (aktive Alarme beim Laden + Resync nach Verbindungsabriss — Sicherheits-Backstop).
- **`POST /v1/alarms/{id}/ack`** — Quittierung (reine UI-/Audit-Aktion, **kein** Bahn-Aktor, RB-01).
- **`GET /v1/readings`** — Historie.

Verbindliche Form in der OpenAPI-Spec (DTB-19); eingefroren in `04-Source-code/docs/API_FROZEN_v1.md` (DTB-35).
Internes Datenmodell s. §4.

## 10. Mapping FA/NF → Backend-Modul (Kurzfassung)

| Anforderung | Modul |
|---|---|
| Risikobewertung / Alarmierung | Bewertung, Alarm |
| Temperatur/Feuchte/Druck/Taupunkt | Ingest, Model, Bewertung |
| Datenspeicherung / Logging | Persistenz, Audit |
| Vorhersage + veraltete Daten + defekte Sensoren | Prognose, Validierung |
| Schnittstellen | API |
| Parametrierbarkeit (NF-05) | Config |
| Fernwartung (NF-07) | API + Auth (T3) |
| Ausfallrobustheit (NF-01) | Validierung (fail-safe), Persistenz (Puffer) |
| Keine Auto-Freigabe (RB-01) | API liefert nur Bewertung — **kein** Freigabe-/Aktor-Endpoint |
