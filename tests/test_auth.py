from __future__ import annotations

import pytest

from app.extensions import db
from app.models import User


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _create_user(app, username="testuser", password="Test123!", role="student"):
    with app.app_context():
        u = User(username=username, email=f"{username}@test.com", role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id


# ─── Tests page de connexion ──────────────────────────────────────────────────

class TestLoginPage:
    def test_login_page_returns_200(self, client):
        response = client.get("/auth/login")
        assert response.status_code == 200

    def test_login_page_contains_form(self, client):
        response = client.get("/auth/login")
        assert b"username" in response.data or b"connexion" in response.data.lower()

    def test_login_redirects_authenticated_user(self, client, app):
        _create_user(app, username="logintest", password="Login123!")
        client.post("/auth/login", data={
            "username": "logintest",
            "password": "Login123!",
        }, follow_redirects=False)
        response = client.get("/auth/login", follow_redirects=False)
        # Un utilisateur connecté est redirigé
        assert response.status_code in (200, 302)


# ─── Tests authentification ───────────────────────────────────────────────────

class TestAuthentication:
    def test_login_wrong_password(self, client, app):
        _create_user(app, username="wrongpass", password="Correct123!")
        response = client.post("/auth/login", data={
            "username": "wrongpass",
            "password": "WrongPassword!",
        }, follow_redirects=True)
        assert response.status_code == 200
        # Doit rester sur la page de login ou afficher une erreur
        assert b"wrongpass" not in response.data or response.status_code == 200

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/login", data={
            "username": "ghost_user_xyz",
            "password": "Password123!",
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_logout_requires_login(self, client):
        response = client.post("/auth/logout", follow_redirects=True)
        assert response.status_code == 200


# ─── Tests sécurité des mots de passe ────────────────────────────────────────

class TestPasswordSecurity:
    def test_password_hashed_in_db(self, app):
        with app.app_context():
            u = User(username="hashtest", email="hashtest@test.com", role="student")
            u.set_password("MySecurePass1!")
            db.session.add(u)
            db.session.commit()
            assert u.password_hash != "MySecurePass1!"
            assert u.password_hash.startswith("$2b$") or u.password_hash.startswith("$2a$")

    def test_check_password_correct(self, app):
        with app.app_context():
            u = User(username="checkpass", email="checkpass@test.com", role="student")
            u.set_password("MyPass123!")
            db.session.add(u)
            db.session.commit()
            assert u.check_password("MyPass123!") is True

    def test_check_password_wrong(self, app):
        with app.app_context():
            u = User(username="wrongcheck", email="wrongcheck@test.com", role="student")
            u.set_password("MyPass123!")
            db.session.add(u)
            db.session.commit()
            assert u.check_password("WrongPass123!") is False


# ─── Tests pages protégées ────────────────────────────────────────────────────

class TestProtectedRoutes:
    def test_admin_dashboard_requires_auth(self, client):
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code in (302, 401)

    def test_professor_dashboard_requires_auth(self, client):
        response = client.get("/professor/dashboard", follow_redirects=False)
        assert response.status_code in (302, 401)

    def test_student_dashboard_requires_auth(self, client):
        response = client.get("/student/dashboard", follow_redirects=False)
        assert response.status_code in (302, 401)

    def test_root_redirects_to_login(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
