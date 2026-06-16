# Randbedingungsmetriken

> Messbare Kennzahlen für die **nicht-funktionalen Anforderungen (NF-01…NF-11)** sowie die harte
> Randbedingung **RB-01** des Prototyps zur Vereisungserkennung am Flughafen ANR.
> IDs und Taxonomie folgen `Usecase-quick.md` (NFA vs. RB vs. AE).

## Lesehinweis (wichtig)

Jede Metrik hat **zwei Zielwerte**, weil Industrie-/Normwerte für einen 3-Wochen-Studienprototyp
mit günstiger/teils simulierter Sensorik (vgl. `Architektur-Stack-Konzept.md`) meist **nicht
verifizierbar** sind:

- **Referenzwert (Realbetrieb):** an Norm/Industrie orientierter Sollwert für ein Produktivsystem.
- **Prototyp-Abnahmekriterium (ANR, 3 Wo.):** was im Rahmen dieses Projekts tatsächlich **prüfbar**
  ist. `n/v` = im Prototyp **nicht verifizierbar**, nur als dokumentierte Zielgröße geführt.

Quellen-Status: ✅ belastbar · ⚠ **unverifiziert** (vor Übernahme ins Lastenheft prüfen).

---

## 1. Mapping-Übersicht (NFR → Metrik → Zielwerte)

| NFR-ID | Anforderung | Primärmetrik | Referenzwert (Realbetrieb) | Prototyp-Kriterium (3 Wo.) |
|---|---|---|---|---|
| **NF-01** | Ausfallrobustheit | Verhalten bei Komm./Strom-Ausfall; lokaler Puffer | kein stiller Ausfall; sicherer Zustand | Ausfall simuliert → Warnung + sicherer Zustand; Puffer ≥ 30 min ✔ prüfbar |
| **NF-02** | Datenaktualität/Latenz | Messintervall; End-to-End-Latenz | ≥ 1 Messung/min; Änderungserkennung ≤ 5 min | Intervall fix (z. B. 60 s); Latenz Sensor→Anzeige gemessen ✔ |
| **NF-03** | Verfügbarkeit | Uptime „Nines" | ≥ 99,9 % (max. 8,76 h/a) | n/v (Laufzeit zu kurz); Ersatz: stabiler Demo-Betrieb + Sensor-Fallback ✔ |
| **NF-04** | Genauigkeit/Belastbarkeit | Sensorabweichung vs. Referenz; FP/FN | Oberflächentemp ± 0,1 °C; RCAM-konforme Risikostufe | Abweichung dokumentiert (real ±0,2–0,5 °C); beide Vorfälle korrekt klassifiziert ✔ |
| **NF-05** | Parametrierbarkeit | Konfigurierbarkeit des Betriebspunkts | Schwellwerte ohne Codeänderung | Schwellen in Config/UI, Wirkung zur Laufzeit ✔ |
| **NF-06** | **Hardware**-Wartbarkeit | Tauschzeit Sensor; Steckbarkeit | Hot-Swap; MTTR < 4 h; Ersatzbestand | Sensor steckbar, Tausch < X min ohne Recompile ✔ |
| **NF-07** | Zugriffsschutz | Auth/Authz/TLS; unberechtigte Zugriffe | 0 unberechtigt; Rollenmodell; Verschlüsselung | **bedingt** — nur falls Fernzugriff (AE-02): Auth + TLS; sonst „lokal, kein Netzexposé" |
| **NF-08** | Usability | SUS; Aufgabenerfolg; Time-on-Task | SUS ≥ 80; Erfolg ≥ 90 % | SUS-Mini-Test (3–5 Personen) ≥ 68; Ampel ≤ X s erfassbar; Klicktiefe ≤ 3 ✔ |
| **NF-09** | Log-Integrität/Nachvollziehbarkeit | Audit-Abdeckung; Aufbewahrung | 100 % sicherheitsrel. Aktionen, manipulationssicher | append-only Log (Bewertung/Alarm/Quittierung) + Zeitstempel ✔ |
| **NF-10** | Wirtschaftlichkeit | Stückkosten; Budgettreue | ROI ≥ 0 / Payback ≤ 24 Mon. | ROI n/v; Ersatz: Stückkosten je Node + Budget dokumentiert, Sensorzahl begründet ✔ |
| **NF-11** | Erweiterbarkeit | unterstützte Sensoren/Standorte | mehrere Standorte | Datenmodell/API mit ≥ 2 Sensor-IDs (2 simul. Feeds) ✔ |
| **RB-01** | **Harte Randbedingung:** keine Auto-Freigabe | automatische Freigabe-Events | 0 (durch Architektur erzwungen) | 0; kein Aktor/Schreibpfad zur Freigabe; Ausgaben als „Entscheidungsunterstützung" + Quittierungspflicht ✔ |

