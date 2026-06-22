# Task-Zuweisungsvorschlag G2 Backend

> Ausgangslage: `teamstruktur-final.md` (4 Rollen, 8 Personen) + aktueller Jira-Stand (Projekte DTB & ORG).  
> Ziel: Vorschlag, wer welche Jira-Tasks übernimmt, begründet nach Rollen, kritischem Pfad und aktuellem Workload.  
> **Dies ist ein Vorschlag — finale Zuweisung liegt beim PL/Architekten-Team.**

---

## 1. Teamstruktur (final)

| Rolle | Personen | Kernverantwortung |
|---|---|---|
| Backend-Developer | **Arash · Luca** | Ingest, Geschäftslogik, Bewertungslogik, API-Implementierung |
| Datenbank-Engineers | **Andreas · Leon** | Schema, Repository-Pattern, Persistenz, Datenintegrität |
| Architekten | **Lucas · Johannes** | API-Design, Datenmodell, Architekturentscheidungen, technische Unterstützung |
| Test & Code-Review | **Arezo · Amelie** | Testfälle, Testprotokoll, DoD, Code-Review |

> **Hinweis zum Jira-Bestand:** Im Jira tauchen zusätzlich Namen wie *Vladi, Maryam, Reisi, Ilchyshyn, Petzold, Hartling, Mohammadi, Berger* auf. Diese scheinen ältere/andere Bezeichnungen oder Personen aus Querschnitts-/Orga-Rollen zu sein, die nicht in `teamstruktur-final.md` enthalten sind. Der Vorschlag orientiert sich an der **finalen Rollenaufteilung** und benennt offene Klärungsbedarfe.

---

## 2. Kritische Pfad-Betrachtung

Der kritische Pfad für M2 ist:

1. **Datenmodell + API-Contract einfrieren** (P1)
2. **Bewertungslogik** (P2.4) — Kern-IP, muss korrekt sein
3. **Persistenz + DB-Setup** (P2.2 + MySQL-Setup-Tasks) — Enabler für alle folgenden Features
4. **Fail-safe-Verhalten** (P3.1/P3.2/P3.7 + ADR E-32) — sicherheitskritisch

Diese Tasks sollten auf den **verlässlichsten Köpfen** liegen (Architekten + erfahrene Devs), nicht auf Querschnitts-Rollen allein.

---

## 3. Aktueller Jira-Workload (Stand 22.06.2026)

### Bereits zugewiesen

| Person | Anzahl | Tickets |
|---|---|---|
| **Lucas Vöhringer** | ~9 | DTB-1, DTB-2, DTB-12, DTB-19, DTB-26, DTB-35, DTB-38, ORG-5, ORG-6, ORG-7 |
| **Johannes Petzold** | 2 | DTB-11, DTB-15 |
| **Arash** | 1 | DTB-5 (Epic) |

### Noch nicht zugewiesen

- Luca, Andreas, Leon, Arezo, Amelie
- Alle ORG-Tickets außer ORG-5/6/7
- Die meisten DTB-Implementierungs- und Test-Tasks

> **Erkenntnis:** Lucas ist stark überlastet (10 Tickets, davon mehrere kritische Pfad-Items). Entlastung dringend empfohlen.

---

## 4. Vorgeschlagene Task-Zuweisung

### 4.1 Architekten (Lucas · Johannes)

**Lucas** — fachliche Leitung, kritische Pfad-Entscheidungen, Naht:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-2 | P0.1 Stack-Entscheidung | Architekturentscheidung, DRI |
| DTB-12 | P1.1 Datenmodell-Schema festzurren | Naht-Definition, kritischer Pfad |
| DTB-19 | P1.2 API-Spezifikation v1 | Contract-first, Naht zu G1/G3 |
| DTB-35 | P1.4 Contract v1 einfrieren | Freigabe-Autorität |
| DTB-38 | P2.4 Bewertungsmodul 4-Stufen-Logik | Kern-IP + sicherheitskritisch |
| DTB-48 | ADR E-32 Fail-safe Multi-Layer | NF-01, Architektur-Entscheidung |
| DTB-39 | AE-01/NF-02 Betriebsmodell/Latenz | Entscheidungslog, E-30/E-31 |
| DTB-43 | P2.5 GET /assessment/current | Fail-safe an der Lese-Grenze |
| ORG-5/6/7 | PL/Meilensteine | PL-Rolle |

**Johannes** — technische Infrastruktur, DB-Setup, Tooling:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-11 | CI/CD-Setup | Infrastruktur/DevEx |
| DTB-15 | Config-Infrastructure thresholds.json | Grundbaustein für NF-05 |
| DTB-53 | Docker Compose MariaDB | dev=prod, DB-Setup |
| DTB-55 | SQLAlchemy-Engine + Session/Pool | zentraler DB-Bootstrap |
| DTB-54 | Alembic initialisieren | Schema-Migrationen |
| DTB-56 | MySQL-Treiber festlegen | technische Infrastruktur-Entscheidung |

