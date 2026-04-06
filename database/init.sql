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
  failed_login_attempts INT  NOT NULL DEFAULT 0,
  locked_until  DATETIME     NULL,
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

-- ── CLASSES ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS classes (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(50)  NOT NULL UNIQUE,
  description VARCHAR(200) NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── STUDENTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  user_id        INT NOT NULL UNIQUE,
  student_number VARCHAR(256) NULL UNIQUE,
  classe_id      INT NULL,
  CONSTRAINT fk_student_user FOREIGN KEY (user_id)
    REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_student_classe FOREIGN KEY (classe_id)
    REFERENCES classes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── MATIERES (sujets indépendants) ──────────────────────────
CREATE TABLE IF NOT EXISTS matieres (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(200) NOT NULL,
  code        VARCHAR(20)  NOT NULL UNIQUE,
  credits     INT          NOT NULL DEFAULT 3,
  description TEXT         NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── ENSEIGNEMENTS (matiere + classe + prof) ─────────────────
CREATE TABLE IF NOT EXISTS enseignements (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  matiere_id   INT NOT NULL,
  classe_id    INT NOT NULL,
  professor_id INT NOT NULL,
  CONSTRAINT uq_matiere_classe UNIQUE (matiere_id, classe_id),
  CONSTRAINT fk_ens_matiere FOREIGN KEY (matiere_id)
    REFERENCES matieres(id) ON DELETE CASCADE,
  CONSTRAINT fk_ens_classe FOREIGN KEY (classe_id)
    REFERENCES classes(id) ON DELETE CASCADE,
  CONSTRAINT fk_ens_prof FOREIGN KEY (professor_id)
    REFERENCES professors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── GRADES (inscription + notation) ─────────────────────────
CREATE TABLE IF NOT EXISTS grades (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  student_id       INT NOT NULL,
  enseignement_id  INT NOT NULL,
  grade            DECIMAL(4,2) NULL,
  graded_by        INT NULL,
  graded_at        DATETIME NULL,
  CONSTRAINT uq_student_enseignement UNIQUE (student_id, enseignement_id),
  CONSTRAINT fk_grade_student FOREIGN KEY (student_id)
    REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_grade_enseignement FOREIGN KEY (enseignement_id)
    REFERENCES enseignements(id) ON DELETE CASCADE,
  CONSTRAINT fk_grade_grader FOREIGN KEY (graded_by)
    REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT chk_grade_range CHECK (grade IS NULL OR (grade >= 0 AND grade <= 20))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── ATTENDANCES (présences / absences / retards) ────────────
CREATE TABLE IF NOT EXISTS attendances (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  student_id       INT          NOT NULL,
  enseignement_id  INT          NOT NULL,
  date             DATE         NOT NULL,
  status           VARCHAR(10)  NOT NULL DEFAULT 'present',
  recorded_by      INT          NULL,
  recorded_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_attendance_student_ens_date UNIQUE (student_id, enseignement_id, date),
  CONSTRAINT fk_att_student FOREIGN KEY (student_id)
    REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_att_enseignement FOREIGN KEY (enseignement_id)
    REFERENCES enseignements(id) ON DELETE CASCADE,
  CONSTRAINT fk_att_recorder FOREIGN KEY (recorded_by)
    REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_att_date (date),
  INDEX idx_att_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── SCHEDULES ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedules (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  enseignement_id  INT          NOT NULL,
  day_of_week      INT          NOT NULL,
  start_time       VARCHAR(5)   NOT NULL,
  end_time         VARCHAR(5)   NOT NULL,
  room             VARCHAR(50)  NULL,
  CONSTRAINT fk_sched_enseignement FOREIGN KEY (enseignement_id)
    REFERENCES enseignements(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── MESSAGES ──────────────────────────────────────────���──────
CREATE TABLE IF NOT EXISTS messages (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  sender_id   INT          NOT NULL,
  receiver_id INT          NOT NULL,
  subject     VARCHAR(200) NOT NULL,
  body        TEXT         NOT NULL,
  read_at     DATETIME     NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_msg_sender FOREIGN KEY (sender_id)
    REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_msg_receiver FOREIGN KEY (receiver_id)
    REFERENCES users(id) ON DELETE CASCADE
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

-- ── SECURITY POLICIES (singleton) ────────────────────────────
CREATE TABLE IF NOT EXISTS security_policies (
  id                          INT AUTO_INCREMENT PRIMARY KEY,
  waf_enabled                 BOOLEAN      NOT NULL DEFAULT TRUE,
  waf_block_sqli              BOOLEAN      NOT NULL DEFAULT TRUE,
  waf_block_xss               BOOLEAN      NOT NULL DEFAULT TRUE,
  waf_block_scanners          BOOLEAN      NOT NULL DEFAULT TRUE,
  csp_enabled                 BOOLEAN      NOT NULL DEFAULT TRUE,
  hsts_enabled                BOOLEAN      NOT NULL DEFAULT TRUE,
  x_frame_deny                BOOLEAN      NOT NULL DEFAULT TRUE,
  x_content_type_nosniff      BOOLEAN      NOT NULL DEFAULT TRUE,
  referrer_policy_enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
  permissions_policy_enabled  BOOLEAN      NOT NULL DEFAULT TRUE,
  session_lifetime_minutes    INT          NOT NULL DEFAULT 30,
  session_secure_cookie       BOOLEAN      NOT NULL DEFAULT TRUE,
  session_httponly             BOOLEAN      NOT NULL DEFAULT TRUE,
  session_fingerprint_enabled BOOLEAN      NOT NULL DEFAULT TRUE,
  max_login_attempts          INT          NOT NULL DEFAULT 5,
  lockout_duration_minutes    INT          NOT NULL DEFAULT 15,
  account_lockout_enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
  totp_2fa_available          BOOLEAN      NOT NULL DEFAULT TRUE,
  pwd_min_length              INT          NOT NULL DEFAULT 8,
  pwd_require_upper           BOOLEAN      NOT NULL DEFAULT TRUE,
  pwd_require_digit           BOOLEAN      NOT NULL DEFAULT TRUE,
  pwd_require_special         BOOLEAN      NOT NULL DEFAULT TRUE,
  rate_limiting_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
  login_rate_limit            VARCHAR(30)  NOT NULL DEFAULT '5 per minute',
  audit_logging_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
  updated_at                  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert default policy (all security options ON)
INSERT INTO security_policies (id) VALUES (1);

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
