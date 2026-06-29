-- =====================================================================
-- G2 "Vereisung ANR" -- DB-Schema (DDL) - MariaDB/MySQL - utf8mb4
-- Handgeschrieben statt ORM/Alembic (E-35). Datenmodell: Backend-Konzept §4 + DTB-12.
-- Alle Zeitstempel UTC (DATETIME(3) ist in MySQL zeitzonenlos -> App speichert UTC).
-- Idempotent (CREATE TABLE IF NOT EXISTS). Reihenfolge wegen Fremdschluesseln beachten.
-- Enums als VARCHAR + CHECK (spiegeln src/model/enums.py).
-- =====================================================================

CREATE TABLE IF NOT EXISTS threshold_set (
  id          BIGINT       NOT NULL AUTO_INCREMENT,
  name        VARCHAR(128) NOT NULL,
  params      JSON         NOT NULL,
  valid_from  DATETIME(3)  NOT NULL,
  changed_by  VARCHAR(128) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reading (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  sensor_id      VARCHAR(64)  NOT NULL,
  measured_at    DATETIME(3)  NOT NULL,                 -- UTC, = G1 measured_at
  received_at    DATETIME(3)  NOT NULL,                 -- UTC, Poll-Zeit (G2)
  surface_temp_c DOUBLE       NOT NULL,
  air_temp_c     DOUBLE       NOT NULL,
  humidity_pct   DOUBLE       NOT NULL,                 -- Luftfeuchte
  pressure_hpa   DOUBLE       NULL,
  dew_point_c    DOUBLE       NULL,                     -- berechnet (Magnus)
  source         VARCHAR(8)   NOT NULL DEFAULT 'real',
  status         VARCHAR(8)   NOT NULL DEFAULT 'ok',
  PRIMARY KEY (id),
  KEY idx_reading_sensor_ts (sensor_id, measured_at),
  CONSTRAINT chk_reading_source CHECK (source IN ('real','sim')),
  CONSTRAINT chk_reading_status CHECK (status IN ('ok','fault'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS assessment (
  id               BIGINT       NOT NULL AUTO_INCREMENT,
  ts               DATETIME(3)  NOT NULL,               -- UTC, Bewertungszeit
  reading_id       BIGINT       NULL,                   -- ON DELETE SET NULL: Snapshot bleibt audit-fest
  threshold_set_id BIGINT       NULL,
  risk_level       VARCHAR(8)   NOT NULL,
  driving_factor   VARCHAR(64)  NULL,
  explanation      VARCHAR(512) NULL,
  -- Entscheidungs-Snapshot (DTB-12): self-contained fuer Audit/Anzeige
  surface_temp_c   DOUBLE       NULL,
  dew_point_c      DOUBLE       NULL,
  delta_t          DOUBLE       NULL,
  humidity_pct     DOUBLE       NULL,
  forecast_surface_temp_c DOUBLE NULL,                 -- DTB-33/FA-06: 30-min-Prognose-T_s (Nachvollziehbarkeit FA-05)
  displayed_risk_level VARCHAR(8) NULL,                 -- DTB-27 Anzeige-Hysterese: entprellte Stufe fuer die Ampel (Serve)
  PRIMARY KEY (id),
  KEY idx_assessment_ts (ts),
  CONSTRAINT chk_assessment_risk CHECK (risk_level IN ('green','yellow','orange','red','unknown')),
  CONSTRAINT chk_assessment_displayed_risk CHECK (displayed_risk_level IS NULL OR displayed_risk_level IN ('green','yellow','orange','red','unknown')),
  CONSTRAINT fk_assessment_reading FOREIGN KEY (reading_id) REFERENCES reading(id) ON DELETE SET NULL,
  CONSTRAINT fk_assessment_threshold FOREIGN KEY (threshold_set_id) REFERENCES threshold_set(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS alarm (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  assessment_id BIGINT       NOT NULL,
  severity      VARCHAR(8)   NOT NULL,
  raised_at     DATETIME(3)  NOT NULL,                  -- UTC
  state         VARCHAR(16)  NOT NULL DEFAULT 'active',
  PRIMARY KEY (id),
  KEY idx_alarm_state (state),
  CONSTRAINT chk_alarm_severity CHECK (severity IN ('warning','critical')),
  CONSTRAINT chk_alarm_state CHECK (state IN ('active','acknowledged','cleared')),
  CONSTRAINT fk_alarm_assessment FOREIGN KEY (assessment_id) REFERENCES assessment(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- append-only (NF-09): kein UPDATE/DELETE auf App-/Grant-Ebene erzwingen
CREATE TABLE IF NOT EXISTS acknowledgement (
  id        BIGINT       NOT NULL AUTO_INCREMENT,
  alarm_id  BIGINT       NOT NULL,
  operator  VARCHAR(128) NOT NULL,
  note      VARCHAR(512) NULL,
  ts        DATETIME(3)  NOT NULL,                       -- UTC
  PRIMARY KEY (id),
  CONSTRAINT fk_ack_alarm FOREIGN KEY (alarm_id) REFERENCES alarm(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- append-only (NF-09)
CREATE TABLE IF NOT EXISTS audit_log (
  id          BIGINT       NOT NULL AUTO_INCREMENT,
  ts          DATETIME(3)  NOT NULL,                     -- UTC
  event_type  VARCHAR(32)  NOT NULL,
  entity_type VARCHAR(32)  NOT NULL,
  entity_id   BIGINT       NULL,
  actor       VARCHAR(128) NOT NULL DEFAULT 'system',
  detail      JSON         NULL,
  PRIMARY KEY (id),
  KEY idx_audit_ts_event (ts, event_type),         -- DTB-29: Abfragen nach Zeit + Ereignistyp
  CONSTRAINT chk_audit_event CHECK (event_type IN
    ('reading_ingested','assessment_made','alarm_raised','alarm_acknowledged','threshold_changed','sensor_fault'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Idempotente Index-Migration fuer bestehende audit_log-Tabellen (DTB-29).
-- CREATE TABLE IF NOT EXISTS ueberspringt bereits existierende Tabellen; daher wird der
-- alte Index idx_audit_ts hier explizit entfernt und der Composite-Index idx_audit_ts_event
-- (ts, event_type) angelegt, falls noch nicht vorhanden.
-- MySQL-kompatibel: statt DROP/ADD INDEX IF EXISTS (MariaDB-Erweiterungen) pruefen wir
-- ueber INFORMATION_SCHEMA.STATISTICS und fuehren ALTER TABLE nur aus, wenn noetig.
-- Das funktioniert sowohl auf MariaDB (Projekt-Default, E-29) als auch auf MySQL 5.7/8.0.
SELECT COUNT(*) INTO @idx_audit_ts_exists
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'audit_log'
  AND INDEX_NAME = 'idx_audit_ts';

SET @drop_idx_audit_ts_sql = IF(
    @idx_audit_ts_exists > 0,
    'ALTER TABLE audit_log DROP INDEX idx_audit_ts',
    'SELECT 1'
);

PREPARE drop_idx_audit_ts_stmt FROM @drop_idx_audit_ts_sql;
EXECUTE drop_idx_audit_ts_stmt;
DEALLOCATE PREPARE drop_idx_audit_ts_stmt;

SELECT COUNT(*) INTO @idx_audit_ts_event_exists
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'audit_log'
  AND INDEX_NAME = 'idx_audit_ts_event';

SET @add_idx_audit_ts_event_sql = IF(
    @idx_audit_ts_event_exists = 0,
    'ALTER TABLE audit_log ADD INDEX idx_audit_ts_event (ts, event_type)',
    'SELECT 1'
);

PREPARE add_idx_audit_ts_event_stmt FROM @add_idx_audit_ts_event_sql;
EXECUTE add_idx_audit_ts_event_stmt;
DEALLOCATE PREPARE add_idx_audit_ts_event_stmt;

-- Idempotente Spalten-Migration fuer bestehende assessment-Tabellen (DTB-33/FA-06).
-- CREATE TABLE IF NOT EXISTS oben legt die Spalte nur bei Neuinstallation an; fuer bereits
-- existierende DBs wird forecast_surface_temp_c hier nachgezogen, sonst schlaegt der INSERT
-- von MySqlAssessmentRepository mit "Unknown column" fehl (-> RepositoryError, NF-01).
-- MySQL-kompatibel: statt ADD COLUMN IF NOT EXISTS (MariaDB-Erweiterung) pruefen wir
-- ueber INFORMATION_SCHEMA.COLUMNS und fuehren ALTER TABLE nur aus, wenn die Spalte fehlt.
-- Das funktioniert sowohl auf MariaDB (Projekt-Default, E-29) als auch auf MySQL 5.7/8.0.
SELECT COUNT(*) INTO @forecast_surface_temp_col_exists
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'assessment'
  AND COLUMN_NAME = 'forecast_surface_temp_c';

SET @add_forecast_surface_temp_col_sql = IF(
    @forecast_surface_temp_col_exists = 0,
    'ALTER TABLE assessment ADD COLUMN forecast_surface_temp_c DOUBLE NULL',
    'SELECT 1'
);

PREPARE add_forecast_surface_temp_col_stmt FROM @add_forecast_surface_temp_col_sql;
EXECUTE add_forecast_surface_temp_col_stmt;
DEALLOCATE PREPARE add_forecast_surface_temp_col_stmt;

-- Idempotente Spalten-Migration fuer bestehende assessment-Tabellen (DTB-27 Anzeige-
-- Hysterese). displayed_risk_level traegt die entprellte Stufe (RiskHysterese), die
-- die Serve-Schicht an G3 ausliefert; risk_level bleibt die rohe Kaskadenstufe.
-- Muster analog forecast_surface_temp_c (oben): INFORMATION_SCHEMA-Check -> ALTER.
SELECT COUNT(*) INTO @displayed_risk_level_col_exists
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'assessment'
  AND COLUMN_NAME = 'displayed_risk_level';

SET @add_displayed_risk_level_col_sql = IF(
    @displayed_risk_level_col_exists = 0,
    'ALTER TABLE assessment ADD COLUMN displayed_risk_level VARCHAR(8) NULL AFTER forecast_surface_temp_c',
    'SELECT 1'
);

PREPARE add_displayed_risk_level_col_stmt FROM @add_displayed_risk_level_col_sql;
EXECUTE add_displayed_risk_level_col_stmt;
DEALLOCATE PREPARE add_displayed_risk_level_col_stmt;

-- Idempotenter CHECK-Constraint fuer migrierte assessment-Tabellen (DTB-27).
-- CREATE TABLE legt den Constraint nur bei Neuinstallation an; fuer bereits
-- bestehende DBs (Pi-Migration) wird er hier nachgezogen, damit der Schema-Stand
-- zwischen Frischinstallation und Migration identisch ist (Review MEDIUM).
-- Muster analog idx_audit_ts-Migration: INFORMATION_SCHEMA.TABLE_CONSTRAINTS pruefen.
SELECT COUNT(*) INTO @chk_displayed_risk_exists
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'assessment'
  AND CONSTRAINT_NAME = 'chk_assessment_displayed_risk';

SET @add_chk_displayed_risk_sql = IF(
    @chk_displayed_risk_exists = 0,
    "ALTER TABLE assessment ADD CONSTRAINT chk_assessment_displayed_risk CHECK (displayed_risk_level IS NULL OR displayed_risk_level IN ('green','yellow','orange','red','unknown'))",
    'SELECT 1'
);

PREPARE add_chk_displayed_risk_stmt FROM @add_chk_displayed_risk_sql;
EXECUTE add_chk_displayed_risk_stmt;
DEALLOCATE PREPARE add_chk_displayed_risk_stmt;
