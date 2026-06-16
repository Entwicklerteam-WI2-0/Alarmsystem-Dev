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

**Die einzige Naht = API + Datenmodell — und die gehört uns.** G1 pusht dagegen, G3 konsumiert sie.

## 2. Backend-Komponenten (Module)

```
   (von G1)                                                         (an G3)
  POST /readings ─► [Ingest] ─► [Validierung/Plausibilität] ─► [Persistenz]
                                        │  Stale/Defekt-Check        │
                                        ▼                            ▼
                                  (sicherer Zustand)          [Bewertung] ──► [Alarm]
                                                                    │            │
                                                                    ▼            ▼
                                                              [Persistenz]   [API: GET ...] ─► G3
                                  [Prognose 30 min] ◄── liest Zeitreihe ──┘
                                  [Config/Schwellen]  [Logging/Audit]  (querschnittlich)
```

| Modul | Aufgabe | Anf. |
|---|---|---|
| **Ingest** | Messdatensätze annehmen (REST), Eingangsvalidierung | FA-Schnittstellen |
| **Validierung/Plausibilität** | Bereichscheck, Stale-Erkennung (>180 s), Sensor-Defekt (Flatline/Sprung/Timeout) | FA „veraltete Daten/defekte Sensoren", NF-01 |
| **Persistenz** | Speichern von Messwerten, Bewertungen, Alarmen, Quittierungen | FA Datenspeicherung, NF-09 |
| **Bewertung** | **Vereisungsrisiko** (4-Stufen-Logik) aus T_s/T_d/RH/Niederschlag | FA Risikobewertung, `Schwellenwerte.md §2` |
| **Alarm** | Schwellüberschreitung → Alarm-Objekt + Schweregrad | FA Alarmierung, NF-08 |
| **Prognose** | 30-min-Trend (Extrapolation T_s, T_d, Drucktendenz) | FA 30-min-Vorlauf |
| **API** | Serving für G3 (aktueller Zustand, Historie, Alarme), Ingest-Endpoint | FA Schnittstellen |
| **Config** | Schwellen zur Laufzeit parametrierbar | FA/NF-05 |
| **Logging/Audit** | append-only Protokoll aller Mess-/Bewertungs-/Alarm-/Quittierungs-Events | FA Logging, NF-09 |

## 3. Interner Datenfluss

`POST /readings` → **Validierung** (Bereich, Plausibilität, Stale/Defekt) → **DB `readings`** →
**Bewertung** (`Schwellenwerte.md §2`) → **`assessment`** (+ ggf. **`alarm`**) → **DB** →
`GET /assessment/current` → (G3). Querschnitt: jedes Event ins **Audit-Log**; Bewertung liest Config-Schwellen.

> **Fail-safe:** Bei Stale/Defekt/Ausfall **nicht** auf GRÜN gehen → mindestens GELB/„unbekannt" + Warnung (NF-01).

## 4. Datenmodell (Backend)

| Entität | Felder (Kern) |
|---|---|
| `reading` | id · sensor_id · ts(UTC) · surface_temp_c · air_temp_c · humidity_pct · dew_point_c(berechnet) · pressure_hpa · precip_type · ice_indicator · source(`real|sim`) · received_at |
| `assessment` | id · ts · reading_id · risk_level(`green|yellow|orange|red`) · driving_factor · threshold_set_id · explanation |
| `alarm` | id · assessment_id · severity · raised_at · state(`active|acknowledged`) |
| `acknowledgement` | id · alarm_id · operator · note · ts  *(append-only, NF-09)* |
| `threshold_set` | id · name · params(json) · valid_from · changed_by  *(NF-05)* |
| `audit_log` | append-only Event-Log |

## 5. Bewertungslogik (Kern-IP von G2)

Vollständig in **`Schwellenwerte.md §2`**: 4 Stufen 🟢🟡🟠🔴 aus **Oberflächentemperatur + Taupunkt-Abstand
+ Feuchte + Niederschlag**, mit Hysterese gegen Chattering. Löst beide dokumentierten Vorfälle korrekt auf.
Betriebspunkt (Fehlalarm ↔ Auslassung, K1) **parametrierbar**, Default sicherheitsbetont.

## 6. Tech-Stack Backend (T0 — Optionen offen, gehört ins Entscheidungslogbuch)

| Baustein | Optionen | Empfehlung T0 |
|---|---|---|
| Sprache/Framework | Python **FastAPI** · Flask · Node/Express | FastAPI (schnelle REST + Validierung via Pydantic) |
| Datenbank | **SQLite** (Prototyp) · PostgreSQL · TimescaleDB | SQLite für T0, später Postgres |
| Übertragung | **HTTP-POST** (T0) · MQTT (Skalierung) | HTTP-POST |
| Bewertung | reine Funktion (testbar) + Config | als isolierbares Modul (Coverage ≥ 80 %) |

> Wahl nach **Team-Kompetenz** treffen und begründen — nicht vorwegnehmen.

## 7. Vorschlag Code-/Repo-Struktur (`Alarmsystem-Dev`)

```
src/
  ingest/        # REST-Endpoint, Eingangsvalidierung
  model/         # Datenklassen / Schemas
  assessment/    # Vereisungslogik (Schwellenwerte) — Kernmodul, hohe Testabdeckung
  storage/       # DB-Zugriff (Repository-Pattern)
  api/           # Serving-Endpoints für G3
  config/        # Schwellen/Parameter (parametrierbar)
  forecast/      # 30-min-Trend (T3)
tests/           # Unit-/Integrationstests, v. a. assessment
config/          # Default-Schwellenwerte (aus Schwellenwerte.md)
```

## 8. Ausbaustufen (Backend-scoped)

- **T0 (Kern):** Ingest → speichern → Schwellwert-Bewertung → `GET /assessment/current` → `GET /health`.
- **T1:** Plausibilität/Stale/Defekt-Erkennung, Alarm-Generierung, alle Messgrößen.
- **T2:** Quittierung (FA-10), Audit-Trail, Schwellen-Config-Endpoint, Historie.
- **T3:** 30-min-Prognose, Multi-Sensor (NF-11), Fernwartung + Auth (NF-07).

## 9. Schnittstellen nach außen (abstimmen, nicht bauen)

- **zu G1 (Sensorik):** `POST /readings`-**Payload** — welche Messgrößen real geliefert werden (Seam-Sync).
- **zu G3 (Frontend):** `GET`-**Antwortformate** — was angezeigt wird (Seam-Sync).
- Details in der API-Spezifikation (geplant); Datenmodell s. §4.

## 10. Mapping FA/NF → Backend-Modul (Kurzfassung)

| Anforderung | Modul |
|---|---|
| Risikobewertung / Alarmierung | Bewertung, Alarm |
| Temperatur/Feuchte/Druck/Taupunkt/Niederschlag(-art) | Ingest, Model, Bewertung |
| Datenspeicherung / Logging | Persistenz, Audit |
| Vorhersage + veraltete Daten + defekte Sensoren | Prognose, Validierung |
| Schnittstellen | API |
| Parametrierbarkeit (NF-05) | Config |
| Fernwartung (NF-07) | API + Auth (T3) |
| Ausfallrobustheit (NF-01) | Validierung (fail-safe), Persistenz (Puffer) |
| Keine Auto-Freigabe (RB-01) | API liefert nur Bewertung — **kein** Freigabe-/Aktor-Endpoint |
