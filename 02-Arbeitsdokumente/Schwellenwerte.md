# Schwellenwerte & Entscheidungskategorien

> Konkrete, projektspezifische **Schwellenwerte** für die Vereisungsbewertung sowie Mess-/Betriebs-
> parameter je **funktionaler (FA)** und **nicht-funktionaler (NFA)** Anforderung.
> Zweck: **Kalibrier-/Konfigurationsvorgabe** für die Sensorik (Gruppe 1) und die Bewertungslogik
> (Gruppe 2). Alle Werte sind **Startwerte und parametrierbar (NF-05)** — am Testdatensatz (v. a. den
> zwei dokumentierten Vorfällen) nachzujustieren und im Entscheidungslogbuch zu begründen.

## 0. Leitprinzip (aus den zwei dokumentierten Vorfällen)

1. **Oberflächentemperatur entscheidet, nicht Lufttemperatur.** Vorfall 2: Luft +1,2 °C, trotzdem Eis,
   weil die *Oberfläche* < 0 °C war (nächtliche Abstrahlung). → Bewertung primär über **T_s**.
2. **Vereisung braucht Kälte UND Feuchte.** Vorfall 1: −2,1 °C Luft, aber **kein** Eis (trockene
   Oberfläche) → reine Temperatur löste einen **Fehlalarm** aus. → Kälte allein alarmiert nicht.
3. **Sicherheits-Bias:** **keine verpasste Vereisung** (FN-Ziel 0 %) hat Vorrang vor Fehlalarmen
   (FP-Ziel < 1 %) — „lieber zehn Fehlalarme als ein vereistes Flugzeug". Schwellen daher konservativ.

## 1. Eingangsgrößen der Bewertung

| Symbol | Größe | Quelle | Einheit |
|---|---|---|---|
| **T_s** | Oberflächentemperatur | Sensor (primär) | °C |
| T_a | Lufttemperatur | Sensor (Kontext) | °C |
| RH | relative Luftfeuchte | Sensor | % |
| **T_d** | Taupunkt | **berechnet** (Magnus aus T_a, RH) | °C |
| **ΔT** | Taupunkt-Abstand = T_s − T_d | berechnet | K |
| Niederschlag | vorhanden? + Art (Regen/gefrierend/Schnee/Graupel) | Sensor / Sim | — |
| p | Luftdruck (Tendenz) | Sensor | hPa |

> Taupunkt T_d = Magnus-Formel (a=17,62; b=243,12 °C). ΔT ≤ 0 ⇒ Oberfläche unter Taupunkt ⇒ Kondensation/Reif.

## 2. Entscheidungskategorien Vereisungsrisiko — **die Kernlogik**

| Stufe | Bedingung (Startwerte, parametrierbar) | Bedeutung | Aktion |
|---|---|---|---|
| 🟢 **GRÜN** | `T_s > +1,0 °C` | kein Vereisungsrisiko | nur Anzeige |
| 🟡 **GELB** | `T_s ≤ +1,0 °C` **und** *keine* Feuchte¹ — **ODER** Prognose: `T_s ≤ 0 °C` in ≤ 30 min | kalte/grenzwertige, aber trockene Oberfläche → beobachten / Vorwarnung | Vorwarnung anzeigen |
| 🟠 **ORANGE** | `T_s ≤ 0,0 °C` **und** Feuchte vorhanden¹ | Vereisung **wahrscheinlich** | Warnung (optisch **+** akustisch) |
| 🔴 **ROT** | `T_s ≤ 0,0 °C` **und** (gefrierender Niederschlag **oder** `ΔT ≤ 0 °C`) | **aktive Eisbildung / Glatteis** | Alarm höchster Prio, **Quittierung erforderlich** |

¹ **„Feuchte vorhanden"** := `RH ≥ 90 %` **oder** `ΔT (T_s − T_d) ≤ 1,0 °C` **oder** Niederschlag detektiert.

**Entprellung/Hysterese (ISA-18.2, gegen Chattering):** Hochstufung nach `On-Delay ≥ 60 s` Bedingung erfüllt.
Rückstufung erst, wenn die untere Schwelle um `0,5 °C` **unterschritten** ist **und** für `≥ 5 min` stabil.

