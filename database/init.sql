-- ============================================================
-- Plateforme de Gestion Académique Sécurisée
-- Schéma MySQL — GCS2-UE7-2 DevSecOps
-- ============================================================

CREATE DATABASE IF NOT EXISTS academique
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE academique;

-- ── USERS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(80)  NOT NULL UNIQUE,
  email         VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20)  NOT NULL DEFAULT 'student',
  is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  totp_secret   VARCHAR(256) NULL,
  totp_enabled  BOOLEAN      NOT NULL DEFAULT FALSE,
  backup_codes  TEXT         NULL,
  INDEX idx_users_username (username),
  INDEX idx_users_email    (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── PROFESSORS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS professors (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL UNIQUE,
  department      VARCHAR(100) NULL,
  specialization  VARCHAR(200) NULL,
  CONSTRAINT fk_prof_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── STUDENTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL UNIQUE,
  student_number VARCHAR(256) NULL UNIQUE,
  class_name     VARCHAR(50) NULL,
  CONSTRAINT fk_student_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── COURSES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS courses (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  professor_id INT          NOT NULL,
  name         VARCHAR(200) NOT NULL,
  code         VARCHAR(20)  NOT NULL UNIQUE,
  class_name   VARCHAR(50)  NOT NULL,
  credits      INT          NOT NULL DEFAULT 3,
  description  TEXT         NULL,
  CONSTRAINT fk_course_prof FOREIGN KEY (professor_id)
    REFERENCES professors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── GRADES (inscription + notation) ─────────────────────────
-- grade IS NULL  → inscrit, pas encore noté
-- grade NOT NULL → note attribuée
CREATE TABLE IF NOT EXISTS grades (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  student_id  INT NOT NULL,
  course_id   INT NOT NULL,
  grade       DECIMAL(4,2) NULL,
  graded_by   INT NULL,
  graded_at   DATETIME NULL,
  CONSTRAINT uq_student_course UNIQUE (student_id, course_id),
  CONSTRAINT fk_grade_student FOREIGN KEY (student_id)
    REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_grade_course  FOREIGN KEY (course_id)
    REFERENCES courses(id)  ON DELETE CASCADE,
  CONSTRAINT fk_grade_grader  FOREIGN KEY (graded_by)
    REFERENCES users(id)    ON DELETE SET NULL,
  CONSTRAINT chk_grade_range  CHECK (grade IS NULL OR (grade >= 0 AND grade <= 20))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── AUDIT LOGS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT          NULL,
  username      VARCHAR(80)  NULL,
  action        VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50)  NULL,
  resource_id   INT          NULL,
  ip_address    VARCHAR(45)  NULL,
  user_agent    VARCHAR(255) NULL,
  status_code   INT          NULL,
  timestamp     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_audit_timestamp (timestamp),
  INDEX idx_audit_username  (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── USER SESSIONS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_sessions (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT          NOT NULL,
  token_hash    VARCHAR(64)  NOT NULL UNIQUE,
  ip_address    VARCHAR(45)  NULL,
  user_agent    VARCHAR(255) NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked       BOOLEAN      NOT NULL DEFAULT FALSE,
  CONSTRAINT fk_session_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_session_user (user_id),
  INDEX idx_session_token (token_hash),
  INDEX idx_session_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
