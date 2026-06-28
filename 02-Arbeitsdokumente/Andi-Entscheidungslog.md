# Persönliches Entscheidungslog — Andi (G2)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-28
> **Autor:** Andi · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

## 2026-06-28 — DTB-34: Review-Findings nachgereicht (Offset-Oberlimit, Validierung zentralisieren, Spec-Freeze)

- **Kontext/Task:** Nachträgliche Review-Findings zu DTB-34 (keine CRITICAL/HIGH, ein MEDIUM, drei LOWs).

- **Entscheidung:**
  - Validierungslogik von `get_between` in `src/storage/repository.py` in die Modul-Funktion `_validate_get_between_args()` ausgelagert; sowohl `InMemoryReadingRepository` als auch `ReadingRepository` rufen sie auf (MEDIUM).
  - Fehlermeldungen der Validierung auf API-Parameternamen `'from'`/`'to'` umgestellt (statt internen `from_dt`/`to_dt`), weil `ValueError` direkt als 400-Response an G3 weitergegeben wird (LOW).
  - `offset` in `GET /v1/readings` API-seitig auf `0 … 100_000` begrenzt (`le=100_000` in FastAPI + `maximum: 100000` in `openapi.yaml`); verhindert extreme Pagination-Anfragen, die MySQL intern materialisieren lassen (LOW).
  - Additive Ergänzungen in `openapi.yaml` (`offset`-Parameter, 503-Response für `/v1/readings`) dokumentiert: keine Breaking Changes, sondern Ausfüllen einer T1-Lücke im eingefrorenen Vertrag v1.0. Architekten-Review war einverstanden (LOW).

- **Begründung:**
  Die zentrale Validierungsfunktion vermeidet Copy-Paste-Drift zwischen InMemory- und PyMySQL-Implementierung. Die API-freundlichen Fehlermeldungen erhöhen die Verständlichkeit für G3-Consumer. Das `offset`-Oberlimit ist ein vorsorglicher Schutz vor DoS-artigen Anfragen bei wachsender Tabelle. Die Spec-Änderungen sind **additiv** (neue optionale Felder/Responses), kein Breaking Change — G3-Clients, die `offset` nicht senden, verhalten sich unverändert; die 503-Response dokumentiert nur bereits implementiertes Verhalten.

- **Alternativen:**
  - **Validierung im Endpoint statt Repository** — verworfen, weil das Repository-Interface unabhängig von der API genutzt wird (Tests, Poller) und dort konsistente Regeln sinnvoll sind.
  - **Fehlermeldungen im Repository belassen (from_dt/to_dt) und im Endpoint mappen** — verworfen, weil es mehr Code ohne Mehrwert bedeutet; `get_between` wird ausschließlich vom Historien-Endpoint konsumiert.
  - **Offset-Oberlimit auch im Repository erzwingen** — verworfen, weil es eine API-/Verbraucher-Regel ist, keine Persistenz-Regel; das Repository prüft nur `offset < 0`.

- **Ergebnis/Status:** Umgesetzt auf `dtb-34`. Tests + ruff grün. PR #131 reviewbereit.

## 2026-06-27 — DTB-34: Historien-Endpoint GET /v1/readings

- **Kontext/Task:** DTB-34 (Historie `GET /v1/readings?from=&to=`) · FA-03 (Messwerte persistent mit Zeitstempel) · Backend-Konzept §6a/§7 · E-35 (rohes PyMySQL). Ziel: G3 kann gespeicherte Messwerte abfragen.

- **Entscheidung:**
  - Repository-Interface `Repository` um `get_between(sensor_id, from_dt, to_dt, limit, offset, order)` erweitert; Implementierung in `InMemoryReadingRepository` und `ReadingRepository` (parametrisiertes PyMySQL).
  - Query dynamisch aus festen WHERE-Fragmenten und parametrisierten Werten gebaut (`sensor_id = %s`, optional `measured_at >= %s` / `<= %s`), Sortierung und Pagination ebenfalls parametrisiert.
  - Separates Wire-Schema `ReadingResponse` in `src/model/schemas.py` eingeführt, um internes `Reading` (id optional) vom Contract (id required) zu trennen — analog `AssessmentCurrent`.
  - Endpoint `GET /v1/readings` in `src/api/v1.py` implementiert; Query-Parameter: `from`/`to` (UTC, inklusiv), `sensor_id` (Default `anr-rwy-01`), `limit` (1–1000), `offset` (≥0), `order` (`asc`/`desc`).
  - `openapi.yaml` um `offset`-Parameter erweitert; ursprüngliche T1-Spezifikation enthielt nur `limit`.
  - Fail-safe: DB-Ausfall → 503 `Error{code,message}`; ungültige Parameter (z. B. `from` nach `to`) → 400; no-store Header auf allen Pfaden.

