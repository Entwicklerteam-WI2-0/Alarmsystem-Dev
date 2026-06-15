# Architektur- & Stack-Konzept — Vereisungserkennung ANR

**Deliverable:** Architektur (M1-Architekturideen → M2 Umsetzung) · **Status:** v0.1 — Entwurf
**Bezug:** `Usecase-quick.md` (FA/NF/RB/AE), `Stakeholderanalyse.md`, `Power-Interest-Grid.md`
**Vorgehen:** funktional, **von der Kernfunktion ausgehend** → dann Ausbaustufen. Konkrete Technologie-Auswahl ist **noch offen** (Projektregel) — hier zuerst die **Funktionsallokation**, Tech nur als Optionen.

---

## 1. Kernfunktion (der eine wesentliche Faden)

> **Aus realen Oberflächen-/Wetterdaten ein Vereisungsrisiko ermitteln und es dem Menschen als nachvollziehbare Entscheidungsgrundlage anzeigen — ohne selbst zu sperren/freizugeben (RB-01).**

Daraus folgt der **Kernpfad (Vertical Slice / MVP)**, der zuerst end-to-end laufen muss:

```
1 Sensor misst Oberfläche  →  Backend bewertet Risiko (Schwellwert)  →  Frontend zeigt Ampel + Werte
```

Alles Weitere (Prognose, Alarmierung, Quittierung, Multi-Sensor, Auth …) wird **auf diesen funktionierenden Faden aufgesetzt**, nicht davor.

---

## 2. Architektur-Überblick (3 Schichten)

```
 [ SENSORIK (G1) ]        [ BACKEND + DB (G2) ]              [ FRONTEND (G3) ]
  Messung,          ──►    Ingest · Plausibilität ·    ◄──►   Dashboard: Risiko+Werte,
  Zeitstempel,             Risikobewertung · Alarme ·          Status, Alarm, Quittierung,
  Senden                   Prognose · Audit                    Config-UI
                              ▲   │
                              │   ▼
                         [ DATENBANK(EN) ]
                          Zeitreihe (Messwerte),
                          Config/Schwellen, Audit-Log
```

**Schnittstelle = API + Datenmodell von G2** (laut Zeitplan Ende Woche 2 final) — das ist die *einzige* Naht, an der sich G1 und G3 ausrichten müssen.

---

## 3. Funktionsallokation pro Schicht  ← *primäre Aufgabe dieses Dokuments*

Legende Stufe: **T0** = Kernpfad (MVP) · **T1** = Kernfunktion vollständig · **T2** = Sicherheit/Betrieb · **T3** = Erweiterung.

### 3.1 Sensorik (Gruppe 1 — Wasserfall)

| Funktion | Anf. | Stufe | Min. Umsetzung |
|---|---|---|---|
| Oberflächentemperatur messen | FA-01 | **T0** | 1 Kontakt-/IR-Sensor |
| Luft-Temp + -Feuchte messen | FA-02 | T1 | kombinierter Sensor |
| Taupunkt | FA-01 | T1 | **berechnet** aus Temp+Feuchte (kein eigener Sensor) |
| Oberflächenfeuchte / Niederschlagsart | FA-01 | T1/T3 | Sensor oder **simuliert** |
| Eisindikator | FA-01 | T3 | **Proxy** (Temp≤0 & feucht/Taupunkt) oder simuliert — echter Sensor teuer (WX-500 ~4.800 €, K3) |
| Abtastung im Intervall + Zeitstempel | NF-02, FA-03 | **T0** | fixes Intervall, Uhr am Node |
| Lokale Plausibilität / Puffer bei Ausfall | FA-04, NF-01 | T2 | Store-&-Forward |
| Übertragung an Backend | FA-09 | **T0** | **HTTP-POST** (T0) → MQTT (T3) |
| Robustheit / Wartbarkeit | NF-06 | T2 | Gehäuse, steckbarer Tausch |

### 3.2 Backend + Datenbanken (Gruppe 2 — Wasserfall)

| Funktion | Anf. | Stufe | Min. Umsetzung |
|---|---|---|---|
| Ingest-Endpoint (Messwerte annehmen) | FA-09 | **T0** | ein POST-Endpoint |
| Persistenz mit Zeitstempel | FA-03 | **T0** | eine Tabelle `readings` |
| Plausibilität + Stale-Detection | FA-04 | T1 | Range-Check + „zu alt"-Flag |
| **Risikobewertung (Schwellwert)** | FA-05 | **T0** | Regel; auslösende Größe mitliefern (nachvollziehbar) |
| Parametrierbare Schwellen | NF-05, FA-11 | T2 | erst Config-Datei → später DB/UI |
| Alarm-Generierung | FA-08 | T1 | Schwellüberschreitung → Alarm-Objekt + Schweregrad |
| Quittierung / manuelle Entscheidung erfassen | FA-10 | T2 | Endpoint + Tabelle |
| Audit-Trail (Messwerte/Bewertung/Alarme/Quittierung) | FA-12, NF-09 | T2 | append-only Log |
| Prognose ≥ 30 min | FA-06 | **T3** | Trend/Extrapolation → Modell |
| API für Frontend | FA-09 | **T0** | GET aktueller Zustand |
| Auth / Zugriffsschutz | NF-07 | T3 | erst bei Fernzugriff (AE-02) |
| Datenmodell definieren | Schnittstelle | **T0** | Kernschema früh einfrieren |

