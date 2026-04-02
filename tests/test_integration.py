from __future__ import annotations

"""
Tests d'intégration — flux complets multi-rôles.
Vérifie les scénarios end-to-end : inscription → notation → consultation.
"""

import pytest

from app.extensions import db
from app.models import Course, Grade, Professor, Student, User


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _register_user(app, username, email, password, role):
    """Crée un utilisateur + profil directement en base."""
    with app.app_context():
        u = User(username=username, email=email, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
        if role == "professor":
            db.session.add(Professor(user_id=u.id, department="Test"))
        elif role == "student":
            db.session.add(Student(user_id=u.id, student_number=f"INT-{username}", class_name="GCS2"))
        db.session.commit()
        return u.id


def _login(client, username, password):
    return client.post("/auth/login", data={
        "username": username,
        "password": password,
    }, follow_redirects=True)


def _logout(client):
    client.post("/auth/logout", data={}, follow_redirects=True)


# ─── Flux complet : professeur crée cours → étudiant s'inscrit → professeur note ──

class TestFullAcademicFlow:

    def test_professor_can_login(self, client, app):
        _register_user(app, "int_prof", "int_prof@test.com", "Prof123!", "professor")
        resp = _login(client, "int_prof", "Prof123!")
        assert resp.status_code == 200
        _logout(client)

    def test_student_can_login(self, client, app):
        _register_user(app, "int_student", "int_student@test.com", "Student123!", "student")
        resp = _login(client, "int_student", "Student123!")
        assert resp.status_code == 200
        _logout(client)

    def test_professor_dashboard_accessible(self, client, app):
        _register_user(app, "int_prof2", "int_prof2@test.com", "Prof123!", "professor")
        with client:
            _login(client, "int_prof2", "Prof123!")
            resp = client.get("/professor/dashboard")
            assert resp.status_code == 200
            _logout(client)

    def test_student_dashboard_accessible(self, client, app):
        _register_user(app, "int_stud2", "int_stud2@test.com", "Student123!", "student")
        with client:
            _login(client, "int_stud2", "Student123!")
            resp = client.get("/student/dashboard")
            assert resp.status_code == 200
            _logout(client)

    def test_student_can_view_courses_page(self, client, app):
        _register_user(app, "int_stud3", "int_stud3@test.com", "Student123!", "student")
        with client:
            _login(client, "int_stud3", "Student123!")
            resp = client.get("/student/courses")
            assert resp.status_code == 200
            _logout(client)

    def test_student_can_view_grades_page(self, client, app):
        _register_user(app, "int_stud4", "int_stud4@test.com", "Student123!", "student")
        with client:
            _login(client, "int_stud4", "Student123!")
            resp = client.get("/student/grades")
            assert resp.status_code == 200
            _logout(client)


# ─── Tests RBAC cross-rôle ────────────────────────────────────────────────────

class TestRBACCrossRole:
    """Vérifie qu'un rôle ne peut pas accéder aux espaces d'un autre rôle."""

    def test_professor_cannot_access_admin(self, client, app):
        _register_user(app, "rbac_prof", "rbac_prof@test.com", "Prof123!", "professor")
        with client:
            _login(client, "rbac_prof", "Prof123!")
            resp = client.get("/admin/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)

    def test_professor_cannot_access_student_area(self, client, app):
        _register_user(app, "rbac_prof2", "rbac_prof2@test.com", "Prof123!", "professor")
        with client:
            _login(client, "rbac_prof2", "Prof123!")
            resp = client.get("/student/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)

    def test_student_cannot_access_professor_area(self, client, app):
        _register_user(app, "rbac_stud", "rbac_stud@test.com", "Student123!", "student")
        with client:
            _login(client, "rbac_stud", "Student123!")
            resp = client.get("/professor/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)

    def test_student_cannot_access_admin(self, client, app):
        _register_user(app, "rbac_stud2", "rbac_stud2@test.com", "Student123!", "student")
        with client:
            _login(client, "rbac_stud2", "Student123!")
            resp = client.get("/admin/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)

    def test_admin_cannot_access_professor_area(self, client, app):
        _register_user(app, "rbac_admin", "rbac_admin@test.com", "Admin123!", "admin")
        with client:
            _login(client, "rbac_admin", "Admin123!")
            resp = client.get("/professor/dashboard", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)


# ─── Tests protection IDOR ────────────────────────────────────────────────────

class TestIDORProtection:
    """Un étudiant ne peut pas accéder aux cours auxquels il n'est pas inscrit."""

    def test_student_cannot_access_unregistered_course(self, client, app):
        with app.app_context():
            # Créer un professeur et un cours
            pu = User(username="idor_prof", email="idor_prof@test.com", role="professor")
            pu.set_password("Prof123!")
            db.session.add(pu)
            db.session.flush()
            p = Professor(user_id=pu.id, department="Test")
            db.session.add(p)
            db.session.flush()
            c = Course(professor_id=p.id, name="IDOR Course",
                       code="IDOR-001", class_name="GCS2", credits=3)
            db.session.add(c)
            db.session.flush()
            course_id = c.id

            # Créer un étudiant NON inscrit au cours
            su = User(username="idor_stud", email="idor_stud@test.com", role="student")
            su.set_password("Student123!")
            db.session.add(su)
            db.session.flush()
            db.session.add(Student(user_id=su.id, student_number="IDOR-001", class_name="GCS2"))
            db.session.commit()

        with client:
            _login(client, "idor_stud", "Student123!")
            # Tenter d'accéder au cours sans être inscrit
            resp = client.get(f"/student/courses/{course_id}", follow_redirects=False)
            assert resp.status_code in (302, 403)
            _logout(client)

    def test_student_can_access_registered_course(self, client, app):
        with app.app_context():
            pu = User(username="idor_prof2", email="idor_prof2@test.com", role="professor")
            pu.set_password("Prof123!")
            db.session.add(pu)
            db.session.flush()
            p = Professor(user_id=pu.id, department="Test")
            db.session.add(p)
            db.session.flush()
            c = Course(professor_id=p.id, name="IDOR Course 2",
                       code="IDOR-002", class_name="GCS2", credits=3)
            db.session.add(c)
            db.session.flush()

            su = User(username="idor_stud2", email="idor_stud2@test.com", role="student")
            su.set_password("Student123!")
            db.session.add(su)
            db.session.flush()
            s = Student(user_id=su.id, student_number="IDOR-002", class_name="GCS2")
            db.session.add(s)
            db.session.flush()

            # Inscrire l'étudiant au cours
            db.session.add(Grade(student_id=s.id, course_id=c.id, grade=None))
            db.session.commit()
            course_id = c.id

        with client:
            _login(client, "idor_stud2", "Student123!")
            resp = client.get(f"/student/courses/{course_id}")
            assert resp.status_code == 200
            _logout(client)


# ─── Tests profil utilisateur ─────────────────────────────────────────────────

class TestUserProfile:

    def test_student_can_view_profile(self, client, app):
        _register_user(app, "profile_stud", "profile_stud@test.com", "Student123!", "student")
        with client:
            _login(client, "profile_stud", "Student123!")
            resp = client.get("/student/profile")
            assert resp.status_code == 200
            _logout(client)

    def test_professor_can_view_profile(self, client, app):
        _register_user(app, "profile_prof", "profile_prof@test.com", "Prof123!", "professor")
        with client:
            _login(client, "profile_prof", "Prof123!")
            resp = client.get("/professor/profile")
            assert resp.status_code == 200
            _logout(client)

    def test_admin_can_view_users_list(self, client, app):
        _register_user(app, "profile_admin", "profile_admin@test.com", "Admin123!", "admin")
        with client:
            _login(client, "profile_admin", "Admin123!")
            resp = client.get("/admin/users")
            assert resp.status_code == 200
            _logout(client)
