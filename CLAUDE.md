# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Was dieses Verzeichnis ist (Stand: noch kein Code)

Dies ist **kein Software-Repository**, sondern das **Projekt-Briefing** für den Projektkurs
„Vereisungserkennung am Flughafen ANR". Es enthält bisher nur drei PDF-Quelldokumente — der
eigentliche Prototyp ist noch zu bauen. Eine künftige Claude-Instanz entwickelt das System hier
voraussichtlich von Grund auf.

> Umgebungs-Hinweis: PDFs lassen sich hier nur per Text-Extraktion lesen
> (`pdftotext -layout "<datei>.pdf" -`). Bild-Rendering über das Read-Tool schlägt fehl, weil
> `pdftoppm` nicht im PATH liegt.

Quelldokumente:
- `Handreichung für die Studis.pdf` — Aufgabenstellung, Rollen, Gruppen, Meilensteine, Bewertungskriterien
- `Hintergrundgeschichte.pdf` — **bewusst widersprüchliches/unvollständiges Rohmaterial** (E-Mails,
  Chats, Protokolle, Vorfallberichte). Primärquelle für das Requirements Engineering
- `Wochenübersicht.pdf` — 3-Wochen-Zeitplan mit Meilensteinen M1–M3

## Kernauftrag des Projekts

Prototypisches System zur **Erfassung und Bewertung von Vereisungsbedingungen** an einem
Regionalflughafen in Mittelgebirgslage. Fünf Komponenten:

1. Sensordatenerfassung
2. Datenverarbeitung
3. Backend-System
4. Visualisierung (Frontend)
5. Vereisungsbewertung (Entscheidungslogik)

**Zentrale Eigenheit:** Es existiert keine saubere Spezifikation. Das Lastenheft muss aus dem
widersprüchlichen Material in `Hintergrundgeschichte.pdf` **erst hergeleitet** werden — das ist
ausdrücklich Teil der Aufgabe und der Bewertung. Das Briefing nie als fertige Spec behandeln.

## Harte Randbedingungen & Designentscheidungen (aus der Hintergrundgeschichte abgeleitet)

Diese Punkte ergeben sich nur aus dem Querlesen mehrerer Quellen und prägen Architektur und
Entscheidungslogik maßgeblich:

- **Sicherheitskritisch — keine Automatik-Freigabe:** Das System darf die Startbahn NIE automatisch
  freigeben oder sperren. Die Verantwortung bleibt beim Menschen (Aussage Sicherheitsbeauftragte).
  Das System ist Entscheidungs*unterstützung*, kein Aktor.
- **Lufttemperatur reicht nicht:** Beide dokumentierten Vorfälle scheiterten an reiner
  Lufttemperatur-Messung — Fehlalarm bei −2,1 °C (kein Eis) und übersehene Eisbildung bei +1,2 °C.
  Tatsächlich relevant: **Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Niederschlagsart**.
- **Zielkonflikt Fehlalarm vs. Sicherheit:** Betrieb/Controlling wollen unnötige Sperrungen
  vermeiden (Kosten); die Sicherheit sagt „Lieber zehn Fehlalarme als ein vereistes Flugzeug".
  Diese Abwägung ist der Kern der Bewertungslogik und muss bewusst parametrierbar sein.
- **Vorhersage statt Momentaufnahme:** Fluglotsen brauchen ≥ 30 min Vorlaufzeit, nicht nur den
  aktuellen Ist-Zustand.
- **Wartbarkeit der Sensoren:** Vorfeld-Sensoren werden regelmäßig durch Räum-/Streufahrzeuge und
  Flugbetrieb beschädigt — Robustheit und Austauschbarkeit einplanen.
- **Betriebsmodell offen:** IT tendiert zu lokalem Betrieb (Cloud „macht Probleme"), wünscht aber
  Fernzugriff. Diese Entscheidung begründet dokumentieren statt vorwegnehmen.
- **Budgetdruck:** Controlling lehnt teure Experimente ab; Referenzsensor WX-500 ~4.800 €/Stück
  (misst Oberflächentemperatur, Feuchte, Eisindikator). Sensoranzahl und -auswahl begründen.
- **Risiken R1–R5:** falsche Sensordaten, Kommunikationsausfall, Stromausfall, nicht erkannte
  Vereisung, zu viele Fehlalarme — bei Architektur und Entscheidungslogik adressieren.

## Arbeitsorganisation (3 Gruppen, bewusster Methodenvergleich)

- **Gruppe 1 — Sensorik & Daten** (Wasserfall): reale Sensoren recherchieren, Datenblätter
  analysieren, Auswahl begründen, prototypische Messung
- **Gruppe 2 — Backend & Entscheidungslogik** (Wasserfall): Datenmodell, API, Speicherung,
  Vereisungsbewertung
- **Gruppe 3 — Frontend & Integration** (Scrum): Nutzeroberfläche, Visualisierung, Alarmierung,
  Gesamtsystemintegration

Die Schnittstelle zwischen den Gruppen ist die **API/das Datenmodell** (Gruppe 2) — laut Zeitplan
bis Ende Woche 2 final, damit Sensorik und Frontend dagegen integrieren können.

## Deliverables & Meilensteine

Pflicht-Dokumentation: **versioniertes Lastenheft**, Architekturdiagramm, API-Beschreibung,
Sensordatenanalyse, **Entscheidungslogbuch** (geprüfte Alternativen, Begründungen, offene
Unsicherheiten).

- **M1 (Ende Woche 1):** Stakeholderanalyse, erste Anforderungen, Sensorkandidaten + Datenblätter,
  Architekturideen, dokumentierte Konflikte & offene Anforderungen
- **M2 (Ende Woche 2):** funktionierende Einzelmodule, dokumentierte API & Datenmodell, erste
  End-to-End-Teilintegration, getestete Sensor-/Datenpipeline
- **M3 (Abschluss):** vollständiger Prototyp, Live-Demonstration, Abschlusspräsentation, validierte
  Vereisungslogik, Reflexion + Methodenvergleich (Wasserfall vs. agil)

Bewertet werden vor allem: Nachvollziehbarkeit technischer Entscheidungen, Qualität der
Datenanalyse, Umgang mit widersprüchlichen Anforderungen, technische Umsetzung, Teamorganisation,
Reflexion.

## Konventionen

- Sprache aller Artefakte: **Deutsch**.
- Noch **kein Versionskontrollsystem** initialisiert. Da das Lastenheft versioniert sein soll, ist
  ein frühes `git init` sinnvoll.
- Build-/Test-/Lint-Kommandos und Tech-Stack existieren noch nicht — die Stack-Wahl ist eine offene
  Entscheidung und gehört ins Entscheidungslogbuch.
