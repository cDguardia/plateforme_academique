from __future__ import annotations

import os
from datetime import datetime
import secrets

import click
from flask import Flask, g, redirect, render_template, url_for, session, request, flash
from flask_login import current_user, login_required, logout_user

from config import CONFIG_MAP
from app.extensions import bcrypt, cors, csrf, db, jwt, limiter, login_manager


def create_app(env: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    # ── Configuration ────────────────────────────────────────────────────────
    cfg_name = env or os.environ.get("FLASK_ENV", "default")
    app.config.from_object(CONFIG_MAP.get(cfg_name, CONFIG_MAP["default"]))
    if not app.config.get("SECRET_KEY"):
        if cfg_name == "production":
            raise RuntimeError("SECRET_KEY must be set in production")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    # ── Extensions ───────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    # ── User loader ──────────────────────────────────────────────────────────
    from app.models import User, UserSession

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ── Headers de sécurité HTTP ─────────────────────────────────────────────
    if not app.config.get("TESTING"):
        @app.before_request
        def waf_middleware():
            """Middleware WAF simple pour bloquer les attaques courantes"""
            # Bloquer les User-Agents suspects
            user_agent = request.headers.get('User-Agent', '').lower()
            suspicious_ua = ['sqlmap', 'nmap', 'nikto', 'dirbuster', 'gobuster']
            if any(ua in user_agent for ua in suspicious_ua):
                from flask import abort
                abort(403)

            # Bloquer les payloads SQLi dans les paramètres
            sqli_patterns = ["'", '"', 'union', 'select', 'drop', 'insert', 'update', 'delete', '--', '/*', '*/']
            for value in request.args.values():
                if any(pattern in str(value).lower() for pattern in sqli_patterns):
                    abort(403)
            for value in request.form.values():
                if any(pattern in str(value).lower() for pattern in sqli_patterns):
                    abort(403)

    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = secrets.token_hex(16)

        # Vérification de session fingerprint
        if current_user.is_authenticated and "session_token" in session:
            token = session["session_token"]
            try:
                user_session = UserSession.query.filter_by(
                    user_id=current_user.id,
                    token_hash=UserSession.hash_token(token),
                    revoked=False
                ).first()
                if not user_session:
                    logout_user()
                    session.clear()
                    flash("Session invalide. Veuillez vous reconnecter.", "danger")
                    return redirect(url_for("auth.login"))
                # Mettre à jour dernière activité
                user_session.last_seen = datetime.utcnow()
                db.session.commit()
            except Exception:
                logout_user()
                session.clear()
                flash("Session expirée. Veuillez vous reconnecter.", "danger")
                return redirect(url_for("auth.login"))

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        csp_nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"style-src 'self' 'nonce-{csp_nonce}'; "
            f"script-src 'self' 'nonce-{csp_nonce}'; "
            "img-src 'self' data:; "
            "font-src 'self' data:"
        )

        if not app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers.pop("Server", None)

        return response

    # ── Blueprints ───────────────────────────────────────────────────────────
    from app.auth import auth_bp
    from app.routes_admin import admin_bp
    from app.routes_messages import messages_bp
    from app.routes_professor import professor_bp
    from app.routes_schedule import schedule_bp
    from app.routes_api import api_bp
    from app.routes_sessions import sessions_bp
    from app.routes_student import student_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(professor_bp, url_prefix="/professor")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(messages_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(api_bp)

    # ── Routes globales ──────────────────────────────────────────────────────
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "professor":
            return redirect(url_for("professor.dashboard"))
        return redirect(url_for("student.dashboard"))

    # ── Gestionnaires d'erreurs ───────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("500.html"), 500

    # ── Contexte global templates ─────────────────────────────────────────────
    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.utcnow().year}

    # ── Health check ─────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    # ── CLI Commands ─────────────────────────────────────────────────────────
    @app.cli.command("init-db")
    def init_db_command():
        from app import models  # noqa: F401
        db.create_all()
        click.echo("✓ Base de données initialisée.")

    @app.cli.command("seed-db")
    def seed_db_command():
        from app import models  # noqa: F401
        db.create_all()
        _seed_demo_data()
        click.echo("✓ Données de démonstration injectées.")

    return app


