# AGENTS.md – Projektkurs: Vereisungserkennung am Flughafen ANR

> Diese Datei richtet sich an KI-Coding-Agenten, die an diesem Projekt arbeiten.
> Sie beschreibt den aktuellen Stand auf Grundlage der tatsächlich vorhandenen Dateien.
> Sprache: Deutsch (wie alle Projektdokumente).
> **Hinweis:** Dieses Repo ist das **Arbeitsrepo der Backend-Gruppe (G2)** — `Entwicklerteam-WI2-0/Alarmsystem-Dev`.

---

## 1. Projektübersicht

Materialien für einen **studentischen Projektkurs** zur Entwicklung eines **prototypischen Systems zur
Erfassung und Bewertung von Vereisungsbedingungen** am fiktiven Flughafen **ANR (Airport North Regional)**.

**Stand:** Die **Anforderungs-/Planungsphase ist weitgehend abgeschlossen** (Anforderungen, Schwellenwerte,
Backend-Konzept, Projektplan liegen vor). Das Repo geht in die **Implementierungsphase** über — Quellcode
(`src/`, `tests/`) entsteht hier. Der konkrete Technologiestack ist noch nicht final festgelegt.

### Kernziele

- Erfassung relevanter Wetter-/Oberflächendaten (Oberflächentemperatur, Feuchte, Taupunkt, Niederschlagsart, Luftdruck).
- **Bewertung von Vereisungsrisiken** (Entscheidungslogik, s. `Schwellenwerte.md`).
- Backend zur Datenverarbeitung und Entscheidungsunterstützung (**unser Fokus, G2**).
- Visualisierung/Alarmierung über ein Frontend (G3), Sensorik (G1).
- Funktionierender Gesamtprototyp.

### Rahmenbedingungen (bewusst widersprüchlich)

- **Sicherheit vs. Betriebskosten:** Sicherheit bevorzugt Fehlalarme, Betrieb will keine unnötigen Sperrungen.
- **Messgrößen:** Lufttemperatur allein reicht nicht — **Oberflächentemperatur** ist entscheidend.
- **Verantwortung:** Keine automatische Startbahnfreigabe durch das System — der **Mensch entscheidet** (RB-01).
- **Vorhersagehorizont:** mindestens **30 Minuten** Vorlauf.

---

## 2. Projektstruktur

Repo `Alarmsystem-Dev` (Remote `Entwicklerteam-WI2-0/Alarmsystem-Dev`, Branch `main`), gegliedert in:

- `01-quellen/` — Briefing-Rohmaterial vom Dozenten (`.txt`, read-only)
- `02-Arbeitsdokumente/` — erarbeitete `.md`-Deliverables; Bilder in `02-Arbeitsdokumente/assets/`
- `03-abgaben/` — abgabefertige/eingefrorene Stände
- `CLAUDE.md` / `AGENTS.md` / `Agents-gpt-gemini.md` im **Root** (gitignored; Auto-Load bzw. Chat-KI-Briefing)

| Datei | Inhalt |
|-------|--------|
| `01-quellen/Die Hintergrundgeschichte.txt` | Hintergrundgeschichte ANR: Vorfälle, E-Mails, Chats, Gutachten, unvollständiger Lastenheft-Entwurf |
| `01-quellen/Studierenden-Handreichung.txt` | Aufgabenstellung, Rollen, Gruppen, Vorgehensmodelle, Meilensteine, Bewertung |
| `01-quellen/Zeitplan.txt` | Wochenplanung (Analyse/Anforderungen, Entwicklung/Prototyping) |
| `01-quellen/Prüfungsleistung Anforderungen.txt` | Bewertungskriterien (40 % individuell / 60 % Gruppe) + Pflichtdokumente |
| `02-Arbeitsdokumente/Usecase-quick.md` | Usecase + Anforderungen (FA, NF, RB-01, AE, Konflikte K1–K9) |
| `02-Arbeitsdokumente/Schwellenwerte.md` | **Vereisungslogik + konkrete Schwellenwerte** (4 Stufen) + Kalibriervorgaben je FA/NFA |
| `02-Arbeitsdokumente/Backend-Konzept.md` | Architektur der Backend-Gruppe: Module, Datenmodell, Tech-Stack-Optionen, Code-Struktur |
| `02-Arbeitsdokumente/Tasks+Projektplan.md` | Phasen P0–P6, Meilensteine M1–M3, Kanban-Tasks (Owner/DoD/Größe) |
| `02-Arbeitsdokumente/Team-Organisation+Regeln.md` | Rollen/DRI, Zusammenarbeit, Teamregeln |
| `02-Arbeitsdokumente/assets/` | Architekturskizze (WhatsApp-Bild) + Rollen-/Gruppeneinteilungsbilder |
| `03-abgaben/Nutzer und Stakeholdermodel 1.md` / `2.md` | Stakeholder-/Nutzermodell (abgabefertig) |
| `Agents-gpt-gemini.md` (Root) | KI-Onboarding (einfügbares Briefing für ChatGPT/Gemini) |
| `CLAUDE.md` / `AGENTS.md` (Root) | Projekt-/Agenten-Briefing |

