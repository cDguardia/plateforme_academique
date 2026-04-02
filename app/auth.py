from __future__ import annotations

import base64
import io

import pyotp
import qrcode
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.forms import ChangePasswordForm, LoginForm, RegisterForm, TotpForm
from app.models import Professor, Student, User, log_audit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", error_message="Trop de tentatives. Réessayez dans 1 minute.")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()

        if user and user.is_active and user.check_password(form.password.data):
            if user.totp_enabled:
                # Stocker l'ID en session pré-auth, rediriger vers vérification 2FA
                session["pre_auth_user_id"] = user.id
                session.permanent = True
                return redirect(url_for("auth.two_fa_verify"))

            login_user(user, remember=False)
            session.permanent = True
            log_audit("login_success")
            flash("Connexion établie.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        log_audit("login_failed", username=form.username.data.strip())
        flash("Identifiants invalides ou compte inactif.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/2fa/verify", methods=["GET", "POST"])
def two_fa_verify():
    user_id = session.get("pre_auth_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user or not user.totp_enabled:
        session.pop("pre_auth_user_id", None)
        return redirect(url_for("auth.login"))

    form = TotpForm()
    if form.validate_on_submit():
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(form.code.data.strip(), valid_window=1):
            session.pop("pre_auth_user_id", None)
            login_user(user, remember=False)
            session.permanent = True
            log_audit("login_success_2fa")
            flash("Connexion établie avec 2FA.", "success")
            return redirect(url_for("dashboard"))
        flash("Code invalide ou expiré.", "danger")

    return render_template("2fa_verify.html", form=form)


@auth_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def two_fa_setup():
    if current_user.totp_enabled:
        flash("Le 2FA est déjà activé sur votre compte.", "info")
        return redirect(url_for("dashboard"))

    # Générer un secret si pas encore fait
    if not current_user.totp_secret:
        current_user.totp_secret = pyotp.random_base32()
        db.session.commit()

    totp = pyotp.TOTP(current_user.totp_secret)
    uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Guardia EDU"
    )

    # Générer le QR code en base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    form = TotpForm()
    if form.validate_on_submit():
        totp_check = pyotp.TOTP(current_user.totp_secret)
        if totp_check.verify(form.code.data.strip(), valid_window=1):
            current_user.totp_enabled = True
            db.session.commit()
            log_audit("2fa_enabled")
            flash("2FA activé avec succès.", "success")
            return redirect(url_for("dashboard"))
        flash("Code invalide. Vérifiez l'heure de votre téléphone.", "danger")

    return render_template("2fa_setup.html", form=form, qr_b64=qr_b64,
                           secret=current_user.totp_secret)


@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def two_fa_disable():
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    log_audit("2fa_disabled")
    flash("2FA désactivé.", "info")
    return redirect(url_for("dashboard"))


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

        if user.role == "professor":
            db.session.add(Professor(user_id=user.id))
        elif user.role == "student":
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
