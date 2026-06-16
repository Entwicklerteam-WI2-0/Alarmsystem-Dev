# Entscheidungslog — Lucas (Systemarchitektur)

> **Zweck:** Nachvollziehbare Dokumentation der getroffenen Entscheidungen (Architektur, Organisation,
> Vorgehen) aus Sicht des Systemarchitekten — Pflichtdeliverable „Entscheidungslogbuch" und Grundlage
> für die Bewertung (Kriterium *Nachvollziehbarkeit technischer Entscheidungen*).
> **Format:** je Eintrag *Entscheidung · Begründung · verworfene Alternative · Bezug*. Lebendes Dokument.
> **Stand:** 16.06.2026 · **Bezug:** `Backend-Konzept.md`, `Schwellenwerte.md`, `Tasks+Projektplan.md`, `Usecase-quick.md`.

---

## A. Repository & Tooling

**E-01 — Ein konsolidiertes Arbeitsrepo (`Alarmsystem-Dev`, Org `Entwicklerteam-WI2-0`)**
- *Entscheidung:* Doku **und** Code in einem Team-Repo; frühere Ordner/Remotes (`technology-engeneering`, `Backend Sensor POC`) abgelöst.
- *Begründung:* Mehrere lokale Ordner auf wechselnde Remotes führten zu Push-Problemen und Divergenz (versehentlich vertauschter `.git`-Ordner). **Ein Repo = eine Wahrheit.**
- *Alternative:* getrennte Doku-/Code-Repos — verworfen: zu viel Sync-Overhead für 3 Wochen + unerfahrenes Team.

**E-02 — Ordnerstruktur `01-quellen / 02-Arbeitsdokumente / 03-abgaben`**
- *Begründung:* Read-only-Quellen, lebende Arbeitsdokumente und abgabefertige Stände sauber trennen → weniger „welche Datei gilt?".

**E-03 — Git-Workflow: Feature-Branch → PR → Review → `main`; `main` immer lauffähig; `CLAUDE.md`/`AGENTS.md` gitignored**
- *Begründung:* Reviewbarkeit + stabiler Hauptzweig; Agent-Instruktionsdateien sind lokal/tool-spezifisch, gehören nicht in die geteilte Historie.

## B. Architektur (Backend, G2)

**E-04 — 3-Schichten-Architektur; API/Datenmodell ist die *einzige* Naht und G2-Verantwortung**
- *Begründung:* Eine klar definierte Schnittstelle entkoppelt G1/G2/G3; laut Zeitplan bis Ende Woche 2 final.

**E-05 — Backend-Konzept strikt auf G2 begrenzt**
- *Begründung:* Ein früherer Entwurf konzipierte Sensorik (G1) und Frontend (G3) mit → Scope-Verwässerung. Jede Gruppe verantwortet ihren Teil; wir definieren nur den Vertrag.

**E-06 — Contract-first: API + Datenmodell zuerst einfrieren**
- *Begründung:* Der Vertrag entblockt G1 (Ingest) und G3 (Konsum) gleichzeitig und erlaubt paralleles Arbeiten — **kritischer Pfad**. Wird er spät fertig, blockiert er das Gesamtprojekt.

**E-07 — Ausbaustufen T0–T3; Vertical Slice (T0) zuerst end-to-end**
- *Begründung:* Den durchgehenden Faden (Sensor→Backend→Anzeige) früh beweisen — genau das, woran Studi-Projekte sonst in Woche 3 scheitern.

**E-08 — Technologiestack bewusst OFFEN; T0-Empfehlung FastAPI + SQLite + HTTP** *(Status: offen)*
- *Begründung:* Projektregel verlangt eine begründete Stack-Wahl statt Vorwegnahme; finale Wahl hängt an der Team-Kompetenz. SQLite/HTTP sind minimal genug für den Prototyp, FastAPI bietet schnelle REST + Validierung.
- *Alternative:* sofortige Festlegung — vertagt (s. Abschnitt G).

**E-09 — Sensorik-Pragmatik: ein günstiger echter Sensor für die Kerngröße + Simulator-Feed hinter *einer* Ingest-Schnittstelle**
- *Begründung:* Reale Vorfeld-Sensorik ist in 3 Wochen unrealistisch und teuer (Konflikte K3/K4). So läuft die Demo zuverlässig; echte Sensoren ersetzen die Simulation später 1:1.

## C. Vereisungs-Entscheidungslogik & Schwellenwerte

**E-10 — Bewertung über Oberflächentemperatur + Taupunkt-Abstand + Feuchte + Niederschlag; Lufttemperatur nur Kontext**
- *Begründung:* **Beide dokumentierten Vorfälle** scheiterten an reiner Lufttemperatur — Fehlalarm bei −2,1 °C (kein Eis) und übersehenes Eis bei +1,2 °C (Oberfläche kälter als Luft). Kernfehler des Altsystems.

**E-11 — 4-Stufen-Risikomodell (🟢🟡🟠🔴) mit konkreten Schwellen + Hysterese/Entprellung**
- *Begründung:* Klare, parametrierbare Kategorien statt eines unscharfen Einzelwerts; Hysterese verhindert Alarm-Flattern (ISA-18.2). Beide Vorfälle werden korrekt aufgelöst.

