# Persönliches Entscheidungslog — Andi (G2)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-25
> **Autor:** Andi · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

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
