from __future__ import annotations

import os
from datetime import datetime, timezone
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
        import re as _re

        # Patterns WAF : séquences réellement dangereuses (pas de mots isolés)
        _SQLI_RE = _re.compile(
            r"(\bunion\s+select\b"        # UNION SELECT
            r"|;\s*(drop|alter|truncate)\b"  # ;DROP / ;ALTER
            r"|\bor\s+1\s*=\s*1"          # OR 1=1
            r"|\band\s+1\s*=\s*1"          # AND 1=1
            r"|--\s*$"                      # commentaire SQL en fin de chaîne
            r"|/\*.*?\*/"                   # commentaire bloc SQL
            r"|<script"                     # XSS basique
            r"|javascript\s*:"             # XSS javascript:
            r"|\bon\w+\s*=)"              # event handlers (onclick=, onerror=)
            , _re.IGNORECASE
        )
        _SUSPICIOUS_UA = _re.compile(
            r"(sqlmap|nmap|nikto|dirbuster|gobuster|havij|acunetix)", _re.IGNORECASE
        )

        @app.before_request
        def waf_middleware():
            """Middleware WAF — bloque les patterns d'attaque sans faux positifs."""
            # Bloquer les User-Agents d'outils d'attaque connus
            user_agent = request.headers.get("User-Agent", "")
            if _SUSPICIOUS_UA.search(user_agent):
                from flask import abort
                abort(403)

            # Vérifier les paramètres GET et POST avec des regex ciblées
            for value in request.args.values():
                if _SQLI_RE.search(str(value)):
                    from app.models import log_audit
                    log_audit("waf_blocked", resource_type="request")
                    abort(403)
            for value in request.form.values():
                if _SQLI_RE.search(str(value)):
                    from app.models import log_audit
                    log_audit("waf_blocked", resource_type="request")
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
        def _csp_nonce():
            return getattr(g, "csp_nonce", "")
        ctx = {"current_year": datetime.now(timezone.utc).year, "unread_msgs": 0, "csp_nonce": _csp_nonce}
        if current_user.is_authenticated:
            from app.models import Message
            ctx["unread_msgs"] = Message.query.filter_by(
                receiver_id=current_user.id, read_at=None
            ).count()
        return ctx

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
    from app.models import AuditLog, Classe, Enseignement, Grade, Matiere, Professor, Schedule, Student, User

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

    prof3 = User(username="prof.duval", email="duval@guardia.school", role="professor")
    prof3.set_password("Prof123!")

    # Étudiants GCS2
    gcs2_students = [
        ("alice.dupont",   "alice@guardia.school",    "GCS2-001"),
        ("bob.martin",     "bob@guardia.school",      "GCS2-002"),
        ("claire.petit",   "claire@guardia.school",   "GCS2-003"),
        ("david.blanc",    "david@guardia.school",    "GCS2-004"),
        ("emma.leroy",     "emma@guardia.school",     "GCS2-005"),
        ("felix.moreau",   "felix@guardia.school",    "GCS2-006"),
    ]
    # Étudiants GCS3
    gcs3_students = [
        ("julie.bernard",  "julie@guardia.school",    "GCS3-001"),
        ("kevin.thomas",   "kevin@guardia.school",    "GCS3-002"),
        ("lea.richard",    "lea@guardia.school",      "GCS3-003"),
        ("maxime.robert",  "maxime@guardia.school",   "GCS3-004"),
        ("nina.girard",    "nina@guardia.school",     "GCS3-005"),
    ]

    all_student_users = []
    for uname, email, _ in gcs2_students + gcs3_students:
        u = User(username=uname, email=email, role="student")
        u.set_password("Student123!")
        all_student_users.append(u)

    db.session.add_all([admin, prof1, prof2, prof3, *all_student_users])
    db.session.flush()

    # ── Profils professeurs ───────────────────────────────────────────────────
    p1 = Professor(user_id=prof1.id, department="Cybersécurité", specialization="Cryptographie, Pentesting")
    p2 = Professor(user_id=prof2.id, department="Développement", specialization="DevSecOps, Web Security")
    p3 = Professor(user_id=prof3.id, department="Réseaux", specialization="Architecture réseau, Cloud Security")
    db.session.add_all([p1, p2, p3])
    db.session.flush()

    # ── Classes ──────────────────────────────────────────────────────────────
    gcs2 = Classe(name="GCS2", description="Guardia Cybersecurity School — 2e année")
    gcs3 = Classe(name="GCS3", description="Guardia Cybersecurity School — 3e année")
    db.session.add_all([gcs2, gcs3])
    db.session.flush()

    # ── Profils étudiants ────────────────────────────────────────────────────
    gcs2_profiles = []
    for (_, _, num), u in zip(gcs2_students, all_student_users[:6]):
        s = Student(user_id=u.id, student_number=num, classe_id=gcs2.id)
        gcs2_profiles.append(s)

    gcs3_profiles = []
    for (_, _, num), u in zip(gcs3_students, all_student_users[6:]):
        s = Student(user_id=u.id, student_number=num, classe_id=gcs3.id)
        gcs3_profiles.append(s)

    db.session.add_all(gcs2_profiles + gcs3_profiles)
    db.session.flush()

    # ── Matières ─────────────────────────────────────────────────────────────
    matieres = [
        Matiere(name="Cryptographie appliquée", code="CRYPTO-101",
                credits=4, description="Algorithmes de chiffrement, PKI, TLS."),
        Matiere(name="Sécurité des réseaux", code="SECU-201",
                credits=3, description="Firewalls, IDS/IPS, VPN, analyse réseau."),
        Matiere(name="Développement sécurisé", code="DEV-301",
                credits=4, description="OWASP Top 10, revue de code, fuzzing."),
        Matiere(name="Web Security & Pentest", code="WEB-401",
                credits=3, description="BurpSuite, SQLi, XSS, CSRF, rapports."),
        Matiere(name="Forensic & Incident Response", code="FORENSIC-501",
                credits=4, description="Analyse post-incident, collecte de preuves, timeline."),
        Matiere(name="Cloud Security", code="CLOUD-601",
                credits=3, description="AWS/Azure sécurité, IAM, conteneurs, SIEM."),
        Matiere(name="Gouvernance & Conformité", code="GRC-701",
                credits=2, description="ISO 27001, RGPD, analyse de risques, PSSI."),
    ]
    db.session.add_all(matieres)
    db.session.flush()

    # ── Enseignements ────────────────────────────────────────────────────────
    # GCS2 : 4 matières
    ens_gcs2 = [
        Enseignement(matiere_id=matieres[0].id, classe_id=gcs2.id, professor_id=p1.id),  # Crypto
        Enseignement(matiere_id=matieres[1].id, classe_id=gcs2.id, professor_id=p1.id),  # Sécu réseaux
        Enseignement(matiere_id=matieres[2].id, classe_id=gcs2.id, professor_id=p2.id),  # Dev sécurisé
        Enseignement(matiere_id=matieres[3].id, classe_id=gcs2.id, professor_id=p2.id),  # Web Pentest
    ]
    # GCS3 : 5 matières (dont certaines partagées avec d'autres profs)
    ens_gcs3 = [
        Enseignement(matiere_id=matieres[2].id, classe_id=gcs3.id, professor_id=p2.id),  # Dev sécurisé
        Enseignement(matiere_id=matieres[3].id, classe_id=gcs3.id, professor_id=p1.id),  # Web Pentest (autre prof)
        Enseignement(matiere_id=matieres[4].id, classe_id=gcs3.id, professor_id=p1.id),  # Forensic
        Enseignement(matiere_id=matieres[5].id, classe_id=gcs3.id, professor_id=p3.id),  # Cloud
        Enseignement(matiere_id=matieres[6].id, classe_id=gcs3.id, professor_id=p3.id),  # GRC
    ]
    db.session.add_all(ens_gcs2 + ens_gcs3)
    db.session.flush()

    # ── Emploi du temps GCS2 ─────────────────────────────────────────────────
    # Lundi=0, Mardi=1, Mercredi=2, Jeudi=3, Vendredi=4
    schedules_gcs2 = [
        Schedule(enseignement_id=ens_gcs2[0].id, day_of_week=0, start_time="09:00", end_time="11:00", room="A101"),
        Schedule(enseignement_id=ens_gcs2[1].id, day_of_week=0, start_time="14:00", end_time="16:00", room="A102"),
        Schedule(enseignement_id=ens_gcs2[2].id, day_of_week=1, start_time="09:00", end_time="12:00", room="Labo 1"),
        Schedule(enseignement_id=ens_gcs2[3].id, day_of_week=2, start_time="10:00", end_time="12:00", room="Labo 2"),
        Schedule(enseignement_id=ens_gcs2[0].id, day_of_week=3, start_time="09:00", end_time="11:00", room="A101"),
        Schedule(enseignement_id=ens_gcs2[1].id, day_of_week=3, start_time="14:00", end_time="16:00", room="A102"),
        Schedule(enseignement_id=ens_gcs2[2].id, day_of_week=4, start_time="09:00", end_time="11:00", room="Labo 1"),
        Schedule(enseignement_id=ens_gcs2[3].id, day_of_week=4, start_time="14:00", end_time="17:00", room="Labo 2"),
    ]
    # ── Emploi du temps GCS3 ─────────────────────────────────────────────────
    schedules_gcs3 = [
        Schedule(enseignement_id=ens_gcs3[0].id, day_of_week=0, start_time="09:00", end_time="12:00", room="B201"),
        Schedule(enseignement_id=ens_gcs3[1].id, day_of_week=0, start_time="14:00", end_time="17:00", room="Labo 3"),
        Schedule(enseignement_id=ens_gcs3[2].id, day_of_week=1, start_time="09:00", end_time="12:00", room="B201"),
        Schedule(enseignement_id=ens_gcs3[3].id, day_of_week=2, start_time="09:00", end_time="11:00", room="B202"),
        Schedule(enseignement_id=ens_gcs3[4].id, day_of_week=2, start_time="14:00", end_time="16:00", room="B203"),
        Schedule(enseignement_id=ens_gcs3[2].id, day_of_week=3, start_time="14:00", end_time="17:00", room="Labo 3"),
        Schedule(enseignement_id=ens_gcs3[3].id, day_of_week=4, start_time="09:00", end_time="11:00", room="B202"),
        Schedule(enseignement_id=ens_gcs3[4].id, day_of_week=4, start_time="14:00", end_time="16:00", room="B203"),
    ]
    db.session.add_all(schedules_gcs2 + schedules_gcs3)

    # ── Notes GCS2 ───────────────────────────────────────────────────────────
    from datetime import datetime
    grades_gcs2 = [
        # alice (0)
        (0, 0, 15.5), (0, 1, 12.0), (0, 2, 17.0), (0, 3, None),
        # bob (1)
        (1, 0,  9.5), (1, 1, 14.0), (1, 2, None),  (1, 3, 11.0),
        # claire (2)
        (2, 0, 18.0), (2, 1, None),  (2, 2, 16.5), (2, 3, 13.0),
        # david (3)
        (3, 0, None),  (3, 1, 10.5), (3, 2, 12.0), (3, 3,  8.0),
        # emma (4)
        (4, 0, 14.0), (4, 1, 16.0), (4, 2, 13.5), (4, 3, 15.0),
        # felix (5)
        (5, 0, 11.0), (5, 1,  7.5), (5, 2, None),  (5, 3, 10.0),
    ]
    for si, ei, gval in grades_gcs2:
        g = Grade(
            student_id=gcs2_profiles[si].id,
            enseignement_id=ens_gcs2[ei].id,
            grade=gval,
            graded_by=prof1.id if ei < 2 else prof2.id,
            graded_at=datetime.utcnow() if gval is not None else None,
        )
        db.session.add(g)

    # ── Notes GCS3 ───────────────────────────────────────────────────────────
    grades_gcs3 = [
        # julie (0)
        (0, 0, 16.0), (0, 1, 14.5), (0, 2, 17.5), (0, 3, 15.0), (0, 4, 13.0),
        # kevin (1)
        (1, 0, 12.0), (1, 1, None),  (1, 2, 11.0), (1, 3, 14.0), (1, 4, 10.5),
        # lea (2)
        (2, 0, 19.0), (2, 1, 18.0), (2, 2, 16.0), (2, 3, None),  (2, 4, 17.5),
        # maxime (3)
        (3, 0, None),  (3, 1, 13.0), (3, 2, 10.0), (3, 3, 11.5), (3, 4, None),
        # nina (4)
        (4, 0, 15.5), (4, 1, 12.0), (4, 2, None),  (4, 3, 16.5), (4, 4, 14.0),
    ]
    for si, ei, gval in grades_gcs3:
        prof_id = ens_gcs3[ei].professor_id
        g = Grade(
            student_id=gcs3_profiles[si].id,
            enseignement_id=ens_gcs3[ei].id,
            grade=gval,
            graded_by=prof_id,
            graded_at=datetime.utcnow() if gval is not None else None,
        )
        db.session.add(g)

    db.session.add(AuditLog(
        username="system", action="seed_db",
        resource_type="system", resource_id=None,
    ))
    db.session.commit()
    click.echo("✓ Seed complet : 2 classes, 3 profs, 11 étudiants, 7 matières, emploi du temps.")
