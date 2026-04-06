from __future__ import annotations

from functools import wraps

from flask import abort, request
from flask_login import current_user


def _get_current_user_role() -> str | None:
    """Récupère le rôle de l'utilisateur, que ce soit via Flask-Login ou JWT."""
    # Flask-Login (sessions web)
    if current_user and current_user.is_authenticated:
        return current_user.role

    # JWT (API) — vérifier si un token JWT est présent
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from flask_jwt_extended import get_jwt_identity
            from app.models import User
            user_id = get_jwt_identity()
            if user_id:
                user = User.query.get(user_id)
                return user.role if user else None
        except Exception:  # noqa: S110
            pass

    return None


def _check_role(*roles: str) -> None:
    """Vérifie le rôle de l'utilisateur connecté (web ou API). Abort 403 + log si refus."""
    role = _get_current_user_role()
    if role is None:
        abort(401)
    if role not in roles:
        from app.models import log_audit
        log_audit(
            action="403_forbidden",
            resource_type="route",
            resource_id=None,
        )
        abort(403)


def admin_required(f):
    """Réservé aux administrateurs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        _check_role("admin")
        return f(*args, **kwargs)
    return decorated


def professor_required(f):
    """Réservé aux professeurs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        _check_role("professor")
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    """Réservé aux étudiants."""
    @wraps(f)
    def decorated(*args, **kwargs):
        _check_role("student")
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles: str):
    """Décorateur générique multi-rôles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            _check_role(*roles)
            return f(*args, **kwargs)
        return decorated
    return decorator