def _seed_demo_data() -> None:
    from app.models import AuditLog, Course, Grade, Professor, Student, User

    if User.query.first():
        click.echo("ℹ Données déjà présentes — seed ignoré.")
        return

    # ── Utilisateurs ─────────────────────────────────────────────────────────
    admin = User(username="admin", email="admin@guardia.school", role="admin")
    admin.set_password("Admin123!")

    prof1 = User(username="prof.martin", email="martin@guardia.school", role="professor")
    prof1.set_password("Prof123!")

    prof2 = User(username="prof.chen", email="chen@guardia.school", role="professor")
    prof2.set_password("Prof123!")

    students_data = [
        ("alice.dupont",  "alice@guardia.school",  "GCS2-001"),
        ("bob.martin",    "bob@guardia.school",    "GCS2-002"),
        ("claire.petit",  "claire@guardia.school", "GCS2-003"),
        ("david.blanc",   "david@guardia.school",  "GCS2-004"),
    ]
    student_users = []
    for uname, email, _ in students_data:
        u = User(username=uname, email=email, role="student")
        u.set_password("Student123!")
        student_users.append(u)

    db.session.add_all([admin, prof1, prof2, *student_users])
    db.session.flush()

    # ── Profils professeurs ───────────────────────────────────────────────────
    p1 = Professor(user_id=prof1.id, department="Cybersécurité", specialization="Cryptographie, Pentesting")
    p2 = Professor(user_id=prof2.id, department="Développement", specialization="DevSecOps, Web Security")
    db.session.add_all([p1, p2])
    db.session.flush()

    # ── Profils étudiants ────────────────────────────────────────────────────
    student_profiles = []
    for (_, _, num), u in zip(students_data, student_users):
        s = Student(user_id=u.id, student_number=num, class_name="GCS2")
        student_profiles.append(s)
    db.session.add_all(student_profiles)
    db.session.flush()

    # ── Cours ────────────────────────────────────────────────────────────────
    courses = [
        Course(professor_id=p1.id, name="Cryptographie appliquée", code="CRYPTO-101",
               class_name="GCS2", credits=4, description="Algorithmes de chiffrement, PKI, TLS."),
        Course(professor_id=p1.id, name="Sécurité des réseaux", code="SECU-201",
               class_name="GCS2", credits=3, description="Firewalls, IDS/IPS, VPN, analyse réseau."),
        Course(professor_id=p2.id, name="Développement sécurisé", code="DEV-301",
               class_name="GCS2", credits=4, description="OWASP Top 10, revue de code, fuzzing."),
        Course(professor_id=p2.id, name="Web Security & Pentest", code="WEB-401",
               class_name="GCS2", credits=3, description="BurpSuite, SQLi, XSS, CSRF, rapports."),
    ]
    db.session.add_all(courses)
    db.session.flush()

    # ── Notes (inscription + quelques notes) ─────────────────────────────────
    sample_grades = [
        (0, 0, 15.5), (0, 1, 12.0), (0, 2, 17.0), (0, 3, None),
        (1, 0,  9.5), (1, 1, 14.0), (1, 2, None),  (1, 3, 11.0),
        (2, 0, 18.0), (2, 1, None),  (2, 2, 16.5), (2, 3, 13.0),
        (3, 0, None),  (3, 1, 10.5), (3, 2, 12.0), (3, 3,  8.0),
    ]
    from datetime import datetime
    for si, ci, gval in sample_grades:
        g = Grade(
            student_id=student_profiles[si].id,
            course_id=courses[ci].id,
            grade=gval,
            graded_by=prof1.id if ci < 2 else prof2.id,
            graded_at=datetime.utcnow() if gval is not None else None,
        )
        db.session.add(g)

    db.session.add(AuditLog(
        username="system", action="seed_db",
        resource_type="system", resource_id=None,
    ))
    db.session.commit()
    click.echo("✓ admin / prof.martin / prof.chen / alice.dupont / bob.martin / claire.petit / david.blanc créés.")