**E-12 — Sicherheits-Bias: verpasste Vereisung (FN) = 0 % Designziel, vor Fehlalarm-Vermeidung (FP < 1 %)**
- *Begründung:* Zielkonflikt K1; Sicherheitsbeauftragte: „Lieber zehn Fehlalarme als ein vereistes Flugzeug". Schwellen daher konservativ.

**E-13 — Oberflächentemp-Genauigkeit ±0,3 °C statt ±0,1 °C**
- *Begründung:* Die Entscheidungsgrenze liegt bei 0 °C; ±0,1 °C ist mit günstiger T0-Sensorik (IR/Kontakt) nicht erreichbar. ±0,3 °C ist ehrlich und ausreichend (K4). Lieber realistisch als unhaltbar.

**E-14 — Alle Schwellen parametrierbar (Config, kein Hardcode)**
- *Begründung:* Der Betriebspunkt (K1) muss am Testdatensatz + den 2 Vorfällen justierbar sein (NF-05); Default sicherheitsbetont.

**E-15 — RB-01 architektonisch erzwungen: System hat keinen Freigabe-/Aktor-Endpoint**
- *Begründung:* Harte Randbedingung — der Mensch ist letzte Instanz. Nicht nur Policy, sondern in der API-Struktur verankert (per Design unmöglich).

## D. Anforderungs-Engineering

**E-16 — ID-Taxonomie FA/NF/RB/AE + Konfliktanalyse K1–K9**
- *Begründung:* Rückverfolgbarkeit (Bewertungskriterium); Zielkonflikte werden explizit gemacht statt versteckt.

**E-17 — Schwellenwerte zweispaltig: Referenzwert (Realbetrieb) ↔ Prototyp-Abnahmekriterium**
- *Begründung:* Industrie-/Normwerte (z. B. Verfügbarkeit, MTBF) sind in 3 Wochen nicht verifizierbar. Ehrliche, prüfbare Prototyp-Kriterien verhindern unhaltbare Versprechen.

**E-18 — Unverifizierte Quellen explizit als ⚠ markiert**
- *Begründung:* Keine erfundene Präzision ins Lastenheft (Belegpflicht); fragwürdige Zitate vor Übernahme prüfen.

## E. Projektorganisation

**E-19 — Rolle Lucas = Systemarchitekt (bewusst nicht Teamlead)**
- *Begründung:* Höchster technischer Hebel (die API/Datenmodell-Naht steuert das ganze System); schützt die individuelle Note (Architektur erzeugt genau die bewertete „Nachvollziehbarkeit"); Skill-Fit; entkoppelt von der People-Management-Lotterie eines 12er-Teams mit hohem Ausfallrisiko.

**E-20 — Kanban: 5 Epics nach Rollen; Spalten = Workflow-Zustände; jede Task mit Owner/DoD/Größe + WIP-Limit**
- *Begründung:* Vorstrukturierte, self-service-fähige Tasks reduzieren Abstimmungslähmung im unerfahrenen Team. Kategorien als Labels, nicht als Spalten (häufige Anfänger-Falle vermieden).

**E-21 — Phasen P0–P6 an M1–M3; Priorisierung Muss = P0–P3 + P5, Soll = P4, Kann = P6**
- *Begründung:* Definiert das benotete Minimum realistisch für 3 Wochen + ~45 % Non-Performer; T3-Erweiterungen sind Bonus, kein Risiko.

**E-22 — Non-Performer-Entkopplung: kritischen Pfad eng besetzen, abgegrenzte Tasks verteilen**
- *Begründung:* Contract (P1) und Kernlogik (P2.4) auf die verlässlichsten Köpfe; parallelisierbare Tasks an den Rest — ein Ausfall darf nie die Naht blockieren.

## F. KI-Einsatz im Team

**E-23 — KI-Onboarding-Dokument für ChatGPT/Gemini (`Agents-gpt-gemini.md`)**
- *Begründung:* Fremd-KIs erfinden sonst Schwellenwerte, konzipieren alle Gruppen mit oder antworten auf Englisch. Das Briefing setzt: Projektdokumente = Ground Truth, keine Halluzinationen, Scope- und Sprachdisziplin.

---

## G. Offene Entscheidungen (bewusst vertagt)

| Offen | Bezug | Warum vertagt |
|---|---|---|
| Konkreter Stack (Sprache/Framework/DB/Protokoll) | E-08, AE | hängt an Team-Kompetenz; T0-Empfehlung steht, finale Wahl folgt |
| Lokal vs. Cloud + Fernzugriff | AE-01/AE-02 | Quelle unentschieden; im Logbuch zu begründen |
| Eisindikator: Proxy vs. echter Sensor vs. Simulation | K3/K4 | Budget- und Messgüte-abhängig |
| Anbindung an das HS-gestellte zentrale Remote | E-01 | sobald die Hochschule es bereitstellt |

> **Pflege:** Bei jeder neuen Festlegung einen `E-xx`-Eintrag ergänzen; offene Punkte aus G nach Entscheidung
> nach oben überführen. So bleibt der rote Faden „Warum haben wir das so gebaut?" jederzeit nachvollziehbar.
