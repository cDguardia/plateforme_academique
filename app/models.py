from __future__ import annotations

import hashlib
import os
from datetime import datetime

from flask import request
from flask_login import UserMixin, current_user

from app.extensions import bcrypt, db


# ─── USER ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 2FA TOTP
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)

    # Sessions actives
    active_sessions = db.relationship(
        "UserSession", back_populates="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    # Relations inverse
    professor_profile = db.relationship(
        "Professor", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    student_profile = db.relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    # ── Sécurité ──────────────────────────────────────────────────────────────

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


# ─── PROFESSOR ───────────────────────────────────────────────────────────────

class Professor(db.Model):
    __tablename__ = "professors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    department = db.Column(db.String(100), nullable=True)
    specialization = db.Column(db.String(200), nullable=True)

    user = db.relationship("User", back_populates="professor_profile")
    courses = db.relationship("Course", back_populates="professor", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Professor user_id={self.user_id}>"


# ─── STUDENT ─────────────────────────────────────────────────────────────────

class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    student_number = db.Column(db.String(20), unique=True, nullable=True)
    class_name = db.Column(db.String(50), nullable=True)

    user = db.relationship("User", back_populates="student_profile")
    grades = db.relationship(
        "Grade", back_populates="student", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student {self.student_number}>"


# ─── COURSE ──────────────────────────────────────────────────────────────────

class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(
        db.Integer, db.ForeignKey("professors.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    credits = db.Column(db.Integer, default=3, nullable=False)
    description = db.Column(db.Text, nullable=True)

    professor = db.relationship("Professor", back_populates="courses")
    grades = db.relationship(
        "Grade", back_populates="course", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Course {self.code}>"


# ─── GRADE (sert aussi d'inscription) ────────────────────────────────────────
# grade IS NULL  → étudiant inscrit, pas encore noté
# grade NOT NULL → note attribuée

class Grade(db.Model):
    __tablename__ = "grades"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    grade = db.Column(db.Numeric(4, 2), nullable=True)  # NULL = inscrit non noté
    graded_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    graded_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student", back_populates="grades")
    course = db.relationship("Course", back_populates="grades")
    grader = db.relationship("User", foreign_keys=[graded_by])

    def __repr__(self) -> str:
        return f"<Grade student={self.student_id} course={self.course_id} grade={self.grade}>"


# ─── AUDIT LOG ───────────────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username = db.Column(db.String(80), nullable=True)  # dénormalisé pour traçabilité
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=True)
    resource_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.username}>"


# ─── USER SESSION ────────────────────────────────────────────────────────────

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="active_sessions")

    @staticmethod
    def generate_token() -> str:
        return os.urandom(32).hex()

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"<UserSession user_id={self.user_id} revoked={self.revoked}>"


# ─── MESSAGE ─────────────────────────────────────────────────────────────────

class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    receiver_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __repr__(self) -> str:
        return f"<Message from={self.sender_id} to={self.receiver_id}>"


# ─── SCHEDULE ────────────────────────────────────────────────────────────────

class Schedule(db.Model):
    __tablename__ = "schedules"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week = db.Column(db.Integer, nullable=False)   # 0=Lun … 6=Dim
    start_time = db.Column(db.String(5), nullable=False)  # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)    # "HH:MM"
    room = db.Column(db.String(50), nullable=True)

    course = db.relationship("Course")

    DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    @property
    def day_name(self) -> str:
        return self.DAY_NAMES[self.day_of_week]

    def __repr__(self) -> str:
        return f"<Schedule course={self.course_id} day={self.day_of_week} {self.start_time}-{self.end_time}>"


# ─── HELPER ──────────────────────────────────────────────────────────────────

def log_audit(
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    username: str | None = None,
) -> None:
    """Enregistre une action dans les logs d'audit.
    Peut être appelé en dehors d'un contexte utilisateur connecté (ex: login_failed).
    """
    try:
        uid = None
        uname = username
        if current_user and current_user.is_authenticated:
            uid = current_user.id
            uname = uname or current_user.username

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        entry = AuditLog(
            user_id=uid,
            username=uname,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip[:45] if ip else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
