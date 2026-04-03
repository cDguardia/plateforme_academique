from __future__ import annotations

from functools import wraps

from flask import abort, request
from flask_login import current_user


def _check_role(*roles: str) -> None:
    """Vérifie le rôle de l'utilisateur connecté. Abort 403 + log si refus."""
    if not current_user.is_authenticated:
        abort(401)
    if current_user.role not in roles:
        # Import local pour éviter les imports circulaires
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
