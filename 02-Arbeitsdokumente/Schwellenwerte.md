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
| RH | relative **Luft**feuchte (Kontext + Input für T_d; **keine** direkte Entscheidungsgröße) | Sensor | % |
| **T_d** | Taupunkt | **berechnet** (Magnus aus T_a, RH) | °C |
| **ΔT** | Taupunkt-Abstand = T_s − T_d | berechnet | K |
| p | Luftdruck (Tendenz) | Sensor | hPa |

> Taupunkt T_d = Magnus-Formel (a=17,62; b=243,12 °C). ΔT ≤ 0 ⇒ Oberfläche unter Taupunkt ⇒ Kondensation/Reif.

## 2. Entscheidungskategorien Vereisungsrisiko — **die Kernlogik**

**Auswertung als priorisierte Kaskade (NF-01 Fail-safe):** Die Stufen werden **von der gefährlichsten
abwärts** geprüft — die **erste zutreffende gewinnt** (ROT → ORANGE → GELB → GRÜN). **GELB ist der Auffang**
für jede Oberfläche, die nicht GRÜN, aber auch noch nicht ORANGE/ROT ist; dadurch bleibt **kein
Wertebereich unklassifiziert** und es wird im Zweifel **nie GRÜN** ausgegeben.

| Prio | Stufe | Bedingung (Startwerte, parametrierbar) | Bedeutung | Aktion |
|---|---|---|---|---|
| 1 | 🔴 **ROT** | `T_s ≤ 0,0 °C` **und** `ΔT ≤ 0 °C` | **aktive Eisbildung / Glatteis** (Oberfläche unter Taupunkt → Reif/Glatteis) | Alarm höchster Prio, **Quittierung erforderlich** |
| 2 | 🟠 **ORANGE** | `T_s ≤ 0,0 °C` **und** Feuchte vorhanden¹ | Vereisung **wahrscheinlich** | Warnung (optisch **+** akustisch) |
| 3 | 🟡 **GELB** | `T_s ≤ +1,0 °C` (Auffang: kalt/grenzwertig, nicht schon ORANGE/ROT) — **oder** Prognose: `T_s ≤ 0 °C` in ≤ 30 min | kalte/grenzwertige Oberfläche (feucht *oder* trocken) → beobachten / Vorwarnung | Vorwarnung anzeigen |
| 4 | 🟢 **GRÜN** | `T_s > +1,0 °C` **und** keine GELB-Prognose | kein Vereisungsrisiko | nur Anzeige |

> **Auswertungsreihenfolge = Implementierungsvorgabe (DTB-38) — genau so kodieren:**
> ```text
> if   T_s ≤ 0,0  und  ΔT ≤ 0,0:       risk = ROT
> elif T_s ≤ 0,0  und  ΔT ≤ 1,0:       risk = ORANGE     # „Feuchte vorhanden"¹
> elif T_s ≤ +1,0  oder  prog_T_s ≤ 0: risk = GELB        # Auffang + 30-min-Vorwarnung
> else:                                risk = GRÜN
> ```
> Die Stufen **überlappen bewusst** (jeder ROT-Fall erfüllt auch ORANGE); die **Reihenfolge** — nicht
> sich gegenseitig ausschließende Bedingungen — stellt sicher, dass die höchste zutreffende Stufe gewinnt.
> Das schließt zugleich die Lücke `0 °C < T_s ≤ +1,0 °C` **mit** Feuchte (fällt jetzt sauber auf GELB).

¹ **„Feuchte vorhanden"** := `ΔT (T_s − T_d) ≤ 1,0 °C` (Oberfläche nahe/unter Taupunkt). **Luft-`RH` allein
triggert keine Feuchte** — sie sagt nichts über die *Oberfläche* (Vorfall 1: 92 % Luftfeuchte bei trockener
Oberfläche → kein Eis); `T_a`/`RH` fließen nur über den Taupunkt `T_d` in `ΔT` ein. *(Luft-RH-Schwelle entfernt → E-33.)*

**Feuchte nicht bestimmbar (Fail-safe, NF-01):** Lässt sich `ΔT` nicht berechnen (z. B. `RH`/`T_a` defekt →
`T_d` fehlt), gilt **„Feuchte vorhanden" = wahr** (konservativ): bei `T_s ≤ 0,0 °C` ⇒ mindestens **ORANGE**,
sonst **GELB** — **nie GRÜN**. Fehlt `T_s` selbst, greift der sichere Zustand aus §3 (stale/defekt → ≥ GELB).

