# Persönliches Entscheidungslog — Andi (G2)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-23
> **Autor:** Andi · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

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
