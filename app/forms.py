from __future__ import annotations

import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError

from app.models import User


# ─── VALIDATION HELPERS ──────────────────────────────────────────────────────

def _validate_password_strength(form, field) -> None:  # noqa: ANN001
    pwd = field.data or ""
    if len(pwd) < 8:
        raise ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
    if not re.search(r"[A-Z]", pwd):
        raise ValidationError("Le mot de passe doit contenir au moins une majuscule.")
    if not re.search(r"\d", pwd):
        raise ValidationError("Le mot de passe doit contenir au moins un chiffre.")
    if not re.search(r"[^A-Za-z0-9]", pwd):
        raise ValidationError("Le mot de passe doit contenir au moins un caractère spécial.")


# ─── AUTH FORMS ──────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    username = StringField(
        "Nom d'utilisateur",
        validators=[DataRequired("Ce champ est requis."), Length(max=80)],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired("Ce champ est requis.")],
    )


class RegisterForm(FlaskForm):
    username = StringField(
        "Nom d'utilisateur",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    email = StringField(
        "Adresse e-mail",
        validators=[DataRequired(), Email("Adresse e-mail invalide."), Length(max=120)],
    )
    role = SelectField(
        "Rôle",
        choices=[("student", "Étudiant")],
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired(), _validate_password_strength],
    )
    password_confirm = PasswordField(
        "Confirmer le mot de passe",
        validators=[DataRequired(), EqualTo("password", "Les mots de passe ne correspondent pas.")],
    )

    def validate_role(self, field) -> None:  # noqa: ANN001
        if field.data not in ("student",):
            raise ValidationError("Seul le rôle étudiant est disponible à l'inscription.")

    def validate_username(self, field) -> None:  # noqa: ANN001
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("Impossible de créer ce compte.")

    def validate_email(self, field) -> None:  # noqa: ANN001
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("Impossible de créer ce compte.")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "Mot de passe actuel",
        validators=[DataRequired()],
    )
    new_password = PasswordField(
        "Nouveau mot de passe",
        validators=[DataRequired(), _validate_password_strength],
    )
    new_password_confirm = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[DataRequired(), EqualTo("new_password", "Les mots de passe ne correspondent pas.")],
    )


# ─── ADMIN FORMS ─────────────────────────────────────────────────────────────

class UserCreateForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Rôle",
        choices=[("student", "Étudiant"), ("professor", "Professeur"), ("admin", "Admin")],
        validators=[DataRequired()],
    )
    password = PasswordField("Mot de passe", validators=[DataRequired(), _validate_password_strength])
    password_confirm = PasswordField(
        "Confirmer",
        validators=[DataRequired(), EqualTo("password", "Mots de passe différents.")],
    )
    is_active = BooleanField("Compte actif", default=True)

    def validate_username(self, field) -> None:  # noqa: ANN001
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("Nom d'utilisateur déjà pris.")

    def validate_email(self, field) -> None:  # noqa: ANN001
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("Email déjà utilisé.")


class UserEditForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField(
        "Rôle",
        choices=[("student", "Étudiant"), ("professor", "Professeur"), ("admin", "Admin")],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Compte actif")


# ─── CLASSE FORMS ────────────────────────────────────────────────────────────

class ClasseForm(FlaskForm):
    name = StringField("Nom de la classe", validators=[DataRequired(), Length(max=50)])
    description = StringField("Description", validators=[Optional(), Length(max=200)])


# ─── MATIERE FORMS ───────────────────────────────────────────────────────────

class MatiereForm(FlaskForm):
    name = StringField("Intitulé de la matière", validators=[DataRequired(), Length(max=200)])
    code = StringField("Code", validators=[DataRequired(), Length(max=20)])
    credits = IntegerField("Crédits ECTS", validators=[DataRequired(), NumberRange(min=1, max=30)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])


# ─── ENSEIGNEMENT FORMS ──────────────────────────────────────────────────────

class EnseignementForm(FlaskForm):
    matiere_id = SelectField("Matière", coerce=int, validators=[DataRequired()])
    classe_id = SelectField("Classe", coerce=int, validators=[DataRequired()])
    professor_id = SelectField("Professeur", coerce=int, validators=[DataRequired()])


# ─── PROFILE FORMS ───────────────────────────────────────────────────────────

class ProfileProfessorForm(FlaskForm):
    department = StringField("Département", validators=[Optional(), Length(max=100)])
    specialization = TextAreaField("Spécialisation", validators=[Optional(), Length(max=500)])


class ProfileStudentForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])


# ─── 2FA FORM ────────────────────────────────────────────────────────────────

class TotpForm(FlaskForm):
    code = StringField(
        "Code à 6 chiffres",
        validators=[
            DataRequired("Ce champ est requis."),
            Regexp(r"^\d{6}$", message="Le code doit contenir exactement 6 chiffres."),
        ],
    )


# ─── MESSAGE FORMS ───────────────────────────────────────────────────────────

class MessageForm(FlaskForm):
    receiver_id = SelectField("Destinataire", coerce=int, validators=[DataRequired()])
    subject = StringField("Sujet", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField(
        "Message",
        validators=[DataRequired(), Length(min=1, max=2000)],
    )


# ─── SCHEDULE FORMS ──────────────────────────────────────────────────────────

class ScheduleForm(FlaskForm):
    enseignement_id = SelectField("Enseignement", coerce=int, validators=[DataRequired()])
    day_of_week = SelectField(
        "Jour",
        choices=[(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"),
                 (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi")],
        coerce=int,
        validators=[DataRequired()],
    )
    start_time = StringField(
        "Heure début (HH:MM)",
        validators=[DataRequired(), Regexp(r"^\d{2}:\d{2}$", message="Format HH:MM requis.")],
    )
    end_time = StringField(
        "Heure fin (HH:MM)",
        validators=[DataRequired(), Regexp(r"^\d{2}:\d{2}$", message="Format HH:MM requis.")],
    )
    room = StringField("Salle", validators=[Optional(), Length(max=50)])
