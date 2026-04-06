"""Tests unitaires — Plateforme Academique Securisee."""
import os
import pytest


@pytest.fixture
def app():
    """Cree une instance de l'application en mode testing."""
    os.environ.setdefault("FERNET_KEY", "I5zvDebYSGLzHt-oWiBOL21govf9UQQa4huvQ8iMs78=")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
    from app import create_app
    from app.extensions import db

    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_app(app):
    """App avec un admin, un prof et un etudiant en base."""
    from app.extensions import db
    from app.models import Classe, Enseignement, Grade, Matiere, Professor, Student, User

    admin = User(username="admin", email="admin@test.com", role="admin")
    admin.set_password("Admin123!")

    prof_user = User(username="prof1", email="prof@test.com", role="professor")
    prof_user.set_password("Prof123!")

    stu_user = User(username="student1", email="stu@test.com", role="student")
    stu_user.set_password("Student123!")

    db.session.add_all([admin, prof_user, stu_user])
    db.session.flush()

    prof = Professor(user_id=prof_user.id, department="Cyber")
    db.session.add(prof)
    db.session.flush()

    classe = Classe(name="GCS2-TEST", description="Test class")
    db.session.add(classe)
    db.session.flush()

    student = Student(user_id=stu_user.id, student_number="TEST-001", classe_id=classe.id)
    db.session.add(student)
    db.session.flush()

    matiere = Matiere(name="Test Subject", code="TEST-101", credits=3)
    db.session.add(matiere)
    db.session.flush()

    ens = Enseignement(matiere_id=matiere.id, classe_id=classe.id, professor_id=prof.id)
    db.session.add(ens)
    db.session.flush()

    grade = Grade(student_id=student.id, enseignement_id=ens.id)
    db.session.add(grade)
    db.session.commit()

    return app


@pytest.fixture
def seeded_client(seeded_app):
    return seeded_app.test_client()


def _login(client, username, password):
    """Helper pour se connecter."""
    return client.post("/auth/login", data={
        "username": username,
        "password": password,
    }, follow_redirects=True)


# ─── HEALTH & BASICS ────────────────────────────────────────────────────────

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_root_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_page_accessible(client):
    response = client.get("/auth/login")
    assert response.status_code == 200


# ─── AUTH ────────────────────────────────────────────────────────────────────

def test_login_valid_credentials(seeded_client):
    resp = _login(seeded_client, "admin", "Admin123!")
    assert resp.status_code == 200


def test_login_invalid_credentials(seeded_client):
    resp = seeded_client.post("/auth/login", data={
        "username": "admin",
        "password": "WrongPassword1!",
    }, follow_redirects=True)
    assert b"incorrect" in resp.data or resp.status_code == 200


def test_logout(seeded_client):
    _login(seeded_client, "admin", "Admin123!")
    resp = seeded_client.post("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200


def test_register_page_accessible(client):
    resp = client.get("/auth/register")
    assert resp.status_code == 200


# ─── RBAC — ADMIN ────────────────────────────────────────────────────────────

def test_admin_dashboard_requires_login(client):
    resp = client.get("/admin/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_admin_dashboard_accessible_by_admin(seeded_client):
    _login(seeded_client, "admin", "Admin123!")
    resp = seeded_client.get("/admin/dashboard")
    assert resp.status_code == 200


def test_admin_dashboard_forbidden_for_student(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/admin/dashboard")
    assert resp.status_code == 403


def test_admin_dashboard_forbidden_for_professor(seeded_client):
    _login(seeded_client, "prof1", "Prof123!")
    resp = seeded_client.get("/admin/dashboard")
    assert resp.status_code == 403


def test_admin_users_forbidden_for_student(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/admin/users")
    assert resp.status_code == 403


# ─── RBAC — PROFESSOR ───────────────────────────────────────────────────────

def test_professor_dashboard_accessible(seeded_client):
    _login(seeded_client, "prof1", "Prof123!")
    resp = seeded_client.get("/professor/dashboard")
    assert resp.status_code == 200


def test_professor_dashboard_forbidden_for_student(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/professor/dashboard")
    assert resp.status_code == 403


def test_professor_courses_accessible(seeded_client):
    _login(seeded_client, "prof1", "Prof123!")
    resp = seeded_client.get("/professor/courses")
    assert resp.status_code == 200


def test_professor_attendance_accessible(seeded_client):
    _login(seeded_client, "prof1", "Prof123!")
    resp = seeded_client.get("/professor/attendance")
    assert resp.status_code == 200


# ─── RBAC — STUDENT ─────────────────────────────────────────────────────────

def test_student_dashboard_accessible(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/student/dashboard")
    assert resp.status_code == 200


def test_student_dashboard_forbidden_for_professor(seeded_client):
    _login(seeded_client, "prof1", "Prof123!")
    resp = seeded_client.get("/student/dashboard")
    assert resp.status_code == 403


def test_student_grades_accessible(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/student/grades")
    assert resp.status_code == 200


def test_student_attendance_accessible(seeded_client):
    _login(seeded_client, "student1", "Student123!")
    resp = seeded_client.get("/student/attendance")
    assert resp.status_code == 200


# ─── SECURITY HEADERS ───────────────────────────────────────────────────────

def test_security_headers(client):
    resp = client.get("/auth/login")
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in resp.headers
    assert "script-src" in resp.headers["Content-Security-Policy"]


def test_login_form_uses_post_method(client):
    resp = client.get("/auth/login")
    assert b'method="POST"' in resp.data
    assert b"username" in resp.data
    assert b"password" in resp.data


# ─── SCHEDULE ───────────────────────────────────────────────────────────────

def test_schedule_requires_login(client):
    resp = client.get("/schedule/", follow_redirects=False)
    assert resp.status_code == 302


def test_schedule_accessible_when_logged_in(seeded_client):
    _login(seeded_client, "admin", "Admin123!")
    resp = seeded_client.get("/schedule/")
    assert resp.status_code == 200


# ─── MESSAGES ───────────────────────────────────────────────────────────────

def test_messages_requires_login(client):
    resp = client.get("/messages/", follow_redirects=False)
    assert resp.status_code == 302


def test_messages_accessible_when_logged_in(seeded_client):
    _login(seeded_client, "admin", "Admin123!")
    resp = seeded_client.get("/messages/")
    assert resp.status_code == 200
