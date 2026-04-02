from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import UserSession, log_audit

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")

SESSION_TOKEN_KEY = "_session_token"


def create_user_session(user_id: int) -> str:
    """Crée une nouvelle session en base et retourne le token brut."""
    token = UserSession.generate_token()
    token_hash = UserSession.hash_token(token)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("User-Agent", "")[:255]
    entry = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        ip_address=ip[:45],
        user_agent=ua,
    )
    db.session.add(entry)
    db.session.commit()
    session[SESSION_TOKEN_KEY] = token
    return token


def revoke_current_session() -> None:
    """Révoque la session courante dans la DB."""
    token = session.get(SESSION_TOKEN_KEY)
    if token:
        token_hash = UserSession.hash_token(token)
        entry = UserSession.query.filter_by(token_hash=token_hash, revoked=False).first()
        if entry:
            entry.revoked = True
            db.session.commit()
    session.pop(SESSION_TOKEN_KEY, None)


@sessions_bp.route("/")
@login_required
def list_sessions():
    active = (
        UserSession.query
        .filter_by(user_id=current_user.id, revoked=False)
        .order_by(UserSession.last_seen.desc())
        .all()
    )
    current_token = session.get(SESSION_TOKEN_KEY)
    current_hash = UserSession.hash_token(current_token) if current_token else None
    return render_template("sessions/list.html", sessions=active, current_hash=current_hash)


@sessions_bp.route("/<int:id>/revoke", methods=["POST"])
@login_required
def revoke(id: int):
    entry = UserSession.query.get_or_404(id)
    # IDOR: seul le propriétaire peut révoquer
    if entry.user_id != current_user.id:
        abort(403)
    entry.revoked = True
    db.session.commit()
    log_audit("session_revoke", resource_type="session", resource_id=id)
    flash("Session révoquée.", "info")
    return redirect(url_for("sessions.list_sessions"))


@sessions_bp.route("/revoke-all", methods=["POST"])
@login_required
def revoke_all():
    current_token = session.get(SESSION_TOKEN_KEY)
    current_hash = UserSession.hash_token(current_token) if current_token else None
    query = UserSession.query.filter_by(user_id=current_user.id, revoked=False)
    if current_hash:
        # Garder la session courante active
        query = query.filter(UserSession.token_hash != current_hash)
    count = query.count()
    query.update({"revoked": True})
    db.session.commit()
    log_audit("session_revoke_all")
    flash(f"{count} autre(s) session(s) révoquée(s).", "success")
    return redirect(url_for("sessions.list_sessions"))