### 3.3 Frontend (Gruppe 3 — Scrum)

| Funktion | Anf. | Stufe | Min. Umsetzung |
|---|---|---|---|
| Aktuelles Risiko (Ampel) + Messwerte | FA-07, FA-05 | **T0** | eine Dashboard-Seite, pollt API |
| Daten-/Sensorstatus (Aktualität) | FA-04, FA-07 | T1 | „Stand vor X min" / stale-Warnung |
| Eindeutige, schnell erfassbare Darstellung | NF-08 | T1 | Ampel zuerst, Details on demand (K8) |
| Alarmanzeige | FA-08 | T1 | sichtbarer Alarm + Schweregrad |
| Quittierungs-UI | FA-10 | T2 | Button + erfasste Entscheidung |
| Verlauf / Historie | FA-03, FA-12 | T2 | Zeitreihen-Chart |
| Schwellen-Config-UI | FA-11 | T2/T3 | Eingabemaske |
| Prognose-Anzeige (inkl. Konfidenz) | FA-06 | T3 | Verlauf + Unsicherheit (K2) |

---

## 4. Funktionale Ausbaustufen (Roadmap)

- **T0 — Kernpfad (zuerst lauffähig):** 1 Sensor → Ingest+Speichern → Schwellwert-Bewertung → Ampel im Dashboard. *Beweist die Integration über alle 3 Schichten — das, was Studi-Projekte sonst in Woche 3 killt.*
- **T1 — Kernfunktion vollständig:** alle Messgrößen (FA-01), Plausibilität+Stale (FA-04), nachvollziehbare Bewertung (FA-05), klare UI + Alarm (NF-08, FA-08).
- **T2 — Sicherheit & Betrieb:** Quittierung/manuelle Entscheidung (FA-10), Audit-Trail (FA-12/NF-09), Ausfallrobustheit/sicherer Zustand (NF-01), parametrierbare Schwellen (NF-05/FA-11), Historie.
- **T3 — Erweiterung:** Prognose ≥ 30 min (FA-06), Multi-Sensor/Standorte (NF-11), Fernzugriff (AE-02) + Auth (NF-07), Verfügbarkeitsziele (NF-03).

---

## 5. Was es MINDESTENS braucht (T0-Minimalset)

**Hardware (1 Sensor-Node):**
- Mikrocontroller mit Netzwerk (z. B. ESP32 — WLAN onboard, günstig) **oder** Raspberry Pi (mehr Rechenleistung, kann auch Backend lokal hosten).
- **Oberflächentemperatur:** IR-Sensor (z. B. MLX90614, berührungslos) oder Kontakt (DS18B20/PT100).
- **Luft-Temp + -Feuchte:** ein Kombisensor (z. B. SHT31/DHT22) → **Taupunkt rechnerisch**.
- Eisindikator zunächst **als Proxy/Simulation** (echter Fahrbahn-/Eissensor sprengt Budget, K3/K4).

**Software (Backend):** ein API-Endpoint (POST Messwert, GET Zustand) + eine kleine Bewertungsregel. Optionen (offen): Python **FastAPI/Flask** oder Node/Express.
**Datenbank:** eine Tabelle `readings`. Optionen (offen): **SQLite** (Prototyp) → PostgreSQL → TimescaleDB (Zeitreihe, T3).
**Übertragung:** **HTTP-POST** reicht für T0 (MQTT erst bei Multi-Sensor/Scale).
**Frontend:** eine Web-Seite, die die API pollt und Ampel+Werte zeigt. Optionen (offen): plain HTML/JS oder React/Vue.

> **Pragmatik-Hinweis (wichtig):** Reale Vorfeld-Sensorik in 3 Wochen ist unrealistisch. Empfehlung: **echter günstiger Sensor für die Kern-Messgröße** (Oberflächentemp + Feuchte→Taupunkt) **+ Simulator-Feed** für den Rest, hinter *einer* einheitlichen Ingest-Schnittstelle. So läuft die Demo zuverlässig und echte Sensoren können später 1:1 die Simulation ersetzen.

---

## 6. Offene Stack-Entscheidungen (nächster Schritt — pro Schicht begründen)

Noch **nicht** festgelegt (vgl. `Usecase-quick.md` §3.4, AE-01):

- **Sensorik:** MCU (ESP32 vs. RPi) · konkrete Sensormodelle · echt vs. simuliert je Messgröße.
- **Übertragung:** HTTP vs. MQTT (Protokoll-Entscheidung).
- **Backend:** Sprache/Framework (Team-Kompetenz entscheidend).
- **DB:** SQLite vs. Postgres vs. Timescale.
- **Frontend:** Framework vs. plain.
- **Betrieb:** lokal vs. Cloud + Fernzugriff (AE-01/AE-02).

> Jede dieser Entscheidungen gehört mit Alternativen + Begründung ins **Entscheidungslogbuch** (Bewertungskriterium „Nachvollziehbarkeit").

---

## 7. Offene Punkte

- Datenmodell-Kernschema (T0) gemeinsam definieren und **früh einfrieren** — die Naht zwischen allen drei Gruppen.
- Eisindikator: Proxy-Logik vs. echter Sensor vs. Simulation entscheiden (hängt an Budget K3 und Messgüte K4).
- Konfliktpunkte aus `Usecase-quick.md` §4 (K1–K9) bei der Detailauslegung beachten — v. a. K1 (Fehlalarm↔Auslassung) als Kern der Bewertungslogik.