> Frühere Dateien sind abgelöst/umbenannt: *Stakeholderanalyse* → *Nutzer-und-Stakeholdermodel*;
> *Randbedingungsmetriken* → *Schwellenwerte*; *Architektur-Stack-Konzept* (zu breit) → *Backend-Konzept* (G2-scoped).
> Ursprüngliche PDFs liegen nicht mehr vor; maßgeblich sind die `.txt`-Extrakte.

### Heutiger Stand (16.06.2026)

Vereisungslogik + Schwellenwerte konkretisiert, Backend-Konzept (G2) und Projektplan/Kanban erstellt,
KI-Onboarding für ChatGPT/Gemini, Rolle/Gruppe bestätigt (G2 Backend; Lucas = Systemarchitekt),
Repo auf `Alarmsystem-Dev` konsolidiert.

---

## 3. Technologiestack

Der konkrete Stack ist **noch nicht final** und gehört begründet ins Entscheidungslogbuch.
Optionen + Empfehlung in **`Backend-Konzept.md` §6**:

- **Backend:** Python **FastAPI** (Empfehlung) · Flask · Node/Express
- **Datenbank:** **SQLite** (T0) → PostgreSQL/TimescaleDB
- **Übertragung:** **HTTP-POST** (T0) → MQTT (Skalierung)
- **Sensorik (G1, Kontext):** ESP32/Raspberry Pi; IR-/Kontaktsensor Oberflächentemp; Kombisensor Temp/Feuchte/Druck (BME280/SHT31); Eisindikator zunächst Proxy/Sim.

**Offene Architekturentscheidungen** (vgl. `Usecase-quick.md` §3.4, AE-01/AE-02): lokal vs. Cloud + Fernzugriff,
Protokoll (HTTP/MQTT), DB-/Framework-Wahl.

---

## 4. Code-Organisation (Backend, G2)

Modul-/Ordnerstruktur s. **`Backend-Konzept.md` §7**:

```text
src/
  ingest/      # REST-Endpoint, Eingangsvalidierung
  model/       # Datenklassen/Schemas
  assessment/  # Vereisungslogik (Schwellenwerte) — Kernmodul, hohe Testabdeckung
  storage/     # DB-Zugriff (Repository-Pattern)
  api/         # Serving-Endpoints für G3
  config/      # parametrierbare Schwellen
  forecast/    # 30-min-Trend (T3)
tests/
```

Zentrale Schnittstelle aller Gruppen = **API/Datenmodell der Gruppe 2**, bis Ende Woche 2 final.
**Scope-Abgrenzung:** G2 baut Backend; Sensor-Hardware = G1, UI = G3. Wir definieren nur den API-Vertrag.

---

## 5. Build- und Testbefehle

**Noch nicht final** (Stack offen). Nach Stack-Entscheidung hier ergänzen:

```bash
# Backend starten / Tests ausführen — nach Stack-Wahl konkretisieren
```

---

## 6. Code-Style und Entwicklungskonventionen

