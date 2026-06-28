# Meilenstein-Tracker — Stand 2026-06-27

> Quellen: `02-Arbeitsdokumente/Tasks+Projektplan.md` (P0–P6, M1–M3),
> `erinnerung/task-prioritaet-aktuell.md` (M2-Kern erreicht),
> `gh pr list --state all --limit 100`.

| Meilenstein | Soll-Termin | Ist-Stand | Ampel | Blocker | Nächste Aktion |
|---|---|---|---|---|---|
| **M1** Setup & Anforderungen | Ende Woche 1 | Stack final (E-35), Repo-Struktur, Contract-Draft, Stakeholder-/Nutzermodell, erste Anforderungen abgegeben. | 🟢 | — | Abgeschlossen. |
| **M2** API/Datenmodell final + lauffähige Teilmodule | Ende Woche 2 | **M2-Kern erreicht:** T0-Slice läuft E2E (`GET /v1/assessment/current`), API v1.0 eingefroren, Datenmodell final, NF-01 durch Integrationstest nachgewiesen. Offen: Alarm-Endpunkte (SSE/Resync/Ack), Prognose (#119), Defekt-Erkennung (#128), Real-DB (#129), Write-Auth (#130). | 🟡 | Offene PRs blocken den vollständigen M2-Abschluss; Wochenend-Freigaben nötig. | Review/Merge: #119, #123, #128, #129, #130; `AlarmRepository` (A2) starten. |
| **M3** Prototyp + Live-Demo + Reflexion | Ende Woche 3 | Voraussetzung M2-Kern steht. E2E mit G1/G3, Testprotokoll, Demo-Skript, Reflexion noch offen. | 🟡 | Hängt am M2-Abschluss; verbleibende Zeit ~1 Woche. | Sobald M2-PRs gemergt: DTB-17/23 E2E-Integration + DTB-30/44 Testprotokoll/Demo beginnen. |

## Offene PRs mit Meilenstein-Relevanz

| PR | Branch | Thema | Status | Blocker / Hinweis |
|---|---|---|---|---|
| #119 | `feat/dtb-33-forecast-producer` | 30-min-Prognose-Producer (FA-06, M3-Pflicht) | **Review-Fixes gepusht** | Nochmals Review/Merge. |
| #123 | `feat/dtb-61-sse-alarm-stream` | SSE-Alarm-Stream (DTB-61, Strang A) | **OPEN** | Alarm-Repository/DB-DDL existiert; kann parallel. |
| #128 | `feat/dtb-20-defekt-erkennung` | Defekt-Erkennung (DTB-20, Strang B) | **OPEN** | Ingest-Wiring offen. |
| #129 | `feat/db-finalisierung-real-mariadb` | Reale MariaDB-Verifikation (DTB-53–56) | **OPEN** | Hardware/DB-Weg für M3/Demo offen. |
| #130 | `feat/dtb-63-write-auth-redo` | Write-Auth schreibende `/v1`-Endpoints (NF-07) | **OPEN** | Blocker für Ack/Config-Schreiben. |
| #125 | `docs/ganter-entscheidungslog-dtb20` | Entscheidungslog DTB-20 | **OPEN** | Doku, nicht kritisch. |
| #117 | `docs/erinnerung-arash-2026-06-27` | Session-Stand Arash | **OPEN** | Doku, nicht kritisch. |

## Kurz-Interpretation

- **M2 ist inhaltlich gerettet** — der kritische Pfad (T0-Slice, NF-01, Contract) steht auf `main`.
- **Risiko M3:** Zeitbudget knapp, aber die offenen Arbeiten sind überwiegend parallelisierbar (Alarme, Prognose, Auth, Defekt-Erkennung, Real-DB). Solange die Wochenend-Reviews nicht schleifen, bleibt M3 machbar.
- **Empfehlung:** Heute/So schnell die offenen PRs durchwinken oder Feedback geben, damit Montag die E2E-Integration mit G1/G3 starten kann.