> **Zusätzlicher Qualitäts-NFR (nicht im Briefing gefordert):** Software-Wartbarkeit — siehe §2.6b.
> Bewusst von NF-06 (Hardware) getrennt.

---

## 2. Detaillierte Metriken pro NFR

### 2.1 NF-04 — Genauigkeit / Realitätsnähe

| Aspekt | Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|---|
| Oberflächentemperatur | Abweichung vs. kalibrierte Referenz | ≤ ± 0,1 °C | ± 0,2–0,5 °C (T0-Sensorik: MLX90614/DS18B20 ±0,5 °C; PT100 kalibriert ±0,2 °C) **— Zielwert ±0,1 °C mit T0-HW nicht erreichbar (K4)** | ✅ Sensor-Datenblätter |
| Lufttemperatur/Taupunkt | Abweichung vs. Referenz | ≤ ± 1,0 °C | dokumentiert | ⚠ CAP 746 (genaue Tabelle prüfen) |
| Luftfeuchtigkeit (relativ) | Abweichung vs. Referenz | ≤ ± 3 % RH | ± 2–3 % RH erreichbar (SHT31 ±2 %, BME280 ±3 %, DHT22 bis ±5 %) ✔ — Kombisensor erfüllt Referenz; **geht direkt in die Taupunktberechnung ein** | ✅ WMO-CIMO (WMO-No. 8); Sensor-Datenblätter |
| Luftdruck (barometrisch) | Absolut- bzw. Tendenz-Abweichung | ≤ ± 0,3 hPa (Met-Beob.); Altimetrie ± 0,1 hPa | absolut ± 1 hPa, **Tendenz ± 0,12 hPa** (BME280/BMP280) ✔ — für Trend/Prognose ausreichend, nicht für QNH | ✅ WMO-CIMO; BME280-Datenblatt |
| Klassifikationsgüte | FP/FN gegen die 2 dokumentierten Vorfälle | — | **beide korrekt:** −2,1 °C → kein Eis, +1,2 °C → Eis ✔ | ✅ Hintergrundgeschichte |
| Risikostufe vs. RCAM | **Plausibilitätsabgleich** der Risikoeinstufung gegen RCAM-Logik (nicht offizielle RWYCC-Ausgabe) | qualitativ konsistent | stichprobenhafter Abgleich dokumentiert | ✅ ICAO Doc 9981 (RCAM) |

> **Scope-Hinweis:** Das System erzeugt **keine** offiziellen Runway Condition Codes (RWYCC), sondern
> Vereisungs-Risiko + Prognose als Entscheidungsunterstützung. RCAM dient als Validierungs**referenz**,
> nicht als Output-Format → daher „Plausibilitätsabgleich" statt „≥ 90 % RWYCC-Korrelation".

> **Rolle Feuchte & Druck:** Die **relative Feuchte** ist eine Kerngröße — sie bestimmt zusammen mit
> der Lufttemperatur den **Taupunkt** und damit die Vereisungslogik. Der **Luftdruck** ist *kein*
> direkter Vereisungstreiber; sein Nutzen liegt in der **Drucktendenz** (fallender Druck ⇒ aufziehende
> Front) als Eingang für die ≥ 30-min-**Prognose** (FA-06). Praktisch liefert ein **BME280**-Kombisensor
> Temperatur + Feuchte + Druck in einem Bauteil (vgl. Sensorwahl in `Architektur-Stack-Konzept.md`) —
> Druck ist damit faktisch „kostenlos" mitnehmbar.