> **Beide Vorfälle korrekt aufgelöst:**
> - Vorfall 1 (−2,1 °C, **trocken**): `T_s ≤ 0`, aber keine Feuchte → **GELB** (kein Alarm) → Fehlalarm vermieden.
> - Vorfall 2 (+1,2 °C Luft, **Oberfläche < 0 °C**, Reif): über `T_s` erfasst → **ORANGE/ROT** → Vereisung erkannt.

## 3. Kalibriervorgabe Sensorik (Mess-Schwellen je Größe)

| Größe | Messbereich | Genauigkeit (**Kalibrierziel**) | Auflösung | Intervall | Hinweis / Platzierung |
|---|---|---|---|---|---|
| **Oberflächentemp T_s** | −40 … +60 °C | **±0,3 °C** (kritisch um 0 °C → **Eispunkt-Kalibrierung**) | 0,1 °C | ≤ 60 s | bündig an repräsentativer Fahrbahn-/Taxiway-Stelle; robust gegen Räumfahrzeuge |
| Lufttemp T_a | −40 … +60 °C | ±1,0 °C | 0,1 °C | ≤ 60 s | strahlungsgeschützt (Radiation Shield) |
| Rel. Feuchte RH | 0 … 100 % | ±3 % RH | 0,1 % | ≤ 60 s | Kombisensor (SHT31/BME280) |
| Taupunkt T_d | (berechnet) | aus T_a + RH (Magnus) | 0,1 °C | — | kein eigener Sensor |
| Luftdruck p | 300 … 1100 hPa | Tendenz ±0,12 hPa | 0,1 hPa | ≤ 60 s | nur Prognose (Tendenz), nicht QNH |
| Niederschlag/-art | ja/nein + Typ | zuverlässige Detektion | — | ≤ 60 s | Present-Weather-/Regendetektor; im Prototyp ggf. simuliert |

