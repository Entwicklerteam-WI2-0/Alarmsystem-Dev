# Stakeholderanalyse — Vereisungserkennung Flughafen ANR

**Deliverable:** Meilenstein M1 (Ende Woche 1)
**Quelle:** `Die Hintergrundgeschichte.txt` (Zeilenbelege in Klammern); ergänzend `Handreichung für die Studis` (§2 „Ihre Rolle") für das Ingenieurteam
**Status:** v0.1 — Entwurf

> Methodik: Es wurden alle im Material genannten oder klar implizierten Interessenträger
> identifiziert, mit Beleg versehen, ihrer Rolle gegenüber dem System zugeordnet und auf
> Zielkonflikte untersucht. Zusätzlich sind latente (im Text fehlende, aber betroffene)
> Stakeholder als Blind-Spot-Befund dokumentiert.

## A) Im Text belegte Stakeholder

> **Stakeholder** = wer das System beeinflussen kann **oder** von ihm bzw. seinen Ergebnissen betroffen ist. Die Spalte „Warum Stakeholder" nennt für jede Partei genau diesen Bezug.

| # | Stakeholder | Warum Stakeholder (Begründung) | Interesse / Stake | Beleg (Zeile) | Rolle ggü. System |
|---|---|---|---|---|---|
| 1 | **Geschäftsführung** | Entscheidet über Budget und Projektfreigabe — ohne ihr Ja existiert das System nicht | Belastbare Zahlen, wirtschaftliche Rechtfertigung der Investition | 65, 72–73 | Entscheider / Budgetfreigabe |
| 2 | **Betriebsleitung** | Trägt die operativen Folgen jeder Sperrentscheidung und gibt die Verfügbarkeitsvorgabe vor | Maximale Bahnverfügbarkeit, keine unnötigen Sperrungen | 27–28 | Entscheider (operativ) |
| 3 | **Flughafenleitung** | Stößt das Projekt zur Behebung der Vorfälle an und fordert Verantwortungsklärung | Klärung von Verantwortung, Verhinderung von Wiederholungsfehlern | 50–52 | Auftraggeber / Aufsicht |
| 4 | **Sicherheitsabteilung / Sicherheitsbeauftragte** | Setzt nicht verhandelbare Sicherheitsvorgaben, die das Systemdesign hart begrenzen (Vetomacht) | Flugsicherheit über alles; keine automatische Bahnfreigabe, Verantwortung beim Menschen | 29–30, 163–165 | Governance / harte Vorgabe |
| 5 | **Winterdienst** | Arbeitet täglich mit den Ergebnissen und liefert die manuelle Gegenkontrolle — Hauptbetroffener im Betrieb | Verlässliche, *richtige* Daten; misstraut der Wetterstation; macht manuelle Kontrolle | 18, 38–43, 53–62, 70–77, 161–162 | Primärnutzer (operativ) |
| 6 | **IT-Abteilung** (Laura, Sebastian) | Betreibt und wartet das System; entscheidet über das Betriebsmodell (lokal/Cloud) | Betreibbarkeit/Wartung; lokal vs. Cloud; Fernzugriff; verteidigt aktuelle Sensoren | 44–45, 55–60, 133–149 | Betreiber / Wartung |
| 7 | **Controlling** | Kann die Lösung über das Budget begrenzen oder kippen (Kostenhoheit) | Kosten begrenzen („keine 100.000 €", „4.800 € sehr teuer") | 66, 68–69, 74–75, 159–160 | Geldgeber / Restriktion |
| 8 | **Fluglotsen** (Daniel, Sandra) | Endabnehmer der Vorhersage; treffen auf Basis der Ausgabe operative Entscheidungen | Direkter Datenzugang + Vorhersage ≥ 30 min, nicht nur Ist-Zustand | 85–99 | Primärnutzer / Endabnehmer |
| 9 | **Externer Gutachter** | Seine fachliche Bewertung prägt die Ursachendeutung und damit die Anforderungen | Fachliche Ursachenklärung: Oberflächentemperatur statt Lufttemperatur | 46–48 | Externe Fachexpertise |
| 10 | **Technischer Berater** | Bestimmt mit, welche Messgrößen überhaupt erfasst werden müssen | Fehlende Messgrößen benennen (Oberflächentemp./-feuchte, Taupunkt, Niederschlagsart) | 78–84 | Externe Fachexpertise |
| 11 | **Wartungstechniker** | Seine Praxiserfahrung definiert nicht-funktionale Anforderungen (Wartbarkeit, Robustheit) | Wartbarkeit/Robustheit der Vorfeld-Sensoren (Beschädigung durch Räum-/Streufahrzeuge) | 114–120 | Betrieb / Instandhaltung |
| 12 | **Sensorhersteller** | Liefert die Schlüsselkomponente; bestimmt Kosten, Verfügbarkeit und Messfähigkeit | Verkauf der Serie WX-500 (~4.800 €/Sensor) | 150–158 | Externer Lieferant |
| 13 | **Airlines** | Tragen die wirtschaftlichen Folgen von Fehlalarmen/Sperrungen; ihre Beschwerden treiben das Projekt | Pünktlichkeit; keine unnötigen Verspätungen (zwei Beschwerden) | 24, 26 | Extern Betroffene (Kunde) |
| 14 | **Reviewer (Lastenheft)** | Prüft und beeinflusst Präzision und Qualität der Anforderungen (Gatekeeper RE) | Präzision der Anforderungen („Was bedeutet *erkennen*?") | 166, 173–174 | Qualitätssicherung RE |
| 15 | **Ingenieurteam (wir / Auftragnehmer)** | Konzipiert und realisiert das System; gestaltet alle Entscheidungen und verantwortet das Ergebnis | Lauffähigen Prototyp + Doku liefern; Projekt unter unklaren Anforderungen stemmen; Methodenvergleich; Projekterfolg & Bewertung | Handreichung §2 „Ihre Rolle" | Auftragnehmer / Realisierer |

**Bewusst *kein* Stakeholder:** Die „Flughäfen A/B/C" (Z. 100–113) sind **Benchmark-/Referenzquellen**, keine Interessenträger am System.

### Klärungsbedarf zur Leitungsebene
Der Text nutzt drei Labels — *Geschäftsführung*, *Betriebsleitung*, *Flughafenleitung* — mit
unterschiedlichem Fokus (Finanzen / Verfügbarkeit / Verantwortung). Ob das drei Rollen oder
dieselbe Instanz unter wechselndem Namen ist, geht aus dem Text **nicht** hervor → als Annahme/
Rückfrage dokumentieren. Ebenso offen: Sind „Sicherheitsabteilung" (Z. 29) und
„Sicherheitsbeauftragte" (Z. 163) identisch?

## B) Zentrale Zielkonflikte

Die Stakeholder sind nicht nur zu zählen — die Anforderungen widersprechen sich entlang dieser Achsen:

1. **Verfügbarkeit ↔ Sicherheit:** Betriebsleitung/Controlling („Bahn nicht unnötig schließen", Kosten) vs. Sicherheit/Winterdienst („Lieber zehn Fehlalarme als ein vereistes Flugzeug"). → Kern der Bewertungslogik; Schwellwert bewusst parametrierbar/begründet.
2. **Kosten ↔ Datenqualität:** Controlling (billig) vs. Berater/Gutachter/Winterdienst (mehr & bessere Messgrößen, teurere Sensoren).
3. **Ist-Zustand ↔ Vorhersage:** Aktuelles System meldet nur den Moment; Fluglotsen brauchen ≥ 30 min Prognose.
4. **Zuständigkeit/Datenhoheit:** Daniel will direkten Datenzugang; Sandra: „dafür ist der Winterdienst zuständig" → organisatorische Grenze.
5. **Lokal ↔ Cloud (+ Fernzugriff):** IT-intern ungelöst (Sebastian: lokal; Laura: Cloud einfacher zu warten, Fernzugriff praktisch).
6. **Schuldfrage IT ↔ Winterdienst:** „falsche Daten" vs. „Sensor laut Hersteller korrekt" — ungeklärte Verantwortlichkeit als sozialer Konflikt.

## C) Latente, externe & regionale Stakeholder (über das Briefing hinaus)

Im Text **nicht** genannt, aber betroffen — ihr Fehlen ist selbst ein dokumentierwürdiger Befund. Die unteren Einträge betreffen das **regionale/gesellschaftliche Umfeld** und setzen voraus, dass das im Briefing fiktive **ANR real dem Flugplatz Coburg** entspricht (Annahme, zu bestätigen):

| Latenter / externer Stakeholder | Warum relevant |
|---|---|
| **Piloten / Flugbesatzung** | Unmittelbar sicherheitsbetroffen durch Vereisung — nirgends als Informationsempfänger genannt |
| **Passagiere** | Von Verspätungen/Sperrungen direkt betroffen (Ende der Wirkungskette) |
| **Generelle Luftfahrtbehörden** (z. B. LBA/EASA, DFS/Flugsicherung) | Regulatorische Vorgaben an ein sicherheitskritisches System; Zulassung/Haftung → **Macht hoch** |
| **Datenschutz/Rechtsabteilung & Versicherung** | Haftung bei Fehlentscheidung, Beweissicherung (Logging) |
| **Stadt / Kommune Coburg** | Kommunaler Träger-/Standortkontext des Regionalflughafens; politisches & wirtschaftliches Interesse (Standortfaktor, ggf. Mitfinanzierung) |
| **Staat Deutschland (Bund)** | Übergeordnete Ebene: Verkehrsinfrastruktur, Regulierung, ggf. Förderung — nur mittelbar am Prototyp |
| **Aeroclub Coburg** | Nutzer des Flugplatzes (allgemeine Luftfahrt) — unmittelbar von Bahnzustand, Sperrung & Vereisung betroffen |
| **Regional ansässige Unternehmen** | Wirtschaftlich von Erreichbarkeit/Betrieb des Flugplatzes abhängig (Geschäftsflüge, Standortanbindung) |
| **Anwohner** | Lokale Betroffenheit (Lärm, Sicherheit); am Vereisungssystem selbst nur geringes direktes Interesse |

## D) Grafische Matrix (Power-Interest)

Vertikal = **Interesse** (oben hoch) · horizontal = **Einfluss** (links A/B = hoch, rechts C/D = niedrig). _(neu)_ = in dieser Iteration ergänzt.

```
                          Hohes Interesse
                                ▲
        ┌───────────────────────────┬─────────────────────────────────┐
        │  A) Manage closely        │  C) Keep informed                │
        │                           │                                  │
        │  • Flughafenleitung       │  • Winterdienst                  │
        │  • Betriebsleitung        │  • Fluglotsen                    │
        │  • Sicherheit             │  • Externer Gutachter            │
        │  • IT-Abteilung           │  • Technischer Berater           │
        │  • Ingenieurteam (intern) │  • Wartungstechniker             │
        │                           │  • Airlines                      │
        │                           │  • Reviewer                      │
        │                           │  • Aeroclub Coburg         (neu) │
 hoher  ├───────────────────────────┼─────────────────────────────────┤ niedriger
Einfluss│  B) Keep satisfied        │  D) Monitor                      │ Einfluss
        │                           │                                  │
        │  • Geschäftsführung       │  • Sensorhersteller              │
        │  • Controlling            │  • Stadt Coburg            (neu) │
        │  • Generelle              │  • Staat Deutschland       (neu) │
        │    Luftfahrtbehörden(neu) │  • Regional ansässige      (neu) │
        │                           │    Unternehmen                   │
        │                           │  • Anwohner                (neu) │
        └───────────────────────────┴─────────────────────────────────┘
                                ▼
                          Niedriges Interesse
```

> Einordnung der neuen Parteien: **Monitor (D)** = Stadt Coburg, Staat Deutschland, regional ansässige Unternehmen, Anwohner (geringe Projektmacht + geringes Interesse am Vereisungssystem selbst). **Aeroclub Coburg → C** (betroffener Nutzer). **Generelle Luftfahrtbehörden → B** (Regulierungsmacht, aber geringes Detail-Interesse am Prototyp).

---

## F) Priorisierung für M1 — Notwendige vs. optionale Stakeholder

Für eine schlanke Anforderungs- und Projektplanung lassen sich die identifizierten Stakeholder in drei Gruppen einteilen.

### A — Unbedingt notwendig (im Fokus behalten)

Direkt am System beteiligt, mit Entscheidungsmacht oder als primärer Nutzer.

| Stakeholder | Begründung |
|---|---|
| Flughafenleitung | Auftraggeberin, treibt das Projekt voran |
| Betriebsleitung | Entscheidet operativ über Bahnverfügbarkeit/Sperrung |
| Sicherheitsabteilung / Sicherheitsbeauftragte | Vetomacht, harte Sicherheitsvorgaben |
| Winterdienst | Primärnutzer des Systems |
| Fluglotsen | Endabnehmer der Vorhersagedaten |
| IT-Abteilung | Architektur-Ownership, Betrieb, Wartung |
| Ingenieurteam (intern) | Realisiert den Prototypen |

### B — Wichtig, aber sekundär (kurz berücksichtigen)

Beeinflussen Anforderungen oder Rahmenbedingungen, haben aber keine direkte Projektmacht im fiktiven Szenario.

| Stakeholder | Begründung |
|---|---|
| Geschäftsführung | Budgetfreigabe, aber wenig operatives Interesse |
| Controlling | Kostenrestriktionen |
| Externer Gutachter | Fachliche Ursachenklärung |
| Technischer Berater | Fehlende Messgrößen benennen |
| Wartungstechniker | Wartbarkeit/Robustheit |
| Generelle Luftfahrtbehörden (z. B. LBA/EASA) | Regulatorischer Rahmen für sicherheitskritische Systeme |
| Aeroclub Coburg | Betroffener Nutzer des Flugplatzes |

### C — Optional / weglassbar (nur bei Bedarf)

Geringer oder indirekter Einfluss auf das System im Projektkontext.

| Stakeholder | Begründung |
|---|---|
| Sensorhersteller | Reiner Lieferant, kein Projektinteresse |
| Airlines | Indirekt betroffen, kein direkter Einfluss |
| Reviewer (Lastenheft) | Prozessrolle, kein eigentlicher Interessenträger |
| Stadt Coburg | Nur indirekt über Flugplatz-/Gemeindeinteressen betroffen |
| Staat Deutschland | Genereller regulatorischer Rahmen, nicht projektspezifisch |
| Regional ansässige Unternehmen | Indirekte wirtschaftliche Betroffenheit |
| Anwohner | Kein direkter Bezug zum Vereisungssystem |

**Empfehlung:** Für M1 reichen die **7 Stakeholder aus Gruppe A** als Kerngruppe. Gruppe B kann als „weitere relevante Akteure" kurz erwähnt werden, Gruppe C lässt sich weglassen oder nur als Fußnote aufführen.

---

## E) Offene Punkte für M1

- Leitungs-Labels konsolidieren — eine Instanz oder drei?
- „Sicherheitsabteilung" vs. „Sicherheitsbeauftragte" — identisch?
- Latente Stakeholder als Annahmen aufnehmen oder bewusst aus dem Scope ausschließen — Entscheidung begründen.
- **ANR ≈ Flugplatz Coburg** bestätigen — die regionalen Stakeholder (Stadt, Aeroclub, Unternehmen, Anwohner) hängen an dieser Annahme.
