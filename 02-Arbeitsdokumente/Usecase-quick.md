# Usecase-Quick: Vereisungserkennung am Flughafen ANR

Abgeleitet aus `Die Hintergrundgeschichte.txt` und `Studierenden-Handreichung.txt`.

---

## 1. Problemstellung

### Ausgangssituation
PROBLEM: Erkennung von Vereisungen auf Startbahn unzureichend.
Der fiktive **Flughafen ANR (Airport North Regional)** liegt in einer Mittelgebirgsregion. In den Wintermonaten treten regelmäßig problematische Wetterbedingungen auf:

- Nebel
- gefrierender Regen
- Schneefall
- starke Temperaturschwankungen

Das aktuelle System zur Vereisungsüberwachung ist unzureichend. Es misst im Wesentlichen **nur Lufttemperatur und Luftfeuchtigkeit** und liefert damit keine verlässliche Grundlage für Betriebsentscheidungen.

### Dokumentierte Probleme

| Vorfall | Ursache | Folge |
|---|---|---|
| **Fehlalarm** (17. Jan., 04:42 Uhr) | Lufttemperatur −2,1 °C, Luftfeuchte 92 % → vorsorgliche Sperrung | 87 Minuten gesperrt, 11 verspätete Flüge, Kosten, Airline-Beschwerden |
| **Nicht erkannte Eisbildung** (03. Feb., 06:18 Uhr) | Lufttemperatur +1,2 °C → keine Warnung | Dünne Eisschicht, vereiste Randbereiche, Startverzögerung 40 Minuten |

Der externe Gutachter weist darauf hin, dass die **Lufttemperatur nicht das entscheidende Kriterium** ist — relevant wäre die **Oberflächentemperatur**. Zudem fehlen weitere Messgrößen:

- Oberflächenfeuchte
- Taupunkt
- Niederschlagsart

### Zentrale Zielkonflikte

