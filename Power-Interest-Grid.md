# Power-Interest-Grid — Stakeholder-Priorisierung

**Deliverable:** Ergänzung zur Stakeholderanalyse für Meilenstein M1  
**Quelle:** `Stakeholderanalyse.md` (v0.1)  
**Status:** v0.1 — Entwurf

---

## 1. Zweck

Das Power-Interest-Grid ordnet die identifizierten Stakeholder nach zwei Dimensionen:

- **Power (Einfluss):** Kann der Stakeholder das Projekt maßgeblich beeinflussen, blockieren oder budgetieren?
- **Interest (Interesse):** Wie stark ist der Stakeholder vom Projekt und seinen Ergebnissen betroffen?

Daraus ergeben sich vier Handlungsfelder:

|  | **Hohes Interesse** | **Niedriges Interesse** |
|---|---|---|
| **Hoher Einfluss** | **A) Manage closely** — eng einbinden, regelmäßig abstimmen | **B) Keep satisfied** — zufriedenstellen, gezielt informieren |
| **Niedriger Einfluss** | **C) Keep informed** — auf dem Laufenden halten | **D) Monitor** — beobachten, nur bei Bedarf aktiv werden |

---

## 2. Einordnung der Stakeholder

| # | Stakeholder | Einfluss | Interesse | Quadrant |
|---|---|---|---|---|
| 1 | Geschäftsführung | Hoch | Niedrig | **B) Keep satisfied** |
| 2 | Betriebsleitung | Hoch | Hoch | **A) Manage closely** |
| 3 | Flughafenleitung | Hoch | Hoch | **A) Manage closely** |
| 4 | Sicherheitsabteilung / Sicherheitsbeauftragte | Hoch | Hoch | **A) Manage closely** |
| 5 | Winterdienst | Niedrig | Hoch | **C) Keep informed** |
| 6 | IT-Abteilung (Laura, Sebastian) | Hoch | Hoch | **A) Manage closely** |
| 7 | Controlling | Hoch | Niedrig | **B) Keep satisfied** |
| 8 | Fluglotsen (Daniel, Sandra) | Niedrig | Hoch | **C) Keep informed** |
| 9 | Externer Gutachter | Niedrig | Hoch | **C) Keep informed** |
| 10 | Technischer Berater | Niedrig | Hoch | **C) Keep informed** |
| 11 | Wartungstechniker | Niedrig | Hoch | **C) Keep informed** |
| 12 | Sensorhersteller | Niedrig | Niedrig | **D) Monitor** |
| 13 | Airlines | Niedrig | Hoch | **C) Keep informed** |
| 14 | Reviewer (Lastenheft) | Niedrig | Hoch | **C) Keep informed** |
| 15 | Ingenieurteam (Auftragnehmer, intern) | Hoch | Hoch | **A) Manage closely** |
| 16 | Generelle Luftfahrtbehörden (LBA/EASA, DFS) | Hoch | Niedrig | **B) Keep satisfied** |
| 17 | Aeroclub Coburg | Niedrig | Hoch | **C) Keep informed** |
| 18 | Stadt / Kommune Coburg | Niedrig | Niedrig | **D) Monitor** |
| 19 | Staat Deutschland (Bund) | Niedrig | Niedrig | **D) Monitor** |
| 20 | Regional ansässige Unternehmen | Niedrig | Niedrig | **D) Monitor** |
| 21 | Anwohner | Niedrig | Niedrig | **D) Monitor** |

> #16–21 stammen aus `Stakeholderanalyse.md` §C (extern/latent, nicht text-belegt). #16 ist latent; #18–21 setzen voraus, dass **ANR real dem Flugplatz Coburg** entspricht (Annahme).

---

## 3. Grafische Matrix

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

---

## 4. Begründung der wichtigsten Einstufungen

### A) Manage closely — Hoher Einfluss + Hohes Interesse

