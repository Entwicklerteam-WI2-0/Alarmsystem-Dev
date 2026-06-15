# AGENTS.md – Projektkurs: Vereisungserkennung am Flughafen ANR

> Diese Datei richtet sich an KI-Coding-Agenten, die an diesem Projekt arbeiten.
> Sie beschreibt den aktuellen Stand des Projekts auf Grundlage der tatsächlich im Projektverzeichnis vorhandenen Dateien.

---

## 1. Projektübersicht

Dieses Verzeichnis enthält Materialien für einen **studentischen Projektkurs im Bereich Technik/Engineering**.
Das Projektthema ist die Entwicklung eines **prototypischen Systems zur Erfassung und Bewertung von Vereisungsbedingungen auf einer Startbahn** am fiktiven Flughafen **ANR (Airport North Regional)**.

**Wichtiger Hinweis:** Im Projektverzeichnis befinden sich derzeit **keine Quellcodedateien, keine Build-Konfigurationen und keine Testinfrastruktur**. Das Projekt befindet sich in der **Anforderungs- und Planungsphase**.

### Kernziele des Projekts

- Erfassung relevanter Wetter- und Oberflächendaten (z. B. Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Niederschlagsart).
- Erkennung bzw. Bewertung von Vereisungsrisiken.
- Bereitstellung eines Backend-Systems zur Datenverarbeitung und Entscheidungsunterstützung.
- Visualisierung der Daten und Alarmierung über ein Frontend.
- Lieferung eines funktionierenden Gesamtprototyps.

### Stakeholder-Konflikte und Rahmenbedingungen

Die Projektausgangslage ist bewusst unvollständig und widersprüchlich gestaltet. Zentrale Spannungsfelder:

- **Sicherheit vs. Betriebskosten:** Die Sicherheitsabteilung bevorzugt eher Fehlalarme, die Betriebsleitung will keine unnötigen Sperrungen.
- **Messgrößen:** Die bisherige Wetterstation erfasst nur Lufttemperatur und Luftfeuchtigkeit. Der externe Gutachter weist darauf hin, dass die **Oberflächentemperatur** entscheidend wäre.
- **Verantwortung:** Menschliche Entscheidungsträger müssen die Startbahnfreigabe erteilen; eine automatische Freigabe durch das System ist **ausgeschlossen**.
- **Vorhersagehorizont:** Die Fluglotsen benötigen Informationen mindestens **30 Minuten** vor dem kritischen Zeitpunkt.

---

## 2. Projektstruktur

Das Verzeichnis enthält die folgenden Dateien:

| Datei | Inhalt |
|-------|--------|
| `Die Hintergrundgeschichte.txt` | Fiktive Hintergrundgeschichte des Flughafens ANR mit Vorfällen, E-Mails, Chats, Gutachten und einem unvollständigen Lastenheft-Entwurf. |
| `Studierenden-Handreichung.txt` | Offizielle Aufgabenstellung für die Studierenden mit Rollen, Gruppenaufteilung, Vorgehensmodellen, Meilensteinen und Bewertungskriterien. |
| `Zeitplan.txt` | Wochenplanung für Woche 1 (Analyse & Anforderungen) und Woche 2 (Entwicklung & Prototyping); die Datei endet nach M2 scheinbar unvollständig. |
| `Stakeholderanalyse.md` | Analyse aller identifizierten Stakeholder (inkl. latenter Stakeholder), Zielkonflikte, Klärungsbedarf. |
| `Usecase-quick.md` | Problemstellung, Usecase, funktionale und nicht-funktionale Anforderungen sowie offene Entscheidungen. |
| `Power-Interest-Grid.md` | Power-Interest-Grid zur Priorisierung der Stakeholder aus `Stakeholderanalyse.md`. |
| `AGENTS.md` | Diese Datei. |
| `CLAUDE.md` | Projektbriefing für Claude Code (Initial-/Quellenbeschreibung). |
| `Handreichung für die Studis.pdf` | PDF-Version der Studierenden-Handreichung. |
| `Hintergrundgeschichte.pdf` | PDF-Version der Hintergrundgeschichte. |
| `Wochenübersicht.pdf` | PDF-Version des 3-Wochen-Zeitplans. |
| `Prüfungsleistung Anforderungen.txt` | Bewertungskriterien für individuelle (40 %) und Gruppenprüfungsleistung (60 %) sowie Liste der zu erstellenden Dokumente. |

### Fehlende Bestandteile

Zum aktuellen Zeitpunkt sind **nicht vorhanden**:

