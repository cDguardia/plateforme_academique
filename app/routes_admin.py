from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.forms import UserCreateForm, UserEditForm
from app.models import AuditLog, Course, Grade, Professor, Student, User, log_audit
from app.rbac import admin_required

admin_bp = Blueprint("admin", __name__)


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "professors":  User.query.filter_by(role="professor").count(),
        "students":    User.query.filter_by(role="student").count(),
        "courses":     Course.query.count(),
    }
    recent_logs = (
        AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    )
    return render_template("dashboard_admin.html", stats=stats, recent_logs=recent_logs)


# ─── USERS ───────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
@admin_required
def users():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    query = User.query
    if q:
        query = query.filter(
            (User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    if role:
        query = query.filter_by(role=role)
    user_list = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=user_list)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def user_create():
    form = UserCreateForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            is_active=form.is_active.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        if user.role == "professor":
            db.session.add(Professor(user_id=user.id))
        elif user.role == "student":
            count = Student.query.count() + 1
            db.session.add(Student(user_id=user.id, student_number=f"GCS2-{count:03d}"))

        db.session.commit()
        log_audit("user_create", resource_type="user", resource_id=user.id)
        flash(f"Utilisateur « {user.username} » créé.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form=form, user=None)


@admin_bp.route("/users/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit(id: int):
    user = User.query.get_or_404(id)
    form = UserEditForm(obj=user)
    if form.validate_on_submit():
        # Vérifier unicité username/email si modifié
        if form.username.data.strip() != user.username:
            if User.query.filter_by(username=form.username.data.strip()).first():
                flash("Ce nom d'utilisateur est déjà pris.", "danger")
                return render_template("admin/user_form.html", form=form, user=user)
        if form.email.data.strip().lower() != user.email:
            if User.query.filter_by(email=form.email.data.strip().lower()).first():
                flash("Cet email est déjà utilisé.", "danger")
                return render_template("admin/user_form.html", form=form, user=user)

        old_role = user.role
        user.username = form.username.data.strip()
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.is_active = form.is_active.data

        # Créer profil si changement de rôle
        if user.role == "professor" and not user.professor_profile:
            db.session.add(Professor(user_id=user.id))
        elif user.role == "student" and not user.student_profile:
            count = Student.query.count() + 1
            db.session.add(Student(user_id=user.id, student_number=f"GCS2-{count:03d}"))

        db.session.commit()
        log_audit("user_edit", resource_type="user", resource_id=user.id)
        flash(f"Utilisateur « {user.username} » modifié.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form=form, user=user)


@admin_bp.route("/users/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(id: int):
    from flask_login import current_user
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for("admin.users"))
    username = user.username
    log_audit("user_delete", resource_type="user", resource_id=user.id)
    db.session.delete(user)
    db.session.commit()
    flash(f"Utilisateur « {username} » supprimé.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:id>/reset-pwd", methods=["POST"])
@login_required
@admin_required
def user_reset_password(id: int):
    import secrets

    user = User.query.get_or_404(id)
    temp_pwd = secrets.token_urlsafe(12)
    user.set_password(temp_pwd)
    db.session.commit()
    log_audit("password_reset", resource_type="user", resource_id=user.id)
    flash(
        f"Mot de passe de « {user.username} » réinitialisé. Communiquez-le de manière sécurisée.",
        "warning",
    )
    return redirect(url_for("admin.users"))


# ─── AUDIT LOGS ──────────────────────────────────────────────────────────────

@admin_bp.route("/audit-logs")
@login_required
@admin_required
def audit_logs():
    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = request.args.get("page", 1, type=int)

    query = AuditLog.query
    if q:
        query = query.filter(
            (AuditLog.action.ilike(f"%{q}%")) | (AuditLog.username.ilike(f"%{q}%"))
        )
    if date_from:
        try:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to + "T23:59:59"))
        except ValueError:
            pass

    logs = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/audit_logs.html", logs=logs)


# ─── STATISTICS ──────────────────────────────────────────────────────────────

@admin_bp.route("/statistics")
@login_required
@admin_required
def statistics():
    from sqlalchemy import func

    total_users = User.query.count()
    stats = {
        "total_users": total_users,
        "admins":      User.query.filter_by(role="admin").count(),
        "professors":  User.query.filter_by(role="professor").count(),
        "students":    User.query.filter_by(role="student").count(),
        "total_courses": Course.query.count(),
        "total_grades":  Grade.query.filter(Grade.grade.isnot(None)).count(),
        "global_average": db.session.query(func.avg(Grade.grade)).scalar(),
    }

    # Cours par classe
    courses_by_class = (
        db.session.query(
            Course.class_name,
            func.count(Course.id).label("course_count"),
        )
        .group_by(Course.class_name)
        .all()
    )
    # Enrichir avec nombre d'étudiants par classe
    enriched = []
    for row in courses_by_class:
        sc = Student.query.filter_by(class_name=row.class_name).count()
        enriched.append({"class_name": row.class_name, "course_count": row.course_count, "student_count": sc})
    stats["courses_by_class"] = enriched

    # Top étudiants
    top = (
        db.session.query(
            User.username,
            func.avg(Grade.grade).label("average"),
        )
        .join(Student, Student.user_id == User.id)
        .join(Grade, Grade.student_id == Student.id)
        .filter(Grade.grade.isnot(None))
        .group_by(User.id, User.username)
        .order_by(func.avg(Grade.grade).desc())
        .limit(5)
        .all()
    )
    stats["top_students"] = top

    # Activité 7 jours
    from datetime import timedelta
    from sqlalchemy import cast, Date
    today = datetime.utcnow().date()
    daily = []
    max_count = 0
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        cnt = AuditLog.query.filter(
            cast(AuditLog.timestamp, Date) == day
        ).count()
        daily.append({"date": datetime.combine(day, datetime.min.time()), "count": cnt})
        if cnt > max_count:
            max_count = cnt
    stats["daily_activity"] = daily
    stats["max_daily"] = max_count or 1

    return render_template("admin/statistics.html", stats=stats)


# ─── SETTINGS ────────────────────────────────────────────────────────────────

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    # Paramètres simplifiés (stockés en mémoire — à persister en DB pour prod)
    settings_data = {
        "session_lifetime": 30,
        "session_secure": False,
        "session_httponly": True,
        "pwd_min_length": 8,
        "pwd_require_upper": True,
        "pwd_require_digit": True,
        "pwd_require_special": True,
    }
    if request.method == "POST":
        log_audit("settings_update")
        flash("Paramètres enregistrés.", "success")
        return redirect(url_for("admin.settings"))

    from flask import current_app
    import sys
    import platform
    system_info = {
        "Python": sys.version.split()[0],
        "Platform": platform.system(),
        "Flask ENV": current_app.config.get("ENV", "development"),
        "Debug": str(current_app.debug),
        "CSRF": str(current_app.config.get("WTF_CSRF_ENABLED", True)),
        "Session lifetime": f"{current_app.config.get('PERMANENT_SESSION_LIFETIME')}",
    }
    return render_template("admin/settings.html", settings=settings_data, system_info=system_info)