**Entprellung/Hysterese (ISA-18.2, gegen Chattering):** Hochstufung nach `On-Delay ≥ 60 s` Bedingung erfüllt.
Rückstufung erst, wenn die untere Schwelle um `0,5 °C` **unterschritten** ist **und** für `≥ 5 min` stabil.

> **Beide Vorfälle korrekt aufgelöst:**
> - Vorfall 1 (−2,1 °C Luft, 92 % **Luft**feuchte, **trockene Oberfläche**): `T_s ≤ 0`, aber `ΔT > 1,0`
>   (Oberfläche weit über Taupunkt) → **keine** Oberflächenfeuchte → **GELB** → Fehlalarm vermieden.
>   *(Luft-RH 92 % triggert bewusst NICHT — der frühere `RH ≥ 90 %`-Term hätte hier fälschlich ORANGE erzeugt; entfernt → E-33.)*
> - Vorfall 2 (+1,2 °C Luft, **Oberfläche < 0 °C**, Reif): über `T_s` erfasst → **ORANGE/ROT** → Vereisung erkannt.

## 3. Kalibriervorgabe Sensorik (Mess-Schwellen je Größe)

| Größe | Messbereich | Genauigkeit (**Kalibrierziel**) | Auflösung | Intervall | Hinweis / Platzierung |
|---|---|---|---|---|---|
| **Oberflächentemp T_s** | −40 … +60 °C | **±0,3 °C** (kritisch um 0 °C → **Eispunkt-Kalibrierung**) | 0,1 °C | ≤ 60 s | bündig an repräsentativer Fahrbahn-/Taxiway-Stelle; robust gegen Räumfahrzeuge |
| Lufttemp T_a | −40 … +60 °C | ±1,0 °C | 0,1 °C | ≤ 60 s | strahlungsgeschützt (Radiation Shield) |
| Rel. Feuchte RH | 0 … 100 % | ±3 % RH | 0,1 % | ≤ 60 s | Kombisensor (SHT31/BME280) |
| Taupunkt T_d | (berechnet) | aus T_a + RH (Magnus) | 0,1 °C | — | kein eigener Sensor |
| Luftdruck p | 300 … 1100 hPa | Tendenz ±0,12 hPa | 0,1 hPa | ≤ 60 s | nur Prognose (Tendenz), nicht QNH |

**Datenstatus-Schwellen (FA „veraltete Daten erkennen" / „defekte Sensoren erkennen"):**
- **Veraltet (stale):** letzter Messwert älter als der **Stale-Timeout `120 s`** (NF-02 final/Contract; parametrierbar in `config/`) → Status „veraltet";
  Risiko **nicht** auf GRÜN herabstufen (fail-safe → mindestens GELB / „unbekannt").
- **Sensor defekt**, wenn: Wert außerhalb Messbereich · **Flatline** (keine Änderung > 15 min trotz erwartetem
  Rauschen) · unplausibler **Sprung > 5 °C/min** · NaN/Timeout. → Sensor markieren → Redundanz nutzen oder sicheren Zustand.

## 4. Schwellenwerte/Parameter je **funktionaler Anforderung**

| Funktionale Anforderung | Schwellwert / Parameter (Startwert) |
|---|---|
| Temperatur | Entscheidungsgrenze **T_s = 0 °C**; T_s/T_a-Bereiche s. §3 |
| Feuchtigkeit | Entscheidung über **Oberflächennähe zum Taupunkt** (`ΔT ≤ 1,0 °C`); Luft-`RH` nur T_d-Input (Genauigkeit ±3 %) |
| Taupunkt | Magnus(T_a, RH); `ΔT ≤ 1 °C` = feucht, `ΔT ≤ 0 °C` = Kondensation/Reif |
| Alarmierung | Auslösung ab **ORANGE**; optisch **+** akustisch; ROT = höchste Prio + Quittierungspflicht |
| Risikobewertung Vereisung | 4-Stufen-Logik §2 |
| Luftdruck | Drucktendenz `< −1 hPa / 3 h` ⇒ Wetterverschlechterung → Prognose-Input |
| Schnittstellen | REST-API (**Pull**: G2 pollt G1s `GET /current` ≤ 60 s, Intervall selbst bestimmt); Datenmodell s. API-Spezifikation |
| Datenspeicherung | Messwerte + Bewertungen + Alarme + Quittierungen; Aufbewahrung ≥ Projektdauer; append-only |
| Vorhersage + Analyse + Wettervorhersage + veraltete Daten | 30-min-Trend (Extrapolation T_s, T_d, Drucktendenz); externe Wettervorhersage als Zusatzeingang; stale > 120 s |
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