### 2.2 NF-04/NF-05 — Zuverlässigkeit (wenig Fehlalarme)

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Chattering-Alarme | 0 | 0 — Deadband + On/Off-Delay implementiert ✔ | ✅ ISA-18.2 / EEMUA 191 |
| Alarmrate (steady state) | ≤ 1 Alarm / 10 min | gegen Testdatensatz geprüft ✔ | ✅ ISA-18.2 Tab. 7 |
| Prioritätsverteilung | 80 % Low / 15 % Med / 5 % High | konzeptionell umgesetzt | ✅ ISA-18.2 |
| False-/Missed-Alarm-Rate | FAR < 1 % / MAR < 0,1 % | an simul./aufgez. Daten gemessen; Betriebspunkt **parametrierbar (NF-05)** ✔ | ⚠ „exida-Benchmark" — Quelle präzisieren |

> Kern-Zielkonflikt **K1** (Fehlalarm ↔ Auslassung): über NF-05 bewusst parametrierbar, Betriebspunkt
> im Entscheidungslogbuch begründen.

### 2.3 NF-02 — Datenaktualität / Latenz

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Messfrequenz | ≥ 1 Messung/min | fixes Intervall (z. B. 60 s) ✔ | ⚠ CAP 746 (Abschnitt prüfen) |
| Latenz Sensor → Anzeige | so klein wie möglich | < X s gemessen (Zielwert im Test festlegen) ✔ | ✅ Projektableitung (FA-06) |
| Kompatibilität 30-min-Prognose | Intervall ≪ Prognosehorizont | erfüllt ✔ | ✅ Projektanforderung |

### 2.4 NF-03 — Verfügbarkeit

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Systemverfügbarkeit | ≥ 99,9 % (krit. Infrastruktur ≥ 99,99 %) | **n/v** (Laufzeit zu kurz) — als Zielgröße dokumentiert | ✅ ISO/IEC 25010 |
| Verhalten bei Sensorausfall | Datenlücke < 5 min via Redundanz/Fallback | Fallback/Warnung im Test nachgewiesen ✔ | ✅ ICAO GRF (zeitnahe Meldung) |
| Demo-Stabilität | — | stabiler Lauf über gesamte Demo-Dauer ✔ | ✅ Projektkriterium M3 |

### 2.5 NF-01 — Ausfallrobustheit & Ausfallsicherheit

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Sicherer Zustand bei Ausfall | kein stiller Ausfall | Komm./Strom-Ausfall simuliert → Warnung + „Risiko anzeigen + manuelle Kontrolle" ✔ | ✅ Projekt (R2/R3) |
| Lokaler Puffer (RPO) | ≤ 5 min Datenverlust | Puffer ≥ 30 min Messdaten ✔ | ✅ Projekt (30-min-Horizont) |
| MTBF / MTTR | MTBF ≥ 1.000 h; MTTR < 4 h | **MTBF n/v** (Zielgröße); MTTR-Konzept (Sensortausch) dokumentiert | ⚠ „Oxmaint"/MIL-HDBK-338B — als Orientierung, nicht als Beleg |
| RTO | < 30 min | Neustart/Recovery-Pfad demonstriert ✔ | ✅ ISO/IEC 25010 Recoverability |
| Redundanz | ≥ 2 unabh. Sensoren je Runway-Third | konzeptionell; optional 2. Sensor im Demo | ✅ ICAO GRF (Third-by-Third) |

### 2.6 NF-06 — Hardware-Wartbarkeit / Austauschbarkeit

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Sensortausch-Zeit (MTTR HW) | < 4 h (Best-in-Class) | Sensor steckbar, Tausch < X min ohne Recompile ✔ | ✅ ISO/IEC 25010 |
| Steckbarkeit/Hot-Swap | Hot-Swap-fähig | dokumentierter Tauschvorgang ✔ | ✅ Projekt (Vorfeld-Beschädigung) |
| Wetterfestigkeit | IP65+, −25 … +50 °C | Schutzgehäuse vorgesehen | ⚠ typ. Airport-Spec (Modell-Datenblatt prüfen) |