- `pyproject.toml`, `package.json`, `Cargo.toml`, `pom.xml`, `go.mod`, `requirements.txt` oder ähnliche Konfigurationsdateien.
- Quellcode, Bibliotheken, Frameworks oder Laufzeitumgebungen.
- Build-Skripte, CI/CD-Konfigurationen oder Deployment-Dateien.
- Testdateien, Testframeworks oder Teststrategien.

**Vorhanden:** Versionskontrolle als Git-Repository (`.git`).

---

## 3. Technologiestack

Der Technologiestack ist **noch nicht festgelegt** und muss im Rahmen des Projekts durch die Gruppen ausgewählt und begründet werden.

### Vom Szenario abgeleitete technische Komponenten

Das geplante System soll folgende Bausteine enthalten:

1. **Sensordatenerfassung** (Gruppe 1)
   - Recherche und Auswahl realer Sensoren (z. B. Sensorserie WX-500 als Beispiel aus dem Szenario).
   - Erfassung von: Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Niederschlagsart, Eisindikator.
2. **Backend & Entscheidungslogik** (Gruppe 2)
   - Datenmodell, API, persistente Speicherung.
   - Algorithmus zur Vereisungsbewertung.
3. **Frontend & Integration** (Gruppe 3)
   - Nutzeroberfläche zur Visualisierung.
   - Alarmierung und Gesamtsystemintegration.

### Architekturentscheidungen (offen)

Folgende Entscheidungen müssen noch getroffen und dokumentiert werden:

- **Lokale Installation vs. Cloud-Betrieb** (im Szenario offen diskutiert: lokal wird von IT bevorzugt, Cloud-Wartung als Vorteil gesehen, Fernzugriff als praktisch erachtet; siehe `Usecase-quick.md`, AE-01/AE-02).
- **Kommunikationsprotokolle** zwischen Sensoren und Backend.
- **Datenbank- und Framework-Auswahl**.
- **Programmiersprachen** für Backend und Frontend.

---

## 4. Code-Organisation und Modulaufteilung

Da noch kein Quellcode existiert, ist die Modulaufteilung anhand der Studierenden-Handreichung definiert:

| Gruppe | Aufgabenbereich | Vorgehensmodell |
|--------|-----------------|-----------------|
| Gruppe 1 – Sensorik & Daten | Recherche realer Sensoren, Datenblattanalyse, Sensorauswahl, prototypische Messung | Wasserfall |
| Gruppe 2 – Backend & Entscheidungslogik | Datenmodell, API, Speicherung, Vereisungsbewertung | Wasserfall |
| Gruppe 3 – Frontend & Integration | Nutzeroberfläche, Visualisierung, Alarmierung, Gesamtsystemintegration | Scrum (agil) |

Sobald Code entsteht, sollte er sich an dieser Dreiteilung orientieren, z. B.:

```text
sensor/
backend/
frontend/
docs/
tests/
```

---

## 5. Build- und Testbefehle

**Derzeit nicht anwendbar.**

Sobald ein Technologiestack gewählt wurde, sollten hier die projektspezifischen Befehle ergänzt werden, z. B.:

```bash
# Beispielhaft, erst nach Stack-Entscheidung zu verifizieren
# Backend starten
# Frontend starten
# Tests ausführen
```

---

## 6. Entwicklungskonventionen

Basierend auf der Studierenden-Handreichung gelten folgende Konventionen:

- **Dokumentation ist verpflichtend:** Jedes technische Ergebnis muss nachvollziehbar dokumentiert werden.
- **Entscheidungen müssen begründet werden:** Alternativen, Entscheidungsgründe und verbleibende Unsicherheiten sind explizit festzuhalten.
- **Lastenheft ist versioniert:** Anforderungen werden iterativ verfeinert (z. B. Version 0.1 → v1).
- **Hybride Methodik:** Gruppe 1 und 2 arbeiten wasserfallartig, Gruppe 3 agil mit Scrum. Schnittstellen zwischen den Gruppen müssen früh definiert werden.
- **Sicherheitskritikalität:** Das System ist sicherheitsrelevant. Jede technische Entscheidung muss die Konsequenzen für Fehlalarme und nicht erkannte Vereisung berücksichtigen.

---

## 7. Teststrategie

Eine formale Teststrategie ist noch nicht etabliert. Aus dem Szenario ergeben sich folgende Testanforderungen:

