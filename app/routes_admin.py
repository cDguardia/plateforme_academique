from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.forms import ClasseForm, EnseignementForm, MatiereForm, UserCreateForm, UserEditForm
from app.models import (
    AuditLog, Classe, Enseignement, Grade, Matiere, Professor,
    SecurityPolicy, Student, User, log_audit,
)
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
        "classes":     Classe.query.count(),
        "matieres":    Matiere.query.count(),
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
            db.session.add(Student(user_id=user.id, student_number=f"ETU-{count:03d}"))

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
        if form.username.data.strip() != user.username:
            if User.query.filter_by(username=form.username.data.strip()).first():
                flash("Ce nom d'utilisateur est déjà pris.", "danger")
                return render_template("admin/user_form.html", form=form, user=user)
        if form.email.data.strip().lower() != user.email:
            if User.query.filter_by(email=form.email.data.strip().lower()).first():
                flash("Cet email est déjà utilisé.", "danger")
                return render_template("admin/user_form.html", form=form, user=user)

        user.username = form.username.data.strip()
        user.email = form.email.data.strip().lower()
        user.role = form.role.data
        user.is_active = form.is_active.data

        if user.role == "professor" and not user.professor_profile:
            db.session.add(Professor(user_id=user.id))
        elif user.role == "student" and not user.student_profile:
            count = Student.query.count() + 1
            db.session.add(Student(user_id=user.id, student_number=f"ETU-{count:03d}"))

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


# ─── CLASSES ─────────────────────────────────────────────────────────────────

@admin_bp.route("/classes")
@login_required
@admin_required
def classes():
    classe_list = Classe.query.order_by(Classe.name).all()
    enriched = []
    for c in classe_list:
        enriched.append({
            "classe": c,
            "student_count": c.students.count(),
            "enseignement_count": c.enseignements.count(),
        })
    return render_template("admin/classes.html", classes=enriched)


@admin_bp.route("/classes/create", methods=["GET", "POST"])
@login_required
@admin_required
def classe_create():
    form = ClasseForm()
    if form.validate_on_submit():
        name = form.name.data.strip().upper()
        if Classe.query.filter_by(name=name).first():
            flash("Cette classe existe déjà.", "danger")
            return render_template("admin/classe_form.html", form=form, classe=None)
        classe = Classe(
            name=name,
            description=form.description.data.strip() if form.description.data else None,
        )
        db.session.add(classe)
        db.session.commit()
        log_audit("classe_create", resource_type="classe", resource_id=classe.id)
        flash(f"Classe « {classe.name} » créée.", "success")
        return redirect(url_for("admin.classes"))
    return render_template("admin/classe_form.html", form=form, classe=None)


