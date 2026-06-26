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
  PRIMARY KEY (id),
  KEY idx_assessment_ts (ts),
  CONSTRAINT chk_assessment_risk CHECK (risk_level IN ('green','yellow','orange','red','unknown')),
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
ALTER TABLE audit_log
  DROP INDEX IF EXISTS idx_audit_ts,
  ADD INDEX IF NOT EXISTS idx_audit_ts_event (ts, event_type);

-- Idempotente Spalten-Migration fuer bestehende assessment-Tabellen (DTB-33/FA-06).
-- CREATE TABLE IF NOT EXISTS oben legt die Spalte nur bei Neuinstallation an; fuer bereits
-- existierende DBs wird forecast_surface_temp_c hier nachgezogen, sonst schlaegt der INSERT
-- von MySqlAssessmentRepository mit "Unknown column" fehl (-> RepositoryError, NF-01).
-- Hinweis: ADD COLUMN IF NOT EXISTS wird von MariaDB lange unterstuetzt, von MySQL erst
-- ab 8.0.21. Bei aelteren MySQL-Versionen muss die Spalte manuell ergaenzt werden.
ALTER TABLE assessment
  ADD COLUMN IF NOT EXISTS forecast_surface_temp_c DOUBLE NULL
    COMMENT 'DTB-33/FA-06: 30-min-Prognose-T_s (Nachvollziehbarkeit FA-05)';
