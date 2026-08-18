-- Face Attendance MySQL/MariaDB schema
-- Charset: utf8mb4 for Thai text

CREATE DATABASE IF NOT EXISTS face_attendance
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE face_attendance;

CREATE TABLE IF NOT EXISTS students (
  person_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  academic_year VARCHAR(16) NOT NULL DEFAULT '',
  term VARCHAR(8) NOT NULL DEFAULT '',
  grade VARCHAR(64) NOT NULL DEFAULT '',
  room VARCHAR(32) NOT NULL DEFAULT '',
  face_score DOUBLE NULL,
  embedding LONGBLOB NULL,
  preview_jpeg LONGBLOB NULL,
  source_path VARCHAR(512) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (person_id),
  KEY idx_students_class (academic_year, term, grade, room),
  KEY idx_students_name (display_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  timestamp_local DATETIME(6) NOT NULL,
  timestamp_utc DATETIME(6) NOT NULL,
  direction ENUM('in', 'out') NOT NULL,
  person_id VARCHAR(64) NOT NULL,
  display_name VARCHAR(255) NOT NULL DEFAULT '',
  academic_year VARCHAR(16) NOT NULL DEFAULT '',
  term VARCHAR(8) NOT NULL DEFAULT '',
  grade VARCHAR(64) NOT NULL DEFAULT '',
  room VARCHAR(32) NOT NULL DEFAULT '',
  similarity DOUBLE NULL,
  snapshot_path VARCHAR(512) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_att_person_time (person_id, timestamp_local),
  KEY idx_att_direction_time (direction, timestamp_local),
  KEY idx_att_class (academic_year, term, grade, room),
  CONSTRAINT fk_att_student
    FOREIGN KEY (person_id) REFERENCES students(person_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS school_option_years (
  value VARCHAR(16) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS school_option_rooms (
  value VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_meta (
  meta_key VARCHAR(64) NOT NULL,
  meta_value TEXT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (meta_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO app_meta (meta_key, meta_value)
VALUES ('schema_version', '1')
ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value);
