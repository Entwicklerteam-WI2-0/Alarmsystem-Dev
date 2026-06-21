# Teamstruktur final — Gruppe 2 (Backend & Entscheidungslogik)

> Verbindliche Rollenaufteilung des aktiven Entwicklerteams.  
> Aktualisiert und verfeinert die vorherige `Team-Organisation+Regeln.md` für die Implementierungsphase.

---

## 1. Aktives Entwicklerteam

| Sub-Team / Rolle | Personen | Kernverantwortung (DRI) |
|---|---|---|
| **Backend-Developer** | Arash · Luca | Ingest, Geschäftslogik, Vereisungs-Bewertungslogik, API-Implementierung |
| **Datenbank-Engineers** | Andreas · Leon | Datenbankschema, Repository-Pattern, Persistenz, Datenintegrität, Abfrageoptimierung |
| **Architekten** | Lucas · Johannes | API-Design, Datenmodell (Naht zu G1/G3), Architekturentscheidungen, technische Unterstützung der aktiven Entwickler |
| **Test & Code-Review** | Arezo · Amelie | Testfälle, Testprotokoll, Definition-of-Done, Code-Review, Qualitätssicherung |

---

## 2. Begründung: Trennung in Backend-Developer und Datenbank-Engineers

Die Unterteilung des Backend-Teams in **Backend-Developer** und **Datenbank-Engineers** ist bewusst gewählt und dient folgenden Zielen:

1. **Klare Verantwortlichkeiten (Separation of Concerns)**  
   Die Backend-Developer konzentrieren sich auf die **Anwendungslogik** (Ingest, Validierung, Vereisungs-Bewertung, API-Endpoints). Die Datenbank-Engineers übernehmen die **Persistenzschicht** (Schema-Design, Repository-Implementierung, Datenintegrität, Abfragen). So entstehen keine „grauen Bereiche" zwischen Geschäftslogik und Datenspeicher.

2. **Spezialisierung statt Generalisierung**  
   Persistenz ist ein eigener technischer Bereich: Indexe, Transaktionen, Normalisierung, Stale-Daten-Erkennung und spätere Migrationen (z. B. SQLite → PostgreSQL/TimescaleDB). Mit dedizierten DB-Engineers wird dieses Thema von Personen betreut, die es als Hauptaufgabe verfolgen, anstatt es nebenbei zu erledigen.

3. **Parallele Arbeit ohne Blockaden**  
   Sobald das API-/Datenmodell eingefroren ist, können Backend-Developer gegen definierte Repository-Schnittstellen arbeiten, während die DB-Engineers die eigentliche Speicherimplementierung vervollständigen. Das reduziert Wartezeiten und Abstimmungsaufwand im kritischen Pfad.

4. **Bessere Review- und Qualitätskultur**  
   Eine eigene DB-Perspektive im Team stellt sicher, dass Datenbank-Entscheidungen (Schema-Änderungen, Query-Performance, Ausfallszenarien) nicht nur „beiläufig" reviewt werden. Das erhöht die Robustheit der Persistenzschicht.

5. **Fail-safe als eigene Schicht**  
   Die Datenbank-Engineers sind explizit dafür zuständig, dass das System bei **Ausfall, veralteten oder fehlenden Daten nie fälschlich GRÜN** ausgibt (NF-01 / Fail-safe). Stale-Daten-Erkennung, Zeitstempel-Validierung und sichere Defaults liegen damit in einer klar benannten Verantwortung.

6. **Vorbereitung auf spätere Skalierung**  
   Eine sauber getrennte Persistenzschicht erleichtert den späteren Wechsel von SQLite (T0) auf eine produktionsreife Datenbank (z. B. PostgreSQL/TimescaleDB). Die DB-Engineers kümmern sich um die Isolation dieser Schicht, sodass Backend-Developer davon möglichst wenig mitbekommen.

---

## 3. Zusammenarbeitsmodell

- **Architekten unterstützen die aktiven Entwickler** mit Spezifikation, Review und Entscheidungen — sie sind keine isolierte „Planungsinstanz".
- **Backend-Developer und DB-Engineers arbeiten contract-first:** Das Datenmodell und die Repository-Schnittstelle werden zuerst gemeinsam mit den Architekten festgelegt, dann implementiert.
- **Test & Code-Review prüft beide Sub-Teams:** Bewertungslogik und Persistenz gleichermaßen unterliegen der DoD und dem Testprotokoll.
- Jede Aufgabe hat **genau einen Owner (DRI)**; Abstimmung findet täglich im Standup statt.

---

## 4. Verwandte Dokumente

- `02-Arbeitsdokumente/Team-Organisation+Regeln.md` — ursprüngliche Organisationsgrundlage
- `02-Arbeitsdokumente/Backend-Konzept.md` — Modulstruktur und Schichtenaufteilung
- `02-Arbeitsdokumente/Schwellenwerte.md` — Anforderungen an die Bewertungslogik und Fail-safe-Verhalten
- `02-Arbeitsdokumente/Tasks+Projektplan.md` — Aufgaben, Meilensteine und DoD
