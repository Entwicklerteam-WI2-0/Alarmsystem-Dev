# Persönliches Entscheidungslog — Leon Hartling (G2, Database-Engineer)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-23
> **Autor:** Leon Hartling · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

## 2026-06-23 — DB-Vorgabe MySQL/MariaDB annehmen statt anfechten
- **Kontext/Task:** P0.1 (Stack/Persistenz) · E-29 (GL-Vorgabe) · NF-05/NF-10 (Wartbarkeit/Betrieb).
  Quelle: `02-Arbeitsdokumente/Surprise Anforderungen.txt` (Mitteilung der Geschäftsleitung).
- **Entscheidung:** Die Persistenz läuft durchgängig auf **MySQL/MariaDB** (dev = prod). Ich nehme die
  GL-Vorgabe **als gesetzt an** und fechte sie **nicht** an.
- **Begründung:** *(eigene Formulierung — bitte prüfen/anpassen)* Die IT des Flughafens betreibt ihre
  bestehenden betrieblichen Anwendungen bereits auf MySQL und hat dort die Erfahrung/Kompetenz. Ein anderer
  DB-Stack (z. B. PostgreSQL) hätte bedeutet, dass sich **die dortige IT an uns** anpassen müsste — das
  wollten wir dem Betreiber nicht aufzwingen und auch **nicht weiter eskalieren**. Die Vorgabe gewichtet
  langfristige **Wartbarkeit und zuverlässigen Betrieb** höher als neue Technologie; für die moderate
  Sensordatenrate eines Regional-Flughafen-Prototyps gibt es **keinen schwerwiegenden technischen
  Gegengrund** gegen MySQL/MariaDB (`Backend-Konzept §6a`). Annehmen statt anfechten spart im 3-Wochen-
  Projekt Zeit und vermeidet einen Konflikt mit dem Betreiber.
- **Alternativen:**
  - **PostgreSQL / TimescaleDB** — verworfen: im Haus nicht etabliert, widerspricht dem GL-Kriterium
    „bestehende Kompetenz"; hätte Anpassung auf Betreiberseite erzwungen. *(E-29)*
  - **SQLite durchgängig** — verworfen: widerspricht der GL-Vorgabe, nicht für Server-/Mehrbenutzer­betrieb
    gedacht. *(E-29)*
  - **SQLite im Dev, MySQL erst in Prod** — verworfen: **SQL-Dialekt-Drift** (AUTO_INCREMENT, JSON-Typ,
    DATETIME-Semantik) fällt erst spät und teuer auf; „dev = prod" vermeidet den Migrationsbruch.
- **Ergebnis/Status:** umgesetzt — gesamter G2-Stack auf MySQL/MariaDB festgelegt (Stack-Doc
  `Stack-Entscheidung-P0.1.md`). *Hinweis zur Abgrenzung:* Die DB-**Wahl** selbst ist extern gesetzt
  (Architekten-Entscheidung E-29, Lucas); **meine** eigene Entscheidung ist die **bewusste Annahme** der
  Vorgabe sowie deren konkrete Umsetzung (siehe nächster Eintrag).

## 2026-06-23 — Schema als handgeschriebenes `schema.sql` (DDL) statt Alembic/ORM
- **Kontext/Task:** Setup-Task „schema.sql (DDL) gegen MariaDB einspielen (ersetzt Alembic)" ·
  E-35 · Datenmodell: `Backend-Konzept §4` + DTB-12. Datei: `04-Source-code/migrations/schema.sql`.
- **Entscheidung:** Das DB-Schema wird als **handgeschriebenes, idempotentes `schema.sql`**
  (`CREATE TABLE IF NOT EXISTS`, Enums als `VARCHAR` + `CHECK`) gepflegt und direkt gegen MariaDB
  eingespielt — **kein Alembic**, **kein ORM** (rohes PyMySQL hinter Repository-Pattern).
- **Begründung:** *(eigene Formulierung — bitte prüfen/anpassen)* Für ~6 stabile Tabellen ist ein
  Migrationsframework (Alembic) + ORM **Overkill**: mehr bewegliche Teile, höhere Lernkurve für ein
  ~2.-Semester-Team, ohne realen Mehrwert in einem 3-Wochen-Prototyp. Ein einziges, gut kommentiertes
  `schema.sql` ist **vollständig überblickbar**, versionierbar und idempotent wieder einspielbar. Den
  Injection-Schutz, den ein ORM mitbringt, sichere ich stattdessen über **parametrisierte Queries (Pflicht)
  + Review**. Der kritische Pfad (Bewertungslogik) bleibt ohnehin **DB-frei**.
  *Offen / noch nicht festgezurrt:* Das endgültige Datenmodell hängt noch an den **finalen Schwellenwerten**
  und daran, **welche Daten** wir von G1 genau erhalten — bis dahin ist `schema.sql` bewusst anpassbar
  gehalten (dieser Eintrag wird ggf. später aktualisiert).
- **Alternativen:**
  - **Alembic (Migrationsframework)** — verworfen: unnötig bei stabilem `schema.sql` für 6 Tabellen. *(E-35)*
  - **SQLAlchemy ORM** — verworfen: Overkill + Lernkurve für ein 3-Wochen-Anfängerprojekt. *(E-35)*
  - **SQLAlchemy Core** (Injection-Schutz ohne volle ORM-Last) — verworfen zugunsten maximaler Einfachheit;
    Schutz stattdessen über parametrisierte Queries + Review. *(E-35)*
- **Ergebnis/Status:** umgesetzt — `04-Source-code/migrations/schema.sql` liegt vor (threshold_set, reading,
  assessment u. a.), idempotent und gegen MariaDB einspielbar. Datenmodell bleibt bis zur Schwellenwert-/
  G1-Daten-Klärung **offen für Anpassung**.