- **Begründung:**
  Die Aufgabenstellung forderte Pagination mit `limit/offset`. Die vorhandene `openapi.yaml`-Definition für `/v1/readings` enthielt zwar `limit`, aber kein `offset`. Da der Endpoint in `API_FROZEN_v1.md` als „reserviert, Form folgt mit openapi.yaml" gekennzeichnet und T1 noch nachjustierbar ist, habe ich `offset` ergänzt, um der DoD gerecht zu werden. Die dynamische Query vermeidet SQL-Injection (nur Werte parametrisiert, WHERE-Fragmente sind Konstanten) und nutzt den vorhandenen Index auf `measured_at`. Ein separates Wire-Schema verhindert, dass die API zukünftig interne Modelländerungen (z. B. neues Feld) automatisch an G3 weitergegeben wird, ohne dass dies am Contract geprüft wird.

- **Alternativen:**
  - **Nur `limit` wie in openapi.yaml; kein `offset`** — verworfen, weil die DoD explizit `limit/offset` nennt und `offset` für eine brauchbare Pagination nötig ist.
  - **Internes `Reading`-Schema direkt als Response verwenden** — verworfen, weil `Reading.id` optional ist und der Contract `id` als required definiert.
  - **Zwei statische SQL-Strings (mit/ohne Zeitfenster)** — verworfen, weil vier Kombinationen (kein/from/to/beide) unübersichtlich wären; die dynamische Variante mit festen Fragmenten bleibt sicher.
  - **Naive Zeitstempel im Endpoint implizit als UTC interpretieren** — verworfen, weil der Contract ISO-8601/UTC verlangt; naive Zeitstempel werden an das Repository weitergegeben, das einen `ValueError` wirft → Endpoint liefert 400.

- **Ergebnis/Status:** Umgesetzt auf `dtb-34`. 540 Tests grün, 30 skipped (DB-Integration), ruff sauber, Coverage 90 %. Offen: Review + Merge nach Zustimmung durch Lucas.

## 2026-06-25 — DTB-13: Stale + Plausibilität als DB-agnostisches Fail-safe

- **Kontext/Task:** DTB-13 (Plausibilität + Stale-Erkennung) · NF-01 (Fail-safe) · E-34
  (Kaskade + UNKNOWN) · Schwellenwerte.md §3. Ziel: Datenqualität vor der Bewertung erkennen
  und bei Problemen nie GRÜN ausgeben.

- **Entscheidung:**
  - Stale-Logik, Sprung- und Flatline-Erkennung in `src/assessment/failsafe.py` bundeln.
  - Stale-Schwelle auf **120 s** parametrieren (nicht 180 s aus Schwellenwerte.md §3),
    um schneller auf Ausfälle reagieren zu können.
  - Plausibilität wird **paarweise** geprüft: aktuelles Reading gegen das vorherige
    (`Repository.get_latest()`), da das Interface schon für Stale benötigt wird.
  - Flatline wird mit einer **Epsilon-Toleranz** (`flatline_epsilon_c = 0,01 °C`) geprüft,
    um Sensorrauschen zu tolerieren.
  - Stale, DB-Ausfall und unplausible Daten bleiben ** drei getrennte Fälle**, liefern aber
    gemeinsam `RiskLevel.UNKNOWN`.

