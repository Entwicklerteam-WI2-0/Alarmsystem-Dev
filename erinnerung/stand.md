# Aktueller Stand

> Stand: 2026-06-21 · Pflege: Lucas (Architekt). Beim Sitzungsstart von `uni:start` gelesen.

## Woran wir gerade arbeiten
- **G2 Backend (Alarmsystem ANR):** Übergang Woche 2. **Projektplan + Jira-Backlog (Projekt DTB)** steht:
  9 Epics / 43 Tasks (DTB-1..DTB-52) + 43 "Blocks"-Abhängigkeitslinks. Begleitdoc:
  `02-Arbeitsdokumente/Projektplan-Jira-Backlog-G2.md`.
- Stack **T0 (FastAPI/SQLite/HTTP) als gesetzt** behandelt (E-08 formal nachziehen → DTB-2). Noch **kein `src/`** —
  Scaffolding (P0 / Epic E-01) ist überfällig.

## Als Nächstes (kritischer Pfad)
1. **P0/Scaffolding heute** abschließen (DTB-1: DTB-2/50/51/52).
2. **Contract-first**: API + Datenmodell (E-02 / DTB-7) + Seam-Sync mit G1+G3 bis Di → M2.
3. **T0 Vertical Slice** (E-03 / DTB-8): assessment-Kern + beide Vorfall-Tests + Fail-safe (≥80 % Coverage).

## Offene Punkte / Blocker
- **M2 (Ende Woche 2) kritisch:** nur 1 echter Backend-Dev (Lucas) auf 7 kritischen Tasks → Petzold früh
  einbinden, P3 bewusst nach Woche 3.
- **Echte Schwellenwerte von G1** ausstehend (~2 Tage) → `config/` parametrierbar halten, NIE hardcoden.
- **Review-Lücken (offen):** Systemkontext-Diagramm (Pflicht W1) ohne Task; NF-07-Auth für `POST /config`
  ohne Task; Config-Redundanz (E-05/E-07/E-09) konsolidieren.
- **Working-Tree uncommitted** (Plan-Doc + Entscheidungslog) — Push/PR nur nach Freigabe.
