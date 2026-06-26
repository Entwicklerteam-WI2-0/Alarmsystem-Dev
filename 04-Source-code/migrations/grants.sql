-- =====================================================================
-- G2 "Vereisung ANR" -- DB-Rechte-Matrix fuer den App-User (DTB-54, E-35).
-- Erzwingt append-only fuer die unveraenderlichen Tabellen (reading, assessment,
-- audit_log, acknowledgement; NF-09) ueber DB-Rechte statt Trigger.
-- Reihenfolge: ERST schema.sql, DANN dieses Skript.
--
-- WARTUNG (Drift-Schutz, DTB-54): Die Tabellenliste unten spiegelt schema.sql.
-- Wird dort eine NEUE Tabelle ergaenzt, MUSS sie hier nachgezogen werden
-- (REVOKE in Block 1b + passender GRANT in Block 2 oder 3) -- sonst hat der
-- App-User darauf keinerlei Rechte und Schreibzugriffe schlagen still fehl.
--
-- AUSFUEHREN ALS DB-ADMIN (root) -- GRANT/REVOKE brauchen GRANT OPTION.
-- KEIN CREATE USER, KEIN Passwort hier (NF-07): der App-User wird beim DB-Init
-- angelegt; dieses Skript vergibt NUR Rechte und ist wiederholbar (idempotent).
-- KEIN "FLUSH PRIVILEGES": GRANT/REVOKE wirken in MariaDB sofort; FLUSH ist nur
-- bei direkter Manipulation der mysql.*-Tabellen noetig -- hier bewusst weggelassen.
--
-- DB-Name und User sind in diesem Skript hart kodiert (SQL kann keine .env lesen).
-- Bei abweichendem DB_NAME/DB_USER muessen alle Bezeichner manuell ersetzt werden.
-- Empfohlene Werte aus .env: DB_NAME=alarmsystem, DB_USER=alarm.
-- Host 'localhost' passt fuer native lokale MariaDB UND Pi via SSH-Tunnel
-- (getunnelte Verbindungen erscheinen serverseitig als 'localhost').
-- Anderer Verbindungsweg -> Host-Specifier anpassen.
-- =====================================================================

-- 1) Saubere Basis: jegliche DB-weiten Rechte entziehen, dann gezielt neu vergeben.
--    Hinweis: auf einem frisch angelegten User gibt MariaDB hier ERROR 1141 aus
--    ("there is no such grant") -- unkritisch, der mysql-Client setzt danach fort.
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.* FROM 'alarm'@'localhost';

-- 1b) Table-Level-Grants werden von ON `alarmsystem`.* NICHT widerrufen.
--     Daher pro Tabelle explizit zuruecksetzen, damit künftige Rechte-Änderungen
--     nicht stillschweigend auf alten Grants aufsetzen.
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`alarm`         FROM 'alarm'@'localhost';
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`threshold_set` FROM 'alarm'@'localhost';
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`reading`       FROM 'alarm'@'localhost';
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`assessment`    FROM 'alarm'@'localhost';
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`audit_log`     FROM 'alarm'@'localhost';
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.`acknowledgement` FROM 'alarm'@'localhost';

-- 2) Zustand/Config -- gezielte DML nur nach tatsaechlichem Bedarf (geringste Rechte):
--    alarm         -- INSERT/SELECT/UPDATE: UPDATE fuer state-Uebergaenge
--                     (active -> acknowledged -> cleared). KEIN DELETE.
--    threshold_set -- NUR INSERT/SELECT: Config-Saetze werden per neuem valid_from-Satz
--                     ersetzt (Supersession) -- nie ge-UPDATE-t, nie geloescht. Es gibt
--                     kein active_flag/superseded_at; UPDATE/DELETE bewusst NICHT vergeben,
--                     da assessment.fk_assessment_threshold (ohne ON DELETE) auf historische
--                     Saetze verweist -- Ueberschreiben/Loeschen wuerde den Audit-Trail brechen.
GRANT INSERT, SELECT, UPDATE ON `alarmsystem`.`alarm`         TO 'alarm'@'localhost';
GRANT INSERT, SELECT         ON `alarmsystem`.`threshold_set` TO 'alarm'@'localhost';

-- 3) append-only / unveraenderlich (NF-09): NUR INSERT + SELECT -> kein UPDATE/DELETE.
--    reading/assessment sind konzeptuell unveraenderlich (Roh-Messwerte von G1 bzw.
--    audit-fester Bewertungs-Snapshot, werden nach dem Schreiben nie geaendert);
--    audit_log/acknowledgement bleiben als Audit-/Quittierungs-Trail unveraenderbar.
GRANT INSERT, SELECT ON `alarmsystem`.`reading`         TO 'alarm'@'localhost';
GRANT INSERT, SELECT ON `alarmsystem`.`assessment`      TO 'alarm'@'localhost';
GRANT INSERT, SELECT ON `alarmsystem`.`audit_log`       TO 'alarm'@'localhost';
GRANT INSERT, SELECT ON `alarmsystem`.`acknowledgement` TO 'alarm'@'localhost';

-- Verifikation (als Admin):   SHOW GRANTS FOR 'alarm'@'localhost';
-- Negativ-Test (als App-User, MUSS je mit ERROR 1142 scheitern):
--   UPDATE audit_log SET actor='x' WHERE id=1;
--   UPDATE reading   SET air_temp_c=0 WHERE id=1;   -- reading jetzt append-only