- **Begründung:**   Die Fail-safe-Logik sollte vor der eigentlichen Vereisungsbewertung erkennen, ob die übermittelten Daten überhaupt verwertbar sind. NF-01
   verlangt, dass das System bei unsicheren oder veralteten Daten nie GRÜN anzeigt; E-34 hat mit RiskLevel.UNKNOWN einen eigenen            
   Fail-safe-Zustand eingeführt, der genau diesen Fall abbildet. Indem ich Stale-Daten, DB-Ausfall und unplausible Werte als drei getrennte 
   Fälle erfasse, aber alle auf UNKNOWN abbilde, bleibt die Fehlerursache für Audit/Log nachvollziehbar, während G3 ein eindeutiges Ergebnis
   erhält.                                                                                                                                  
                                                                                                                                            
   Die Wahl von 120 s für stale_timeout_s habe ich bewusst konservativer als die 180 s aus Schwellenwerte.md §3 gewählt, weil das System bei
   ausgefallenen oder hängenden Sensoren möglichst schnell in den sicheren Zustand wechseln soll. Die paarweise Plausibilitätsprüfung       
   (aktuelles Reading gegen Repository.get_latest()) habe ich gewählt, weil das Repository-Interface dadurch schmal bleibt und DTB-13 als   
   Enabler für DTB-28 nicht zusätzlich blockiert. Für die Flatline-Erkennung habe ich eine kleine Epsilon-Toleranz (0,01 °C) eingeführt, um 
   reales Sensorrauschen zu tolerieren und False-Positives zu vermeiden. 

- **Alternativen:**
  - **Stale-Schwelle = 180 s (3 × Messintervall)** wie in Schwellenwerte.md §3 — verworfen,
    da 120 s konservativer ist und früher auf veraltete Daten hinweist.
  - **Plausibilität über Sliding-Window mit mehreren Readings** — verworfen, weil das
    Repository-Interface aktuell nur `get_latest()` vorsieht und DTB-13 ein Enabler für
    DTB-38 sein soll, ohne DTB-28 zu blockieren.
  - **Flatline ohne Epsilon (exakt gleiche Werte)** — verworfen, weil reales Sensorrauschen
    sonst zu viele False-Positives erzeugen würde.

- **Ergebnis/Status:** Umgesetzt in Commit `8901068` auf `feat/dtb-13-stale-erkennung`.
  121 Tests grün, ruff sauber. Offen: PR nach Genehmigung durch Lucas.

## 2026-06-23 — DB-Zugriff: PyMySQL statt SQLAlchemy/Alembic

- **Kontext/Task:** P1.1 / DTB-12 (Datenmodell), E-35 (Stack-Entscheidung MySQL/MariaDB). Wir müssen im G2-Backend Daten in MySQL/MariaDB persistieren. Die Architektur-Entscheidung E-35 sah bereits PyMySQL + handgeschriebenes `schema.sql` vor; ich habe diese Wahl nochmals bewusst geprüft.

- **Entscheidung:** Wir bleiben bei **PyMySQL** mit selbstgeschriebenem SQL. **Kein SQLAlchemy, kein Alembic.**

- **Begründung:**
  - Das Team kennt SQL bisher nur wenig und will SQL aktiv lernen.
  - Wir planen keine Änderung der Datenbank-Technologie und keine nachträglichen Schemaänderungen.
  - SQLAlchemy und Alembic würden einen zusätzlichen Lernaufwand bedeuten, den wir aktuell als unnötig kompliziert erachten.
  - Mit PyMySQL behalten wir die volle Kontrolle über die SQL-Queries und vermeiden ORM-„Magie".

- **Alternativen:**
  - **SQLAlchemy ORM + Alembic:** Weniger Boilerplate, automatisierte Migrationen, bessere FastAPI-Integration — aber zusätzlicher Lernaufwand für ORM, Sessions und Migrationstool.
  - **SQLAlchemy Core (ohne ORM):** Mittlere Abstraktion — wurde verworfen, weil auch hier der zusätzliche Framework-Einarbeitungsaufwand dem Lernziel „SQL direkt verstehen" widerspricht.

- **Ergebnis/Status:** Entscheidung bestätigt E-35. Umgesetzt in DTB-12 (`migrations/schema.sql`, `src/model/schemas.py`, PyMySQL in `requirements.txt`).

- **Risiko/Nachbedingung:** Falls doch Schemaänderungen nötig werden, müssen wir diese manuell in `schema.sql` bzw. separaten Delta-Skripten versionieren.