### 2.6b Software-Wartbarkeit (zusätzlicher Qualitäts-NFR — nicht im Briefing gefordert)

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Zyklomatische Komplexität (McCabe) | ≤ 10 / Funktion | ≤ 10 für die Entscheidungslogik ✔ | ✅ ISO/IEC 25010 |
| Testabdeckung | ≥ 80 % | **≥ 80 % nur für die Bewertungslogik** ✔ | ✅ Best Practice |
| Linter/Compiler | 0 Errors | 0 Errors, Warnungen dokumentiert ✔ | ✅ — |
| TIOBE TPM / TÜViT-Zertifizierung | ≥ 70 % (Level C) | **out of scope** (keine Zertifizierung im Studienprojekt) | ⚠ TIOBE TPM (Orientierung) |

### 2.7 NF-08 — Bedienbarkeit / Usability

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| System Usability Scale (SUS) | ≥ 80 (gut) | **≥ 68** im Mini-Test (3–5 Personen) ✔ | ✅ Brooke 1996; ISO 9241-11 |
| Aufgabenerfolg | ≥ 90 % | typische Aufgaben (Alarm quittieren, Status lesen) erfolgreich ✔ | ✅ ISO 9241-11 |
| Erfassbarkeit Ampel/Status | — | Risikostatus in ≤ X s erkennbar; Klicktiefe ≤ 3 ✔ | ✅ ISO 9241-11 |

> Bezug **K8**: gestufte UI (Ampel zuerst, Details on demand) für Eindeutigkeit unter Zeitdruck.

### 2.8 NF-09 — Nachvollziehbarkeit / Log-Integrität

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Audit-Abdeckung | 100 % sicherheitsrel. Aktionen | Bewertung/Alarm/Quittierung vollständig geloggt ✔ | ✅ ICAO GRF |
| Manipulationssicherheit | krypto-gesichert | append-only + Zeitstempel (keine Signatur nötig im Prototyp) ✔ | ✅ — |
| Aufbewahrung | regulatorisch | ≥ Projektdauer ✔ | ✅ Entscheidungslogbuch |

### 2.9 NF-07 — Sicherheit / Zugriffsschutz (bedingt)

| Metrik | Referenzwert | Prototyp-Kriterium | Quelle |
|---|---|---|---|
| Authentifizierung/Autorisierung | Rollenmodell (≥ 3 Rollen) | **nur bei Fernzugriff (AE-02):** min. Login + Rollen; sonst „lokal" dokumentiert | ✅ IEC 62443 / BSI |
| Transportverschlüsselung | TLS verpflichtend bei Fernzugriff | TLS falls Netz-Exposé ✔/bedingt | ✅ BSI-Grundschutz |
| Unberechtigte Zugriffe | 0 | 0 (lokaler Betrieb = kein Exposé) ✔ | ✅ ISO 27001 |

> Bezug **K6**: Konfigurierbarkeit (FA-11) + Fernzugriff (AE-02) vergrößern die Angriffsfläche →
> Rechte + Audit-Trail (NF-09).

### 2.10 RB-01 — Harte Randbedingung: keine automatische Freigabe

| Metrik | Zielwert | Prototyp-Verifikation | Quelle |
|---|---|---|---|
| Automatische Startbahn-Freigaben | **0 (hartes Verbot)** | Code-Review: System besitzt **keinen Aktor/Schreibpfad** zur Freigabe; Test bestätigt ✔ | ✅ Projekt; EASA/ICAO-Prinzip |
| Kennzeichnung der Ausgaben | jede Ausgabe = „Entscheidungsunterstützung" | UI-Review ✔ | ✅ Projekt |
| Quittierungspflicht | menschliche Quittierung erforderlich | Quittierungs-Flow vorhanden + geloggt ✔ | ✅ Projekt (FA-10/NF-09) |

