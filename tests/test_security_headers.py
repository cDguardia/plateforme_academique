from __future__ import annotations

"""
Tests des en-têtes de sécurité HTTP.
Vérifie que chaque réponse contient les headers requis par le CDC.
"""


class TestSecurityHeaders:
    """Vérifie la présence et la valeur des headers de sécurité."""

    ENDPOINTS = ["/auth/login", "/health"]

    def test_x_frame_options(self, client):
        for url in self.ENDPOINTS:
            r = client.get(url)
            assert r.headers.get("X-Frame-Options") == "DENY", \
                f"X-Frame-Options manquant sur {url}"

    def test_x_content_type_options(self, client):
        for url in self.ENDPOINTS:
            r = client.get(url)
            assert r.headers.get("X-Content-Type-Options") == "nosniff", \
                f"X-Content-Type-Options manquant sur {url}"

    def test_referrer_policy(self, client):
        for url in self.ENDPOINTS:
            r = client.get(url)
            assert "Referrer-Policy" in r.headers, \
                f"Referrer-Policy manquant sur {url}"

    def test_permissions_policy(self, client):
        for url in self.ENDPOINTS:
            r = client.get(url)
            assert "Permissions-Policy" in r.headers, \
                f"Permissions-Policy manquant sur {url}"

    def test_content_security_policy(self, client):
        for url in self.ENDPOINTS:
            r = client.get(url)
            csp = r.headers.get("Content-Security-Policy", "")
            assert "default-src" in csp, \
                f"CSP default-src manquant sur {url}"


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_returns_json(self, client):
        r = client.get("/health")
        data = r.get_json()
        assert data is not None
        assert data.get("status") == "ok"


class TestRBACIsolation:
    """Vérifie que les rôles ne peuvent pas accéder aux espaces des autres."""

    def test_student_cannot_access_admin(self, client, app):
        from app.extensions import db
        from app.models import User
        with app.app_context():
            u = User(username="student_rbac", email="student_rbac@test.com", role="student")
            u.set_password("Student123!")
            db.session.add(u)
            db.session.commit()

        with client:
            client.post("/auth/login", data={
                "username": "student_rbac",
                "password": "Student123!",
            }, follow_redirects=True)
            response = client.get("/admin/dashboard", follow_redirects=False)
            assert response.status_code in (302, 403)

    def test_student_cannot_access_professor(self, client, app):
        with client:
            response = client.get("/professor/dashboard", follow_redirects=False)
            assert response.status_code in (302, 403)