> **Entlastung von Lucas:** DB-Setup-Tasks (DTB-53 bis DTB-56) werden von Johannes übernommen, da sie technisch eng zusammenhängen und Lucas nicht auch noch das MySQL-Setup allein tragen muss.

---

### 4.2 Backend-Developer (Arash · Luca)

**Arash** — Ingest + Alarm-Pfad:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-18 | P2.1 Poller-Client G1 GET /current | Ingest-Kernaufgabe |
| DTB-32 | P2.3 Taupunkt-Berechnung | reine Funktion, gut testbar |
| DTB-27 | P3.3 Alarm-Generierung + Hysterese | Geschäftslogik |
| DTB-24 | P4.1 Alarm-Quittierung | Alarm-Lifecycle |
| DTB-31 | P3.4 GET /alarms | Serving-Endpoint |

**Luca** — API-Grundgerüst + Serving:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-51 | P0.3 Lauffähiges Grundgerüst (GET /health) | Schneller Win, API-Grundlage |
| DTB-34 | P4.4 Historie GET /readings | Endpoint-Implementierung |
| DTB-37 | P3.5 Restliche Messgrößen | Modell-/Ingest-Erweiterung |
| DTB-33 | P2.4b Einfache 30-min-Trendprognose | Stretch, auf Bewertung aufbauend |
| DTB-50 | P0.2 Repo-Struktur anlegen | zusammen mit Johannes/Lucas |

> **Pairing-Vorschlag:** Arash + Luca sollten gemeinsam den T0-Slice durchspielen (Poller → Bewertung → GET /assessment/current), um Abstimmung zu sichern.

---

### 4.3 Datenbank-Engineers (Andreas · Leon)

> Aufgabe: Repository-Pattern + Schema-Implementierung, auf Basis der von Johannes/Lucas vorgegebenen Engine/Migrationen.

**Andreas** — Repository-Layer + Datenintegrität:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-28 | P2.2 Persistenz (Repository-Pattern) | Kerntask der Rolle |
| DTB-55 | SQLAlchemy-Engine + Session/Pool | *Unterstützung/Review* von Johannes |
| DTB-52 | P0.4 Branch/PR-Konventionen + DoD | *Mitwirkung* (Datenintegrität-Aspekt) |

**Leon** — Migrationen + DB-Betrieb:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-54 | Alembic initialisieren | Schema-Versionierung |
| DTB-56 | MySQL-Treiber festlegen | *Review/Unterstützung* von Johannes |
| DTB-57 | Pi-Betrieb: Retention/Rotation | DB-Betrieb, SD-Kartenschutz |

> **Klarstellung:** DTB-53/-54/-55/-56 sind enge Infrastruktur-Blöcke. Johannes führt sie als DRI durch, Andreas/Leon unterstützen aktiv und übernehmen anschließend den operativen Repository-Layer (DTB-28) und das Retention-Thema (DTB-57).

---

### 4.4 Test & Code-Review (Arezo · Amelie)

> Aufgabe: Tests entwerfen, Review-Prozess etablieren, DoD sicherstellen. Nicht nur „am Ende testen", sondern früh mit den Entwicklern abgleichen.

**Arezo** — Bewertungs- und Fail-safe-Tests:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-21 | pytest-Konfiguration + Fixtures | Test-Infrastruktur |
| DTB-46 | P2.6 Unit-Tests Bewertung (≥80% Coverage) | Kerntest für Bewertungslogik |
| DTB-49 | P3.7 Fail-safe-Test (Stale/Defekt → nie GRÜN) | NF-01 |

**Amelie** — Integration, Sicherheit, Testprotokoll:

| Ticket | Titel | Begründung |
|---|---|---|
| DTB-41 | P3.6 Integrationstest Ingest→Bewertung→API | E2E-Fluss |
| DTB-42 | P4.5 RB-01-Nachweis (kein Aktor-Endpoint) | Sicherheits-Review |
| DTB-30 | P5.3 Testprotokoll (Abnahme-Checkliste) | DoD/Abnahme |
| DTB-22 | Enforce No-Hardcode Rule | Qualitätsregel |

---

### 4.5 Dokumentation / Querschnitt

Diese Tasks sollten **nicht allein einem „Doku-Team"** zugewiesen werden, sondern von den jeweiligen Implementierern mitverfasst und von einer Doku-Rolle konsolidiert werden.