**Datenstatus-Schwellen (FA „veraltete Daten erkennen" / „defekte Sensoren erkennen"):**
- **Veraltet (stale):** letzter Messwert älter als `3 × Intervall` (> 180 s bei 60 s) → Status „veraltet";
  Risiko **nicht** auf GRÜN herabstufen (fail-safe → mindestens GELB / „unbekannt").
- **Sensor defekt**, wenn: Wert außerhalb Messbereich · **Flatline** (keine Änderung > 15 min trotz erwartetem
  Rauschen) · unplausibler **Sprung > 5 °C/min** · NaN/Timeout. → Sensor markieren → Redundanz nutzen oder sicheren Zustand.

## 4. Schwellenwerte/Parameter je **funktionaler Anforderung**

| Funktionale Anforderung | Schwellwert / Parameter (Startwert) |
|---|---|
| Temperatur | Entscheidungsgrenze **T_s = 0 °C**; T_s/T_a-Bereiche s. §3 |
| Feuchtigkeit | `RH ≥ 90 %` = „feucht"; Genauigkeit ±3 % |
| Niederschlag | Detektion ja/nein; jede Detektion hebt Stufe an |
| Taupunkt | Magnus(T_a, RH); `ΔT ≤ 1 °C` = feucht, `ΔT ≤ 0 °C` = Kondensation/Reif |
| Alarmierung | Auslösung ab **ORANGE**; optisch **+** akustisch; ROT = höchste Prio + Quittierungspflicht |
| Risikobewertung Vereisung | 4-Stufen-Logik §2 |
| Luftdruck | Drucktendenz `< −1 hPa / 3 h` ⇒ Wetterverschlechterung → Prognose-Input |
| Niederschlagsart | **gefrierend → ROT**; Schnee/Regen bei `T_s ≤ 0` → ORANGE |
| Schnittstellen | REST-API; Push-Intervall ≤ 60 s; Datenmodell s. API-Spezifikation |
| Datenspeicherung | Messwerte + Bewertungen + Alarme + Quittierungen; Aufbewahrung ≥ Projektdauer; append-only |
| Vorhersage + Analyse + Wettervorhersage + veraltete Daten | 30-min-Trend (Extrapolation T_s, T_d, Drucktendenz); externe Wettervorhersage als Zusatzeingang; stale > 180 s |
| Defekte Sensoren erkennen | Kriterien s. §3 (Bereich / Flatline / Sprung / Timeout) |
| 30-min-Vorlaufzeit | Prognosehorizont **30 min**; GELB-Vorwarnung, wenn progn. `T_s ≤ 0 °C` in ≤ 30 min |
| Fernwartung | nur **authentifiziert + verschlüsselt** (NF-07); Lese- + Konfigzugriff |
| Logging | jede Messung/Bewertung/Alarm/Quittierung mit Zeitstempel (NF-09) |
| Parametrierbarkeit/Konfigurierbarkeit | **alle** Schwellen zur Laufzeit konfigurierbar (Config/UI), **ohne Recompile** |

## 5. Zielwerte je **nicht-funktionaler Anforderung**

| NFA | Zielwert (Startwert) | Hinweis / Realitäts-Check |
|---|---|---|
| Realitätsnah – Lufttemp-Abweichung | < 1,0 °C | aber **T_s ±0,3 °C** nötig, da Entscheidungsgrenze bei 0 °C liegt |
| Realitätsnah – Latenz | so gering wie möglich; Ziel **< 5 s** Sensor→Anzeige | im Test messen |
| Realitätsnah – Feuchte / Druck / Taupunkt | RH ±3 % · Druck-Tendenz ±0,12 hPa · T_d berechnet | |
| Zuverlässigkeit – **verpasste Vereisung (FN)** | **0 % (Designziel)** | nicht hart garantierbar → konservative Schwellen, Sicherheits-Bias |
| Zuverlässigkeit – **Fehlalarm (FP)** | **< 1 %** | nachrangig ggü. FN (K1) |
| Wartbarkeit – Sensortausch | **< 10 min** | steckbar, ohne Recompile |
| Wartbarkeit – Defekt-Erkennung | ≤ 1 Messintervall (≤ 60 s) | s. §3 |
| Wartbarkeit – Platzierung | Taxiway / repräsentative, etwas abgelegene Stelle unter gleichen Bedingungen | robust gegen Fahrzeuge |
| Wirtschaftlichkeit | Budget einhalten; laufende Kosten gering | Stückkosten je Node dokumentieren |
| Dokumentation | 100 % der Entscheidungen begründet | Entscheidungslogbuch |
| Bedienbarkeit/Usability | Alarm auf **≥ 2 Sinnen** (optisch + akustisch) | |
| Hohe Verfügbarkeit der Messungen | Ziel **100 %** + **redundante Datenquelle** | 100 % real nicht beweisbar (NF-03) → echtes Kriterium: Redundanz + **kein stiller Ausfall** |
| Sicherheit | **Mensch = letzte Instanz** (RB-01); 0 automatische Freigaben | |
| Ausfallsicherheit | lokaler Puffer ≥ 30 min; Fallback auf Redundanz; sicherer Zustand bei Ausfall | |

## 6. Parametrierbarkeit & Tuning (NF-05 / K1)

- Alle Schwellen in §2–§5 sind **Startwerte** in einer Config (kein Hardcode), zur Laufzeit änderbar.
- **Betriebspunkt** (FN ↔ FP, Zielkonflikt K1) bewusst wählen: niedrigere Schwellen ⇒ weniger verpasste
  Vereisung, mehr Fehlalarme. Default = **sicherheitsbetont** (FN minimieren).
- **Validierung:** Schwellen gegen die zwei dokumentierten Vorfälle (−2,1 °C / +1,2 °C) **und** einen
  simulierten Datensatz prüfen; jede Anpassung im Entscheidungslogbuch begründen.

---

> **Übergabe an Sensorik (Gruppe 1):** §3 ist die Kalibriervorgabe — entscheidend ist die
> **Oberflächentemperatur mit ±0,3 °C um 0 °C** (Eispunkt-Kalibrierung) sowie die Platzierung an einer
> repräsentativen, fahrzeug-robusten Stelle. Feuchte/Druck liefert idealerweise **ein** Kombisensor (BME280/SHT31).
