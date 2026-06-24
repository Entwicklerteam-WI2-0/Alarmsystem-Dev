-- =====================================================================
-- G2 "Vereisung ANR" -- DB-Rechte-Matrix fuer den App-User (DTB-54, E-35).
-- Erzwingt append-only fuer audit_log/acknowledgement (NF-09) ueber DB-Rechte
-- statt Trigger. Reihenfolge: ERST schema.sql, DANN dieses Skript.
--
-- AUSFUEHREN ALS DB-ADMIN (root) -- GRANT/REVOKE brauchen GRANT OPTION.
-- KEIN CREATE USER, KEIN Passwort hier (NF-07): der App-User wird beim DB-Init
-- angelegt; dieses Skript vergibt NUR Rechte und ist wiederholbar (idempotent).
--
-- Platzhalter an .env koppeln:  DB_NAME=alarmsystem, DB_USER=alarm.
-- Host 'localhost' passt fuer native lokale MariaDB UND Pi via SSH-Tunnel
-- (getunnelte Verbindungen erscheinen serverseitig als 'localhost').
-- Anderer Verbindungsweg -> Host-Specifier anpassen.
-- =====================================================================

-- 1) Saubere Basis: jegliche DB-weiten Rechte entziehen, dann gezielt neu vergeben.
--    Hinweis: auf einem frisch angelegten User warnt MariaDB hier evtl.
--    "there is no such grant" -- unkritisch (es gab schlicht nichts zu entziehen).
REVOKE ALL PRIVILEGES, GRANT OPTION ON `alarmsystem`.* FROM 'alarm'@'localhost';

-- 2) Operative Tabellen: volle DML.
--    alarm braucht UPDATE fuer state-Uebergaenge (active -> acknowledged -> cleared).
GRANT INSERT, SELECT, UPDATE, DELETE ON `alarmsystem`.`reading`       TO 'alarm'@'localhost';
GRANT INSERT, SELECT, UPDATE, DELETE ON `alarmsystem`.`assessment`    TO 'alarm'@'localhost';
GRANT INSERT, SELECT, UPDATE, DELETE ON `alarmsystem`.`alarm`         TO 'alarm'@'localhost';
GRANT INSERT, SELECT, UPDATE, DELETE ON `alarmsystem`.`threshold_set` TO 'alarm'@'localhost';

-- 3) append-only (NF-09): NUR INSERT + SELECT -> kein UPDATE/DELETE moeglich,
--    der Audit-/Quittierungs-Trail bleibt unveraenderbar.
GRANT INSERT, SELECT ON `alarmsystem`.`audit_log`       TO 'alarm'@'localhost';
GRANT INSERT, SELECT ON `alarmsystem`.`acknowledgement` TO 'alarm'@'localhost';

FLUSH PRIVILEGES;

-- Verifikation (als Admin):   SHOW GRANTS FOR 'alarm'@'localhost';
-- Negativ-Test (als App-User, MUSS mit ERROR 1142 scheitern):
--   UPDATE audit_log SET actor='x' WHERE id=1;
