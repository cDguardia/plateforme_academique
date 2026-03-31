from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms import ChangePasswordForm, LoginForm, RegisterForm
from app.models import AuditLog, Professor, Student, User, log_audit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=False)
            # Force session permanente pour gérer l'expiration
            from flask import session
            session.permanent = True
            log_audit("login_success")
            flash("Connexion établie.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        log_audit("login_failed", username=form.username.data.strip())
        flash("Identifiants invalides ou compte inactif.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_audit("logout")
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        # Créer le profil étendu selon le rôle
        if user.role == "professor":
            db.session.add(Professor(user_id=user.id))
        elif user.role == "student":
            # Générer un numéro étudiant unique
            count = Student.query.count() + 1
            student_number = f"GCS2-{count:03d}"
            db.session.add(Student(user_id=user.id, student_number=student_number))

        db.session.commit()
        log_audit("register", resource_type="user", resource_id=user.id)
        flash("Compte créé avec succès. Vous pouvez vous connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Mot de passe actuel incorrect.", "danger")
            return render_template("change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        log_audit("password_change")
        flash("Mot de passe mis à jour avec succès.", "success")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html", form=form)