- **Sprache:** alle Artefakte, Doku, Kommentare auf **Deutsch**.
- **Dokumentationspflicht:** jedes technische Ergebnis nachvollziehbar dokumentieren.
- **Entscheidungen begründen** (Alternativen/Gründe/Unsicherheiten) → **Entscheidungslogbuch**.
- **Lastenheft versioniert**, iterativ verfeinert.
- **Hybride Methodik:** G1/G2 Wasserfall, G3 Scrum; Schnittstellen früh definieren.
- **Sicherheitskritikalität:** jede Entscheidung gegen Fehlalarme/nicht erkannte Vereisung abwägen.
- **Git:** Feature-Branch → PR → Review → `main`; keine Secrets; ausgehende/destruktive Aktionen nur nach Genehmigung.
- **Vereisungslogik/Schwellenwerte ausschließlich aus `Schwellenwerte.md`** — nichts dazuerfinden.
- Abweichungen vom Plan als **[DEVIATION]** markieren und begründen.

---

## 7. Teststrategie

- **Entscheidungslogik:** gegen die zwei dokumentierten Vorfälle (−2,1 °C → kein Eis, +1,2 °C → Eis) prüfen; Coverage ≥ 80 %.
- **Plausibilität/Ausfall:** Stale-/Defekt-Erkennung und Fail-safe (Ausfall → nie GRÜN) testen.
- **Systemtests:** End-to-End Sensor → Backend → Frontend.
- **Mensch-Maschine:** verifizieren, dass **keine** automatische Freigabe möglich ist (RB-01).
- Abnahme-Checkliste s. `Schwellenwerte.md` §3.

---

## 8. Sicherheits-Betrachtungen

- **Keine automatische Freigabe der Startbahn** — Mensch ist letzte Instanz (RB-01).
- **Redundanz/Ausfallabsicherung:** Sensoren werden beschädigt → Wartbarkeit/Ersatz.
- **Robustheit gegen Fehlinformationen:** falsche Daten, Komm./Stromausfall erkennen und behandeln.
- **Fehlalarm vs. Auslassung** bewusst austarieren (parametrierbar, K1).
- **Lokal vs. Cloud:** offen; bei Fernzugriff Authentifizierung/Autorisierung/Verschlüsselung (NF-07).

---

## 9. Meilensteine & Pflichtdokumente

| Meilenstein | Zeitpunkt | Zentrale Deliverables |
|---|---|---|
| M1 | Ende Woche 1 | Stakeholder-/Nutzermodell, erste Anforderungen, Schwellenwerte, Backend-Konzept, dokumentierte Konflikte |
| M2 | Ende Woche 2 | Funktionierende Teilmodule, **API & Datenmodell final**, erste Integration, Testprotokolle |
| M3 | Ende Woche 3 | Vollständiger Prototyp, Live-Demo, Abschlusspräsentation, Reflexion |

**Pflichtdokumente** (laut `Prüfungsleistung Anforderungen.txt`): Stakeholderanalyse, Lastenheft, Systemkontext,
Sensorstudie/-auswahl/Messkonzept (G1), **Datenmodell, API-Dokumentation, Vereisungslogik (G2)**,
UI-/Alarm-/Integrationskonzept (G3), Entscheidungslogbuch (laufend), Testprotokoll, Abschlusspräsentation.

---

## 10. Hinweise für Agenten

- **Scope respektieren:** G2 = Backend. Sensorik/Frontend **nicht** mitkonzipieren — nur die API-Schnittstelle definieren.
- **Anforderungs-/Konzeptdokumente beachten:** `Usecase-quick.md`, `Schwellenwerte.md`, `Backend-Konzept.md`,
  `Tasks+Projektplan.md` (gemeinsame IDs FA/NF/RB/AE/K, Tasks P#.#).
- **Belegbasiert arbeiten:** keine erfundenen Schwellenwerte/Quellen; Unsicheres kennzeichnen; bei Bedarf nachfragen.
- **Session-Recap:** Claude Code → `/ck:resume`; Kimi → aktuellste `recap_YYYY-MM-DD.md` unter `C:\Users\LucasVöhringer\.kimi\.recap\`.
- **Deutsch verwenden.** Sicherheitskritisches Ingenieursprojekt, kein normales Webprojekt.
- Abweichungen als **[DEVIATION]** markieren und begründen.