> **Hinweis zu „SIL":** Eine formale Safety-Integrity-Level-Einstufung (IEC 61508) erfordert den
> vollständigen Sicherheitslebenszyklus und ist **nicht** Teil dieses Prototyps. SIL nur als
> **Denkrahmen** referenzieren; nicht als erreichten Level behaupten. (IEC 61508 low-demand:
> SIL 1 = PFDavg 10⁻²–10⁻¹, SIL 2 = 10⁻³–10⁻².)

---

## 3. Prototyp-Abnahmekriterien (die real prüfbare Teilmenge für M2/M3)

Checkliste dessen, was im Projektzeitraum **nachweisbar** ist — Grundlage fürs Testprotokoll:

- [ ] **RB-01:** 0 automatische Freigaben (Code-Review + Test), Ausgaben als Entscheidungsunterstützung gekennzeichnet, Quittierung vorhanden.
- [ ] **NF-04:** beide dokumentierten Vorfälle (−2,1 °C / +1,2 °C) korrekt klassifiziert; Sensorabweichung gegen Referenz protokolliert.
- [ ] **NF-01:** Ausfall simuliert → Warnung + sicherer Zustand; lokaler Puffer ≥ 30 min.
- [ ] **NF-02:** festes Messintervall + gemessene End-to-End-Latenz.
- [ ] **NF-05:** Schwellwerte ohne Codeänderung konfigurierbar, Wirkung zur Laufzeit.
- [ ] **NF-08:** SUS ≥ 68 im Mini-Test; Ampel schnell erfassbar, Klicktiefe ≤ 3.
- [ ] **NF-09:** append-only Audit-Log (Bewertung/Alarm/Quittierung) mit Zeitstempel.
- [ ] **NF-11:** Datenmodell/API mit ≥ 2 Sensor-Feeds nachgewiesen.
- [ ] **NF-06:** Sensor steckbar/tauschbar ohne Recompile.
- [ ] **Software-Qualität:** Bewertungslogik Coverage ≥ 80 %, McCabe ≤ 10, Linter 0 Errors.

**Nur als Zielgröße dokumentiert (im Prototyp n/v):** NF-03 Verfügbarkeit %, MTBF, ROI/Payback, ±0,1 °C, formale SIL-Einstufung, TÜViT-/TIOBE-Zertifizierung.

---

## 4. Referenzen

**✅ Belastbar**
1. **ICAO Doc 9981 / PANS-Aerodromes** — RCAM & Global Reporting Format (GRF).
2. **ANSI/ISA-18.2-2016 / IEC 62682** — Management of Alarm Systems (Chattering, Alarmrate, Priorisierung).
3. **ISO/IEC 25010:2011** — Software-Produktqualität (Maintainability, Reliability, Recoverability).
4. **ISO 9241-11:2018** — Usability (Effektivität/Effizienz/Zufriedenheit).
5. **Brooke, J. (1996)** — System Usability Scale (SUS).
6. **IEC 61508** — Funktionale Sicherheit (SIL **nur als Denkrahmen**, keine Einstufung im Prototyp).
7. **IEC 62443 / BSI-Grundschutz / ISO 27001** — Zugriffsschutz, Rollenmodell.

**⚠ Vor Übernahme ins Lastenheft verifizieren / abstufen**
8. **CAA CAP 746** — real, aber zitierte Tabellen-/Abschnittsnummern (Tab. 8, 7.82) sind ungeprüft.
9. **IEC 62304** — Medizingeräte-Software; hier **nur als Analogie** für Dokumentationsintensität, **kein** Aviatik-Standard.
10. **„Oxmaint 2026" / „Kern IT 2026" / „ICAO APAC WP 09 (2025), 0,01 mm"** — Quelle/Existenz unbestätigt (Vendor-Blog bzw. möglicher Zitierfehler); **nicht** als Norm verwenden.
11. **MIL-HDBK-338B / „exida-Benchmark"** — generische Zuverlässigkeits-/FAR-Orientierung; konkrete Werte projektspezifisch belegen.