| Ticket | Titel | Vorgeschlagene Owner |
|---|---|---|
| DTB-36 | P5.4a Gruppen-Entscheidungslogbuch finalisieren | Alle Untergruppen (jede liefert Einträge), Doku-Rolle konsolidiert |
| DTB-45 | P5.4b Individuelle Entscheidungsreflexion | Jede Person selbst (nicht delegierbar) |
| DTB-44 | P5.5 Abschlusspräsentation + Demo-Skript | Lucas + alle, Doku-Rolle aufbereitet |
| DTB-47 | P5.6 Reflexion Methodenvergleich | Alle, Doku-Rolle formuliert |
| ORG-16 | Jede Untergruppe führt eigenes Entscheidungslogbuch | Alle Untergruppen |

---

### 4.6 Orga / Schnittstelle (ORG-Projekt)

| Ticket | Titel | Vorgeschlagene Owner |
|---|---|---|
| ORG-9 | Backend-E-Mails an Yana für SharePoint | Lucas (PL) |
| ORG-10 | Lukas Föhringer auf Schnittstellen-Abstimmung ansetzen | Lucas (PL) → Johannes/Lucas als Schnittstelle |
| ORG-11 | Rückmeldung zu Nicks API-Anforderungsvorschlag | Lucas (PL) |
| ORG-12 | Doku-Team auf gemeinsames Lastenheft ansetzen | Lucas (PL) + Doku-Rolle |
| ORG-13 | Gemeinsame Abgaben sicherstellen | Lucas (PL) |
| ORG-14 | API-Vertrag definieren (Contract-first) | Lucas + Johannes |
| ORG-15 | Eigene API-Schnittstellen Richtung Frontend | Backend-Devs (Arash/Luca) + Architekten |
| ORG-16 | Jede Untergruppe eigenes Entscheidungslogbuch | Alle |
| ORG-2/3/4/8 | Vladi/Maryam/Diktiergerät | **Nicht G2-Backend — klären, ob diese Personen überhaupt im G2-Scope sind.** |

---

## 5. Workload-Visualisierung nach Vorschlag

| Person | Anzahl Tickets | Schwerpunkt |
|---|---|---|
| Lucas | ~9 | Architektur, Contract, Bewertungslogik, PL-Orga |
| Johannes | ~6 | DB-Infrastruktur, CI/CD, Config |
| Arash | 5 | Ingest, Alarm, Taupunkt |
| Luca | 5 | API-Grundgerüst, Serving, Messgrößen |
| Andreas | 3 | Repository-Pattern, DB-Engine |
| Leon | 3 | Migrationen, Treiber, Retention |
| Arezo | 3 | pytest, Bewertungs-Tests, Fail-safe |
| Amelie | 4 | Integrationstests, RB-01, Testprotokoll |

> **Verteilung ist deutlich ausgewogener** als aktuell. Lucas bleibt fachlich der DRI für kritische Pfad-Items, erhält aber Entlastung bei technischem DB-Setup.

---

## 6. Offene Punkte / Klärungsbedarf

1. **Wer sind Vladi und Maryam?** Sie tauchen in ORG-2/3/4/8 auf, aber nicht in `teamstruktur-final.md`. Sind sie Teil von G2, G1, G3 oder Querschnittsdoku?
2. **Wer ist „Reisi / Ilchyshyn"?** In einigen Ticket-Beschreibungen als Doku-Team genannt, aber nicht in der finalen Struktur.
3. **Name „Petzold, Johannes" vs. „Johannes"** — Ist Johannes Petzold identisch mit Johannes (Architekt) in `teamstruktur-final.md`? Vermutlich ja.
4. **Namen in Jira konsolidieren:** Arash, Luca, Andreas, Leon, Arezo, Amelie müssen als Jira-User angelegt/zugewiesen werden.
5. **Lucas-Overload:** Sollte Lucas tatsächlich DTB-38 (Bewertungslogik) allein implementieren, oder als Pair mit Arash/Luca? Empfehlung: Pairing, DRI bleibt Lucas.

---

## 7. Sofortige nächste Schritte (Vorschlag)

1. **Klärungs-Meeting** (15 Min): Name-Mapping Jira ↔ Teamstruktur klären; Vladi/Maryam/Reisi/Ilchyshyn zuordnen.
2. **Workload-Entlastung von Lucas:** DTB-53/54/55/56 an Johannes vergeben.
3. **Test-Team früh einbinden:** Arezo/Amelie bekommen schon vor der Implementierung Zugriff auf die Entwürfe von DTB-38/41/46.
4. **Jira-Zuweisungen aktualisieren** gemäß diesem Vorschlag.
5. **Definition of Ready für DTB-38:** Schwellenwerte-Dummies aus `Schwellenwerte.md` + die beiden Vorfälle als Testfixtures bereitstellen.

---

*Erstellt am 22.06.2026 auf Basis von `teamstruktur-final.md`, `Tasks+Projektplan.md`, `Backend-Konzept.md` und dem Jira-Stand der Projekte DTB/ORG.*