| Stakeholder | Begründung |
|---|---|
| **Flughafenleitung** | Auftraggeberin, treibt das Projekt aufgrund der Vorfälle voran, verlangt Verantwortungsklärung (Z. 50–52). |
| **Betriebsleitung** | Operative Entscheidungsmacht über Bahnverfügbarkeit; direkt von Fehlalarmen und Sperrungen betroffen (Z. 27–28). |
| **Sicherheitsabteilung / Sicherheitsbeauftragte** | Hat Vetomacht durch harte Sicherheitsvorgaben („keine automatische Freigabe", Z. 163–165). |
| **IT-Abteilung** | Hat Architektur-Ownership (Lokal/Cloud/Fernzugriff, AE-01/AE-02) und Betriebsverantwortung; ohne ihre Mitträgerschaft scheitert die Umsetzung (Z. 133–149). |
| **Ingenieurteam (intern)** | Realisiert das System; ohne dessen fachliche Expertise und Entscheidungen gibt es keinen Prototypen (Handreichung §2). |

### B) Keep satisfied — Hoher Einfluss + Niedriges Interesse

| Stakeholder | Begründung |
|---|---|
| **Geschäftsführung** | Bestimmt über Budget und Projektfreigabe, ist aber nicht im operativen Detail interessiert (Z. 65, 72–73). |
| **Controlling** | Kann Kosten entscheidend begrenzen; Interesse beschränkt sich primär auf finanzielle Vertretbarkeit (Z. 66, 68–69, 159–160). |
| **Generelle Luftfahrtbehörden** | Regulierungs-/Zulassungsmacht über ein sicherheitskritisches System (hohe Macht), aber geringes Detail-Interesse am Prototyp selbst — zufriedenstellen, Compliance sicherstellen. |

### C) Keep informed — Niedriger Einfluss + Hohes Interesse

| Stakeholder | Begründung |
|---|---|
| **Winterdienst** | Hauptnutzer im Betrieb, hat aber keine Budget- oder Architekturentscheidungsbefugnis (Z. 18, 38–43, 53–62). |
| **Fluglotsen** | Endabnehmer der Vorhersage, stark betroffen, aber keine direkte Projektmacht (Z. 85–99). |
| **Externer Gutachter / Technischer Berater** | Prägen fachliche Anforderungen, haben aber keine organisatorische Macht (Z. 46–48, 78–84). |
| **Wartungstechniker** | Definiert nicht-funktionale Anforderungen wie Robustheit, hat aber keinen Budget-Einfluss (Z. 114–120). |
| **Airlines** | Wirtschaftlich betroffen, aber extern und ohne direkten Einfluss auf das Projekt (Z. 24, 26). |
| **Reviewer (Lastenheft)** | Beeinflusst Qualität der Anforderungen, ist aber kein Entscheider über Scope oder Budget (Z. 166, 173–174). |
| **Aeroclub Coburg** | Nutzer des Flugplatzes (allgemeine Luftfahrt), unmittelbar von Bahnzustand/Sperrung betroffen — hohes Interesse, aber keine Projektmacht. |

### D) Monitor — Niedriger Einfluss + Niedriges Interesse

| Stakeholder | Begründung |
|---|---|
| **Sensorhersteller** | Reiner Lieferant; Interesse beschränkt sich auf Verkauf, Einfluss auf Architektur oder Entscheidungen ist gering (Z. 150–158). |
| **Stadt / Kommune Coburg** | Standort-/Trägerkontext; am konkreten Vereisungs-Prototyp geringes direktes Interesse und (für dieses Projekt) geringe Macht. _Grenzfall — s. §7._ |
| **Staat Deutschland (Bund)** | Übergeordnete Ebene (Infrastruktur, Regulierung); nur sehr mittelbar am Prototyp beteiligt. |
| **Regional ansässige Unternehmen** | Wirtschaftlich vom Flugplatzbetrieb abhängig, aber ohne Bezug zum/Einfluss auf das Vereisungssystem. |
| **Anwohner** | Lokale Betroffenheit (Lärm, Sicherheit); am Vereisungssystem selbst geringes direktes Interesse, keine Projektmacht. |

---

## 5. Konsequenzen für das Projektmanagement

### A) Manage closely
- Regelmäßige Abstimmung mit Sicherheitsabteilung, Betriebsleitung, Flughafenleitung und IT.
- Entscheidungslogbuch führen, um Sicherheits- vs. Verfügbarkeitsabwägungen nachvollziehbar zu dokumentieren.
- Architekturentscheidungen (Lokal/Cloud, Fernzugriff, Kommunikationsprotokolle) früh mit IT festlegen und dokumentieren.
- Ingenieurteam-interne Kommunikation und Entscheidungsprozesse klar regeln (Wasserfall vs. Scrum).

### B) Keep satisfied
- Geschäftsführung und Controlling mit knappen, zahlenbasierten Updates versorgen.
- Kosten-Nutzen-Rechnung für Sensoren (z. B. WX-500) vorbereiten.
- Budgetrahmen früh kommunizieren und dokumentieren.
- Generelle Luftfahrtbehörden: regulatorische Anforderungen früh sichten (Zulassung/Haftung), keine Detail-Einbindung nötig.

### C) Keep informed
- Winterdienst und Fluglotsen in Usability-Tests und Demonstrationen einbeziehen.
- Gutachter/Berater als fachliche Reviewer nutzen.
- Wartungstechniker bei Robustheits- und Wartbarkeitsanforderungen einbeziehen.
- Aeroclub Coburg über Bahnzustand/Alarmierung informieren, sofern Allgemeine Luftfahrt betroffen ist.

### D) Monitor
- Sensorhersteller als reine Beschaffungsoption betrachten; Alternativen recherchieren.
- Stadt Coburg, Staat, regionale Unternehmen, Anwohner: nur beobachten; bei politischer/öffentlicher Relevanz (Förderung, Lärm, Berichterstattung) gezielt informieren.

---

## 6. Verknüpfung mit den Zielkonflikten

Das Grid macht deutlich, **wo die Spannungsfelder entschieden werden müssen**:

- **Verfügbarkeit ↔ Sicherheit** wird in Quadrant A ausgetragen (Betriebsleitung vs. Sicherheitsabteilung).
- **Kosten ↔ Datenqualität** wird zwischen Quadrant B (Geschäftsführung/Controlling) und Quadrant C (Gutachter/Berater/Winterdienst) ausgetragen, letztlich in A entschieden.
- **Lokal ↔ Cloud** wird maßgeblich von IT in Quadrant A geprägt; die Entscheidung wirkt auf alle anderen Quadranten.
- **Ist-Zustand ↔ Vorhersage** betrifft vor allem Fluglotsen (Quadrant C), deren Anforderung aber von A legitimiert werden muss.

---

## 7. Grenzfälle und Einschränkungen

Einige Einstufungen sind kontextabhängig und bewusst nicht umgesortiert:

- **Reviewer (Lastenheft):** Aktuell C. Falls der Reviewer ein formelles **Ablehnungsrecht** für das Lastenheft hat (Gate), verschiebt er sich nach **B**.
- **Airlines:** Aktuell C. Der direkte Einfluss auf das Projekt ist gering, aber ihr wirtschaftlicher Druck (Verspätungen, Beschwerden) kann indirekt auf Geschäftsführung/Betriebsleitung wirken → Einfluss ist **nicht ganz null**.
- **IT-Abteilung:** Wurde aufgrund der Architektur-Ownership (AE-01/AE-02) und Betriebsverantwortung in **A** eingeordnet. Bei reinem „Service-Provider"-Verständnis wäre C gerechtfertigt.
- **Stadt / Kommune Coburg:** Aktuell D. Ist die Stadt **Eigentümerin/Geldgeberin** des Flugplatzes, steigt ihre Macht deutlich → dann eher **B (Keep satisfied)**. Hängt an der Eigentümer-/Finanzierungsstruktur.
- **Regionale Stakeholder (#17–21):** setzen die Annahme **ANR ≈ Flugplatz Coburg** voraus. Trifft das nicht zu, entfallen sie.

---

## 8. Offene Punkte

- Klärung, ob „Geschäftsführung", „Betriebsleitung" und „Flughafenleitung" drei separate Instanzen oder Rollenbezeichnungen derselben Instanz sind (siehe `Stakeholderanalyse.md`, Klärungsbedarf).
- Klärung, ob „Sicherheitsabteilung" und „Sicherheitsbeauftragte" identisch sind.
- **ANR ≈ Flugplatz Coburg** bestätigen — die regionalen Stakeholder (#17–21) hängen an dieser Annahme.
- Eigentümer-/Trägerstruktur des Flugplatzes klären (bestimmt die Macht der Stadt Coburg, s. §7).
- Noch **nicht** im Grid: Piloten/Flugbesatzung, Passagiere, Datenschutz/Rechtsabteilung & Versicherung (bislang nur in `Stakeholderanalyse.md` §C) — bei Bedarf ergänzen.