@admin_bp.route("/classes/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def classe_edit(id: int):
    classe = Classe.query.get_or_404(id)
    form = ClasseForm(obj=classe)
    if form.validate_on_submit():
        name = form.name.data.strip().upper()
        existing = Classe.query.filter_by(name=name).first()
        if existing and existing.id != classe.id:
            flash("Ce nom de classe est déjà utilisé.", "danger")
            return render_template("admin/classe_form.html", form=form, classe=classe)
        classe.name = name
        classe.description = form.description.data.strip() if form.description.data else None
        db.session.commit()
        log_audit("classe_edit", resource_type="classe", resource_id=classe.id)
        flash(f"Classe « {classe.name} » modifiée.", "success")
        return redirect(url_for("admin.classes"))
    return render_template("admin/classe_form.html", form=form, classe=classe)


@admin_bp.route("/classes/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def classe_delete(id: int):
    classe = Classe.query.get_or_404(id)
    name = classe.name
    log_audit("classe_delete", resource_type="classe", resource_id=id)
    db.session.delete(classe)
    db.session.commit()
    flash(f"Classe « {name} » supprimée.", "success")
    return redirect(url_for("admin.classes"))


@admin_bp.route("/classes/<int:id>")
@login_required
@admin_required
def classe_detail(id: int):
    classe = Classe.query.get_or_404(id)
    students = (
        db.session.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.classe_id == classe.id)
        .order_by(User.username)
        .all()
    )
    enseignements = (
        db.session.query(Enseignement, Matiere, Professor, User)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .filter(Enseignement.classe_id == classe.id)
        .order_by(Matiere.name)
        .all()
    )
    # Étudiants non affectés à cette classe (pour le select d'ajout)
    unassigned = (
        db.session.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter((Student.classe_id.is_(None)) | (Student.classe_id != classe.id))
        .order_by(User.username)
        .all()
    )
    return render_template(
        "admin/classe_detail.html",
        classe=classe, students=students, enseignements=enseignements, unassigned=unassigned,
    )


@admin_bp.route("/classes/<int:id>/add-student", methods=["POST"])
@login_required
@admin_required
def classe_add_student(id: int):
    classe = Classe.query.get_or_404(id)
    student_id = request.form.get("student_id", type=int)
    if student_id:
        student = Student.query.get_or_404(student_id)
        student.classe_id = classe.id
        db.session.commit()
        log_audit("classe_add_student", resource_type="classe", resource_id=classe.id)
        flash(f"Étudiant « {student.user.username} » ajouté à {classe.name}.", "success")
    return redirect(url_for("admin.classe_detail", id=classe.id))


@admin_bp.route("/classes/<int:id>/remove-student/<int:student_id>", methods=["POST"])
@login_required
@admin_required
def classe_remove_student(id: int, student_id: int):
    classe = Classe.query.get_or_404(id)
    student = Student.query.get_or_404(student_id)
    if student.classe_id == classe.id:
        student.classe_id = None
        db.session.commit()
        log_audit("classe_remove_student", resource_type="classe", resource_id=classe.id)
        flash(f"Étudiant « {student.user.username} » retiré de {classe.name}.", "info")
    return redirect(url_for("admin.classe_detail", id=classe.id))


# ─── MATIERES ────────────────────────────────────────────────────────────────

@admin_bp.route("/matieres")
@login_required
@admin_required
def matieres():
    matiere_list = Matiere.query.order_by(Matiere.name).all()
    enriched = []
    for m in matiere_list:
        enriched.append({
            "matiere": m,
            "enseignement_count": m.enseignements.count(),
        })
    return render_template("admin/matieres.html", matieres=enriched)


@admin_bp.route("/matieres/create", methods=["GET", "POST"])
@login_required
@admin_required
def matiere_create():
    form = MatiereForm()
    if form.validate_on_submit():
        code = form.code.data.upper().strip()
        if Matiere.query.filter_by(code=code).first():
            flash("Ce code de matière existe déjà.", "danger")
            return render_template("admin/matiere_form.html", form=form, matiere=None)
        matiere = Matiere(
            name=form.name.data.strip(),
            code=code,
            credits=form.credits.data,
            description=form.description.data.strip() if form.description.data else None,
        )
        db.session.add(matiere)
        db.session.commit()
        log_audit("matiere_create", resource_type="matiere", resource_id=matiere.id)
        flash(f"Matière « {matiere.name} » créée.", "success")
        return redirect(url_for("admin.matieres"))
    return render_template("admin/matiere_form.html", form=form, matiere=None)


@admin_bp.route("/matieres/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def matiere_edit(id: int):
    matiere = Matiere.query.get_or_404(id)
    form = MatiereForm(obj=matiere)
    if form.validate_on_submit():
        code = form.code.data.upper().strip()
        existing = Matiere.query.filter_by(code=code).first()
        if existing and existing.id != matiere.id:
            flash("Ce code de matière est déjà utilisé.", "danger")
            return render_template("admin/matiere_form.html", form=form, matiere=matiere)
        matiere.name = form.name.data.strip()
        matiere.code = code
        matiere.credits = form.credits.data
        matiere.description = form.description.data.strip() if form.description.data else None
        db.session.commit()
        log_audit("matiere_edit", resource_type="matiere", resource_id=matiere.id)
        flash(f"Matière « {matiere.name} » modifiée.", "success")
        return redirect(url_for("admin.matieres"))
    return render_template("admin/matiere_form.html", form=form, matiere=matiere)


@admin_bp.route("/matieres/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def matiere_delete(id: int):
    matiere = Matiere.query.get_or_404(id)
    name = matiere.name
    log_audit("matiere_delete", resource_type="matiere", resource_id=id)
    db.session.delete(matiere)
    db.session.commit()
    flash(f"Matière « {name} » supprimée.", "success")
    return redirect(url_for("admin.matieres"))


# ─── ENSEIGNEMENTS ───────────────────────────────────────────────────────────

@admin_bp.route("/enseignements")
@login_required
@admin_required
def enseignements():
    rows = (
        db.session.query(Enseignement, Matiere, Classe, Professor, User)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Classe, Enseignement.classe_id == Classe.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .order_by(Classe.name, Matiere.name)
        .all()
    )
    return render_template("admin/enseignements.html", enseignements=rows)


@admin_bp.route("/enseignements/create", methods=["GET", "POST"])
@login_required
@admin_required
def enseignement_create():
    form = EnseignementForm()
    form.matiere_id.choices = [(m.id, f"{m.code} — {m.name}") for m in Matiere.query.order_by(Matiere.name).all()]
    form.classe_id.choices = [(c.id, c.name) for c in Classe.query.order_by(Classe.name).all()]
    form.professor_id.choices = [
        (p.id, f"{p.user.username} ({p.department or 'N/A'})")
        for p in Professor.query.join(User, Professor.user_id == User.id).order_by(User.username).all()
    ]
    if form.validate_on_submit():
        existing = Enseignement.query.filter_by(
            matiere_id=form.matiere_id.data, classe_id=form.classe_id.data
        ).first()
        if existing:
            flash("Cette matière est déjà enseignée dans cette classe.", "danger")
            return render_template("admin/enseignement_form.html", form=form, enseignement=None)
        ens = Enseignement(
            matiere_id=form.matiere_id.data,
            classe_id=form.classe_id.data,
            professor_id=form.professor_id.data,
        )
        db.session.add(ens)
        db.session.commit()
        log_audit("enseignement_create", resource_type="enseignement", resource_id=ens.id)
        flash("Enseignement créé.", "success")
        return redirect(url_for("admin.enseignements"))
    return render_template("admin/enseignement_form.html", form=form, enseignement=None)


@admin_bp.route("/enseignements/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def enseignement_edit(id: int):
    ens = Enseignement.query.get_or_404(id)
    form = EnseignementForm(obj=ens)
    form.matiere_id.choices = [(m.id, f"{m.code} — {m.name}") for m in Matiere.query.order_by(Matiere.name).all()]
    form.classe_id.choices = [(c.id, c.name) for c in Classe.query.order_by(Classe.name).all()]
    form.professor_id.choices = [
        (p.id, f"{p.user.username} ({p.department or 'N/A'})")
        for p in Professor.query.join(User, Professor.user_id == User.id).order_by(User.username).all()
    ]
    if form.validate_on_submit():
        existing = Enseignement.query.filter_by(
            matiere_id=form.matiere_id.data, classe_id=form.classe_id.data
        ).first()
        if existing and existing.id != ens.id:
            flash("Cette matière est déjà enseignée dans cette classe.", "danger")
            return render_template("admin/enseignement_form.html", form=form, enseignement=ens)
        ens.matiere_id = form.matiere_id.data
        ens.classe_id = form.classe_id.data
        ens.professor_id = form.professor_id.data
        db.session.commit()
        log_audit("enseignement_edit", resource_type="enseignement", resource_id=ens.id)
        flash("Enseignement modifié.", "success")
        return redirect(url_for("admin.enseignements"))
    return render_template("admin/enseignement_form.html", form=form, enseignement=ens)


@admin_bp.route("/enseignements/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def enseignement_delete(id: int):
    ens = Enseignement.query.get_or_404(id)
    log_audit("enseignement_delete", resource_type="enseignement", resource_id=id)
    db.session.delete(ens)
    db.session.commit()
    flash("Enseignement supprimé.", "success")
    return redirect(url_for("admin.enseignements"))


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
        "total_classes": Classe.query.count(),
        "total_matieres": Matiere.query.count(),
        "total_enseignements": Enseignement.query.count(),
        "total_grades":  Grade.query.filter(Grade.grade.isnot(None)).count(),
        "global_average": db.session.query(func.avg(Grade.grade)).scalar(),
    }

    # Enseignements par classe — une seule requête (pas de N+1)
    ens_by_class = (
        db.session.query(
            Classe.id,
            Classe.name,
            func.count(func.distinct(Enseignement.id)).label("ens_count"),
            func.count(func.distinct(Student.id)).label("student_count"),
        )
        .outerjoin(Enseignement, Enseignement.classe_id == Classe.id)
        .outerjoin(Student, Student.classe_id == Classe.id)
        .group_by(Classe.id, Classe.name)
        .all()
    )
    stats["courses_by_class"] = [
        {"class_name": row.name, "course_count": row.ens_count, "student_count": row.student_count}
        for row in ens_by_class
    ]

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
    policy = SecurityPolicy.get_policy()

    if request.method == "POST":
        section = request.form.get("section", "")

        if section == "session":
            lifetime = request.form.get("session_lifetime_minutes", "30")
            try:
                policy.session_lifetime_minutes = max(5, min(1440, int(lifetime)))
            except ValueError:
                policy.session_lifetime_minutes = 30
            policy.session_secure_cookie = "session_secure_cookie" in request.form
            policy.session_httponly = "session_httponly" in request.form
            policy.session_fingerprint_enabled = "session_fingerprint_enabled" in request.form

        elif section == "auth":
            attempts = request.form.get("max_login_attempts", "5")
            lockout = request.form.get("lockout_duration_minutes", "15")
            try:
                policy.max_login_attempts = max(1, min(20, int(attempts)))
            except ValueError:
                policy.max_login_attempts = 5
            try:
                policy.lockout_duration_minutes = max(1, min(120, int(lockout)))
            except ValueError:
                policy.lockout_duration_minutes = 15
            policy.account_lockout_enabled = "account_lockout_enabled" in request.form
            policy.totp_2fa_available = "totp_2fa_available" in request.form

        elif section == "password":
            pwd_len = request.form.get("pwd_min_length", "8")
            try:
                policy.pwd_min_length = max(6, min(128, int(pwd_len)))
            except ValueError:
                policy.pwd_min_length = 8
            policy.pwd_require_upper = "pwd_require_upper" in request.form
            policy.pwd_require_digit = "pwd_require_digit" in request.form
            policy.pwd_require_special = "pwd_require_special" in request.form

        elif section == "rate_limiting":
            policy.rate_limiting_enabled = "rate_limiting_enabled" in request.form
            rate = request.form.get("login_rate_limit", "5 per minute").strip()
            if rate:
                policy.login_rate_limit = rate[:30]

        elif section == "audit":
            policy.audit_logging_enabled = "audit_logging_enabled" in request.form

        from datetime import timezone as tz
        policy.updated_at = datetime.now(tz.utc)
        db.session.commit()
        log_audit("security_policy_update", resource_type="security_policy")
        flash("Politique de securite mise a jour.", "success")
        return redirect(url_for("admin.settings"))

    import sys
    import platform
    from flask import current_app
    system_info = {
        "Python": sys.version.split()[0],
        "Plateforme": platform.system(),
        "Flask ENV": current_app.config.get("ENV", "development"),
        "Debug": str(current_app.debug),
        "CSRF": str(current_app.config.get("WTF_CSRF_ENABLED", True)),
        "Session lifetime": f"{policy.session_lifetime_minutes} min",
    }
    return render_template(
        "admin/settings.html", policy=policy, system_info=system_info,
    )