- **Sensorgenauigkeit:** Validierung der Messdaten gegen Referenzmessungen.
- **Entscheidungslogik:** Prüfung der Vereisungsbewertung anhand bekannter Szenarien (Fehlalarmfall und nicht erkannte Eisbildung aus der Hintergrundgeschichte).
- **Kommunikation:** Tests für Ausfallszenarien (Kommunikationsausfall, Stromausfall).
- **Systemtests:** End-to-End-Tests der gesamten Datenpipeline von Sensor bis Frontend.
- **Mensch-Maschine-Schnittstelle:** Verifikation, dass keine automatische Freigabe der Startbahn möglich ist.

---

## 8. Sicherheits- und Betrachtungen

Das System ist sicherheitskritisch. Mindestanforderungen:

- **Keine automatische Freigabe der Startbahn.** Die Verantwortung liegt immer beim Menschen.
- **Redundanz und Ausfallabsicherung:** Sensoren können auf dem Vorfeld beschädigt werden; Wartbarkeit und Ersatzfähigkeit müssen berücksichtigt werden.
- **Robustheit gegen Fehlinformationen:** Falsche Sensordaten, Kommunikationsausfälle und Stromausfälle müssen erkannt und behandelt werden.
- **Vermeidung von Fehlalarmen und Auslassungsfehlern:** Das System muss ein ausgewogenes Verhältnis zwischen Sensitivität und Spezifität bieten.
- **Lokale Datenverarbeitung vs. Cloud:** Gemäß IT-Abteilung im Szenario offen diskutiert; lokal bevorzugt, Cloud-Wartung als Vorteil gesehen, Fernzugriff als praktisch erachtet. Bei Fernzugriff sind Authentifizierung, Autorisierung und Verschlüsselung erforderlich.

---

## 9. Meilensteine und Deliverables

| Meilenstein | Zeitpunkt | Zentrale Deliverables |
|-------------|-----------|----------------------|
| M1 | Ende Woche 1 | Stakeholderanalyse, erste Anforderungen, Sensorkandidaten + Datenblätter, Architekturideen, dokumentierte Konflikte |
| M2 | Ende Woche 2 | Funktionierende Teilmodule, API & Datenmodell, erste Integration, Testprotokolle |
| M3 | Ende Woche 3 | Vollständiger Prototyp, Live-Demonstration, Abschlusspräsentation, Reflexion |

### Endgültig zu liefernde Ergebnisse

- Funktionierender Prototyp.
- Sensor-, Backend- und Frontend-Komponenten.
- Integriertes Gesamtsystem.
- Versioniertes Lastenheft.
- Architekturdiagramm.
- API-Beschreibung.
- Sensordatenanalyse.
- Entscheidungslogbuch.

### Pflichtdokumente laut `Prüfungsleistung Anforderungen.txt`

| Dokument | Verantwortlich | Zeitpunkt |
|---|---|---|
| Stakeholderanalyse | Alle | Woche 1 |
| Lastenheft | Alle | Woche 1 |
| Systemkontext | Alle | Woche 1 |
| Sensorstudie | Gruppe 1 | Woche 1–2 |
| Sensorauswahl | Gruppe 1 | Woche 2 |
| Messkonzept | Gruppe 1 | Woche 2 |
| Datenmodell | Gruppe 2 | Woche 2 |
| API-Dokumentation | Gruppe 2 | Woche 2 |
| Vereisungslogik | Gruppe 2 | Woche 2 |
| UI-Konzept | Gruppe 3 | Woche 2 |
| Alarmkonzept | Gruppe 3 | Woche 2 |
| Integrationskonzept | Gruppe 3 | Woche 2 |
| Entscheidungslogbuch | Alle | laufend |
| Testprotokoll | Alle | Woche 3 |
| Abschlusspräsentation | Alle | Woche 3 |

---

## 10. Hinweise für Agenten

- **Keine Annahmen über Technologien treffen.** Es gibt noch keinen Stack.
- **Bevor Code generiert wird**, sollte das Lastenheft vervollständigt und der Architekturentwurf dokumentiert werden.
- **Anforderungsdokumente beachten:** `Stakeholderanalyse.md`, `Usecase-quick.md` und `Power-Interest-Grid.md` sind erstellt und enthalten funktionale/nicht-funktionale Anforderungen sowie offene Entscheidungen (z. B. Lokal vs. Cloud, Fernzugriff).
- **Deutsche Sprache verwenden:** Die Projektdokumentation ist auf Deutsch verfasst.
- **Sicherheitsanforderungen immer berücksichtigen:** Dies ist kein normales Webprojekt, sondern ein sicherheitskritisches Ingenieursprojekt.
- **Abweichungen vom dokumentierten Plan müssen als [DEVIATION] markiert und begründet werden** (siehe globale AGENTS.md im Benutzerprofil).