- **Sicherheit vs. Verfügbarkeit:** Sicherheitsabteilung akzeptiert Fehlalarme („Lieber zehn Fehlalarme als ein vereistes Flugzeug"), Betriebsleitung will keine unnötigen Sperrungen.
- **Datenqualität vs. Kosten:** Winterdienst/Berater fordern bessere Sensoren, Controlling lehnt hohe Ausgaben ab (z. B. 4.800 € pro Sensor der Serie WX-500).
- **Ist-Zustand vs. Vorhersage:** Fluglotsen benötigen mindestens 30 Minuten Vorlaufzeit, nicht nur aktuelle Werte.
- **Lokal vs. Cloud:** IT tendiert zu lokalem Betrieb, sieht aber Fernzugriff als praktisch an.

### Harte Randbedingungen

- **Keine automatische Freigabe:** Die Startbahn darf niemals automatisch freigegeben werden; die Verantwortung bleibt beim Menschen.
- **Wartbarkeit:** Sensoren auf dem Vorfeld werden durch Räum-/Streufahrzeuge und Flugbetrieb regelmäßig beschädigt.
- **Risiken:** Falsche Sensordaten, Kommunikationsausfall, Stromausfall, nicht erkannte Vereisung, zu viele Fehlalarme.

---

## 2. Usecase

### Ziel
Entwicklung eines **prototypischen Systems zur Erfassung und Bewertung von Vereisungsbedingungen** auf der Startbahn des Flughafens ANR. Das System soll Entscheidungsträgern eine belastbare, nachvollziehbare Grundlage liefern, wann eine manuelle Kontrolle oder Sperrung der Bahn angezeigt ist.

### Hauptakteure

| Akteur | Interaktion mit dem System |
|---|---|
| **Winterdienst** | Primärnutzer; erhält Alarme/Meldungen, führt manuelle Kontrollen durch |
| **Fluglotsen** | Benötigen Vorhersage ≥ 30 Minuten vor kritischem Zeitpunkt |
| **Betriebsleitung / Geschäftsführung** | Entscheider über Bahnfreigabe/Sperrung, brauchen belastbare Zahlen |
| **IT-Abteilung** | Betreibt und wartet das System |
| **Sicherheitsbeauftragte** | Vorgibt harte Sicherheitsregeln, prüft Compliance |

### Kernfunktionen

1. **Sensordatenerfassung** — Messung von Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Niederschlagsart, Eisindikator.
2. **Datenverarbeitung** — Plausibilisierung, Speicherung, Trendbildung.
3. **Vereisungsbewertung** — Algorithmus zur Risikobewertung, parametrierbar zwischen Fehlalarm- und Auslassungsrisiko.
4. **Backend-System** — API und Datenmodell als Schnittstelle zwischen Sensorik und Frontend.
5. **Visualisierung / Frontend** — Darstellung aktueller und prognostizierter Vereisungsbedingungen.
6. **Alarmierung** — Benachrichtigung relevanter Akteure bei kritischen Zuständen.

### Out-of-Scope / Einschränkungen

- Das System **entscheidet nicht selbst** über Freigabe oder Sperrung.
- Es ist ein **Prototyp** innerhalb eines 3-wöchigen Projektkurses; vollständige Zulassung/Produktivbetrieb ist nicht Ziel.

### Erwartete Deliverables

- Funktionierender Prototyp mit Sensor-, Backend- und Frontend-Komponenten
- Versioniertes Lastenheft
- Architekturdiagramm
- API-Beschreibung
- Sensordatenanalyse
- Entscheidungslogbuch
- Reflexion über Wasserfall vs. Scrum im hybriden Projektverlauf

---

## 3. Funktionale und nicht-funktionale Anforderungen

> Abgeleitet aus Lastenheft-Entwurf, Vorfällen, Zielkonflikten und Stakeholder-Aussagen.
> **Prio:** Muss / Soll / Kann · **Status:** bestätigt (im Material belegt) / Annahme (abgeleitet) / offen (Quelle unentschieden oder Zielwert fehlt).

### 3.1 Funktionale Anforderungen (FA)

| ID | Anforderung | Prio | Status | Quelle / Begründung |
|---|---|---|---|---|
| **FA-01** | Erfasst **Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Niederschlagsart, Eisindikator** als primäre Messgrößen. | Muss | bestätigt | Tech. Notiz (Z. 79–84), Sensorhersteller (Z. 152–156); Lufttemperatur allein reicht nicht (Gutachter, Z. 46–48). |
| **FA-02** | Erfasst ergänzend **Lufttemperatur und Luftfeuchtigkeit** (Bestandsdaten, Vergleichbarkeit). | Soll | bestätigt | Wetterstation (Z. 14–16, 35–37). |
| **FA-03** | Speichert alle Messwerte persistent **mit Zeitstempel**. | Muss | bestätigt | Handreichung Z. 42 „Speicherung". |
| **FA-04** | Prüft Sensordaten auf **Plausibilität**, markiert Ausreißer/fehlende Werte **und erkennt veraltete Daten (Stale-Detection)** — zeigt keine alten Werte als aktuell. | Muss | bestätigt | R1 (Z. 123–124), R2 Kommunikationsausfall (Z. 125–126). |
| **FA-05** | Bewertet das **Vereisungsrisiko** aus den Daten; Bewertung ist **nachvollziehbar** (auslösende Messgröße/Schwelle erkennbar). | Muss | bestätigt | Anf. 2 (Z. 169–170); Reviewer „Was bedeutet erkennen?" (Z. 173–174) → Kriterium noch zu präzisieren. |
| **FA-06** | Liefert **Prognose mit ≥ 30 min Vorlaufzeit**. | Muss | bestätigt | Fluglotsen (Z. 95, 99). |
| **FA-07** | Visualisiert aktuelle + prognostizierte Bedingungen **inkl. Sensor-/Datenstatus**. | Muss | bestätigt | Anf. 3 (Z. 171–172). |
| **FA-08** | **Alarmiert** relevante Akteure bei kritischen Zuständen; Alarme **eindeutig mit Schweregrad**. | Muss | bestätigt | Zielkonflikt (Z. 27–30); Handreichung Z. 47 „Alarmierung". |
| **FA-09** | Stellt eine **API** als Schnittstelle Sensorik ↔ Backend ↔ Frontend bereit. | Muss | bestätigt | Handreichung Z. 41 „API". |
| **FA-10** | _(NEU)_ Mensch **quittiert Alarme**; die getroffene **manuelle Entscheidung** (Kontrolle/Sperrung) wird erfasst. | Muss | Annahme | Sicherheitsbeauftragte (Z. 163–165) + Entscheidungslogbuch (Z. 66). |
| **FA-11** | _(NEU)_ **Schwellwerte/Parameter** der Bewertungslogik sind im System konfigurierbar (Bedien-Gegenstück zu NF-05). | Soll | Annahme | Zielkonflikt Fehlalarm ↔ Sicherheit (Z. 27–30). |
| **FA-12** | _(NEU)_ Protokolliert Messwerte, Bewertungen, Alarme und Quittierungen (**Audit-Trail**). | Muss | Annahme | Entscheidungslogbuch (Z. 66); Haftung/Sicherheit. |

### 3.2 Nicht-funktionale Anforderungen (NFA)

| ID | Anforderung | Prio | Status | Quelle / Begründung |
|---|---|---|---|---|
| **NF-01** | **Ausfallrobustheit:** erkennt und behandelt Kommunikations-/Stromausfall (Warnung + definierter sicherer Zustand, kein stiller Ausfall). _Akzeptanzkriterium: TBD._ | Muss | bestätigt | R2/R3 (Z. 125–128). |
| **NF-02** | _(NEU)_ **Datenaktualität/Latenz:** Messintervall und max. Datenlatenz definiert und mit der 30-min-Prognose kompatibel. _Zielwert: TBD._ | Muss | offen | abgeleitet aus FA-06. |
| **NF-03** | _(NEU)_ **Verfügbarkeit:** hohe Verfügbarkeit im 24/7-Winter-/Nachtbetrieb. _Zielwert: TBD._ | Soll | offen | Vorfälle 04:42 / 06:18 (Z. 13, 34). |
| **NF-04** | **Genauigkeit/Belastbarkeit:** verlässlich für operative Entscheidungen; Validierung gegen Referenzmessung. _Zielwerte (Sensorgenauigkeit, FP-/FN-Rate): TBD._ | Muss | offen | GF „belastbare Zahlen" (Z. 72–73); AGENTS.md Teststrategie. |
| **NF-05** | **Parametrierbarkeit:** Schwellwerte zur Abwägung Fehlalarm vs. Auslassungsfehler konfigurierbar. | Muss | bestätigt | Zielkonflikt (Z. 27–30). |
| **NF-06** | **Wartbarkeit/Austauschbarkeit:** Sensoren/Komponenten leicht wartbar/ersetzbar (Vorfeld-Beschädigung). | Soll | bestätigt | Wartungstechniker (Z. 114–120). |
| **NF-07** | _(NEU)_ **Sicherheit/Zugriffsschutz:** Fernzugriff und Schwellwert-Konfiguration sind authentifiziert, autorisiert, verschlüsselt. | Muss¹ | Annahme | abgeleitet aus Fernzugriff (Z. 147–149) + Sicherheitskritikalität. |
| **NF-08** | _(NEU)_ **Usability:** Alarme/Anzeigen für Operatoren unter Zeitdruck eindeutig und schnell erfassbar. | Soll | Annahme | operativer Kontext (Winterdienst/Fluglotsen, Vorfälle). |
| **NF-09** | **Nachvollziehbarkeit/Log-Integrität:** Protokolle (FA-12) manipulationssicher und ausreichend lange verfügbar. | Muss | bestätigt | Entscheidungslogbuch (Z. 66). |
| **NF-10** | **Wirtschaftlichkeit:** im Budgetrahmen; Sensoranzahl/-kosten begründet. _Budget: TBD._ | Soll | offen | Controlling (Z. 68–69, 159–160). |
| **NF-11** | **Erweiterbarkeit:** mehrere Sensoren/Standorte unterstützbar. | Soll | bestätigt | „Vielleicht brauchen wir zehn" (Z. 77). |

¹ sobald Fernzugriff (AE-02) umgesetzt wird.

### 3.3 Harte Randbedingungen (RB)

| ID | Randbedingung | Quelle |
|---|---|---|
| **RB-01** | **Keine automatische Freigabe/Sperrung** der Startbahn — die Verantwortung bleibt immer beim Menschen. | Sicherheitsbeauftragte (Z. 163–165). |

> RB-01 ersetzt die bisherige Doppelung FA-10(alt)/NF-01(alt) — inhaltlich identisch, daher als *eine* harte Randbedingung geführt.

### 3.4 Offene Entscheidungen & Annahmen (AE)

Aus widersprüchlichem/unentschiedenem Material — **bewusst nicht** als feste Anforderung formuliert (vgl. Bewertungskriterium „Umgang mit widersprüchlichen Anforderungen"):

| ID | Offene Entscheidung | Stand im Material |
|---|---|---|
| **AE-01** | **Lokaler Betrieb vs. Cloud** | IT-Chat unentschieden (Z. 135–149): lokal bevorzugt, Cloud-Wartung als Vorteil genannt → **offen**. So auch in `AGENTS.md`, „Architekturentscheidungen (offen)". |
| **AE-02** | **Fernzugriff** | „wäre praktisch" (Z. 147–149) → Wunsch/Kann, kein Muss; Umfang offen. |

> Hinweis: NF-06(alt) „Lokaler Betrieb" und NF-07(alt) „Fernzugriff" waren als feste NFA formuliert, obwohl die Quelle ausdrücklich **unentschieden** ist — daher hierher verschoben.

### Konvention (kein System-Requirement)

- **Sprache Deutsch** für Doku/UI ist eine **Projektkonvention** (AGENTS.md Z. 183), keine szenario-abgeleitete Anforderung — daher separat, nicht als NFA (vorher NF-11 alt).

---

**Zusammenfassung:** Ein sicherheitskritisches Entscheidungs**unterstützungs**system, das aus widersprüchlichem, unvollständigem Material ein konsistentes Lastenheft + Prototyp ableitet. Punkte mit Status „offen"/„Annahme" sind bewusst markiert und gehören ins Entscheidungslogbuch.



## 4. Konflikte in und zwischen den Anforderungen

> §1 nennt die Zielkonflikte auf **Stakeholder-Ebene**. Dieser Abschnitt zeigt, wie sie sich als **Spannungen zwischen konkreten Anforderungen** niederschlagen — inkl. solcher *innerhalb* einer Anforderung. **intra** = Konflikt steckt in einer Anforderung selbst · **inter** = zwischen mehreren.

| ID | Beteiligte Anforderungen | Art | Spannung | Auflösungsrichtung |
|---|---|---|---|---|
| **K1** | FA-05 · NF-04 · NF-05 | intra/inter | Höhere Sensitivität senkt **Auslassungen** (Sicherheit ↑), erhöht aber **Fehlalarme** (Verfügbarkeit ↓) — beide nicht gleichzeitig minimierbar | NF-05 macht den Betriebspunkt parametrierbar; Schwelle bewusst wählen + im Entscheidungslogbuch begründen (steuert den Konflikt, löst ihn nicht) |
| **K2** | FA-06 ↔ NF-04 · FA-05 | inter | ≥ 30-min-**Prognose** ist prinzipiell ungenauer und schwerer **erklärbar** als die Ist-Messung | Prognose mit **Konfidenz/Unsicherheit** ausgeben; Nachvollziehbarkeit (FA-05) auch für die Prognose fordern |
| **K3** | FA-01 · NF-04 ↔ NF-10 | inter | Mehr/bessere Messgrößen & Sensoren (WX-500 ~4.800 €, „zehn") gegen **Budget** | Sensoranzahl/-auswahl per Kosten-Nutzen begründen; ggf. gestufter Ausbau |
| **K4** | FA-01 ↔ NF-06 | inter | Präzise **Oberflächensensoren** sind empfindlich und werden am Vorfeld **beschädigt** (Genauigkeit vs. Robustheit) | Robuste Bauform/Schutz, Redundanz, einfacher Tausch (NF-06) |
| **K5** | NF-01 ↔ NF-03 · FA-05 | intra/inter | „Definierter **sicherer Zustand**" bei Ausfall ist konservativ (Risiko annehmen/alarmieren) → senkt **Verfügbarkeit** / erhöht Fehlalarme | Sicheren Zustand explizit definieren (vermutlich „Risiko anzeigen + manuelle Kontrolle"), Verfügbarkeitsfolge akzeptieren |
| **K6** | FA-11 · AE-02 ↔ NF-07 | inter | **Konfigurierbarkeit** der Schwellwerte + **Fernzugriff** vergrößern die Angriffs-/Fehlbedienfläche vs. **Zugriffsschutz** | Rollenbasierte Rechte, Audit-Trail (FA-12), Fernzugriff nur abgesichert |
| **K7** | NF-02 ↔ NF-06 · NF-10 · AE-01 | inter | Häufige, **latenzarme** Daten (für FA-06 nötig) vs. **robuste/günstige** Sensorik & lokaler Betrieb | Messintervall an Prognosehorizont koppeln; NF-02-Zielwert festlegen |
| **K8** | FA-05 · FA-07 ↔ NF-08 | inter | **Detail/Nachvollziehbarkeit** (auslösende Messgröße, viel Status) vs. **Eindeutigkeit** unter Zeitdruck | Gestufte UI: Ampel/Status zuerst, Details on demand |
| **K9** | AE-01 ↔ AE-02 · NF-03 | inter (offen) | **Lokal** vs. **Fernzugriff** vs. **Verfügbarkeit** — lokaler Einzelbetrieb = Single Point of Failure | Offene Architekturentscheidung → Entscheidungslogbuch (vgl. §3.4) |

> **RB-01** (keine automatische Freigabe) ist *kein* Konflikt, sondern eine harte Grenze: Sie deckelt, wie stark FA-06/FA-08 den Menschen entlasten dürfen — der Nutzen von Prognose/Alarm hängt damit von der menschlichen Reaktionszeit ab (organisatorisch, nicht technisch lösbar).
>
> Kernspannung quer über alle: **Sicherheit ↔ Verfügbarkeit ↔ Kosten** — kein Optimum für alle drei gleichzeitig; jede Anforderung mit Status „offen"/TBD ist ein bewusst offen gehaltener Punkt dieses Dreiecks. 