from __future__ import annotations

import os
from datetime import datetime, timezone
import secrets

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

    # ── Politiques de sécurité (DB-driven) ──────────────────────────────────
    from app.models import SecurityPolicy

    def _get_policy():
        """Charge la politique de sécurité depuis la DB (cache par requête)."""
        p = getattr(g, "_security_policy", None)
        if p is None:
            try:
                p = SecurityPolicy.query.first()
            except Exception:
                p = None
            g._security_policy = p
        return p

    # ── WAF Middleware ────────────────────────────────────────────────────────
    if not app.config.get("TESTING"):
        import re as _re

        _SQLI_RE = _re.compile(
            r"(\bunion\s+select\b"
            r"|;\s*(drop|alter|truncate)\b"
            r"|\bor\s+1\s*=\s*1"
            r"|\band\s+1\s*=\s*1"
            r"|--\s*$"
            r"|/\*.*?\*/)",
            _re.IGNORECASE,
        )
        _XSS_RE = _re.compile(
            r"(<script"
            r"|javascript\s*:"
            r"|\bon\w+\s*=)",
            _re.IGNORECASE,
        )
        _SUSPICIOUS_UA = _re.compile(
            r"(sqlmap|nmap|nikto|dirbuster|gobuster|havij|acunetix)",
            _re.IGNORECASE,
        )

        @app.before_request
        def waf_middleware():
            """WAF — toujours actif, non desactivable."""
            ua = request.headers.get("User-Agent", "")
            if _SUSPICIOUS_UA.search(ua):
                from flask import abort
                abort(403)

            all_values = list(request.args.values()) + list(request.form.values())
            for value in all_values:
                val = str(value)
                if _SQLI_RE.search(val) or _XSS_RE.search(val):
                    from app.models import log_audit
                    log_audit("waf_blocked", resource_type="request")
                    from flask import abort
                    abort(403)

    # ── CSP Nonce + Session Fingerprint ──────────────────────────────────────
    @app.before_request
    def set_csp_nonce():
        g.csp_nonce = secrets.token_hex(16)

        # Vérification de session fingerprint (contrôlée par la policy)
        if current_user.is_authenticated and "session_token" in session:
            policy = _get_policy()
            if not policy or policy.session_fingerprint_enabled:
                token = session["session_token"]
                try:
                    user_session = UserSession.query.filter_by(
                        user_id=current_user.id,
                        token_hash=UserSession.hash_token(token),
                        revoked=False,
                    ).first()
                    if not user_session:
                        logout_user()
                        session.clear()
                        flash("Session invalide. Veuillez vous reconnecter.", "danger")
                        return redirect(url_for("auth.login"))
                    user_session.last_seen = datetime.now(timezone.utc)
                    db.session.commit()
                except Exception:
                    logout_user()
                    session.clear()
                    flash("Session expiree. Veuillez vous reconnecter.", "danger")
                    return redirect(url_for("auth.login"))

    # ── Security Headers — toujours actifs, non desactivables ──────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"script-src 'self' 'nonce-{nonce}'; "
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
        print("✓ Base de données initialisée.")

    return app
