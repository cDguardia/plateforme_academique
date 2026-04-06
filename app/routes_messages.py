from __future__ import annotations

import bleach
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import MessageForm
from app.models import Enseignement, Grade, Message, Professor, Student, User, log_audit

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")

ALLOWED_TAGS: list[str] = []  # Aucun HTML autorisé


def _get_allowed_contacts() -> list[User]:
    """Retourne les utilisateurs avec qui le current_user peut communiquer."""
    if current_user.role == "student":
        student = current_user.student_profile
        if not student:
            return []
        # Profs des enseignements auxquels l'étudiant est inscrit
        prof_ids = (
            db.session.query(Professor.user_id)
            .join(Enseignement, Enseignement.professor_id == Professor.id)
            .join(Grade, Grade.enseignement_id == Enseignement.id)
            .filter(Grade.student_id == student.id)
            .distinct()
            .all()
        )
        ids = [r.user_id for r in prof_ids]
        return User.query.filter(User.id.in_(ids)).order_by(User.username).all()

    elif current_user.role == "professor":
        prof = current_user.professor_profile
        if not prof:
            return []
        # Étudiants inscrits dans ses enseignements
        student_user_ids = (
            db.session.query(Student.user_id)
            .join(Grade, Grade.student_id == Student.id)
            .join(Enseignement, Grade.enseignement_id == Enseignement.id)
            .filter(Enseignement.professor_id == prof.id)
            .distinct()
            .all()
        )
        ids = [r.user_id for r in student_user_ids]
        return User.query.filter(User.id.in_(ids)).order_by(User.username).all()

    elif current_user.role == "admin":
        return User.query.filter(User.id != current_user.id).order_by(User.username).all()

    return []


@messages_bp.route("/")
@login_required
def inbox():
    page = request.args.get("page", 1, type=int)
    msgs = (
        Message.query
        .filter_by(receiver_id=current_user.id)
        .order_by(Message.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    unread = Message.query.filter_by(receiver_id=current_user.id, read_at=None).count()
    return render_template("messages/inbox.html", msgs=msgs, unread=unread)


@messages_bp.route("/sent")
@login_required
def sent():
    page = request.args.get("page", 1, type=int)
    msgs = (
        Message.query
        .filter_by(sender_id=current_user.id)
        .order_by(Message.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("messages/sent.html", msgs=msgs)


@messages_bp.route("/<int:id>")
@login_required
def read(id: int):
    msg = Message.query.get_or_404(id)
    # IDOR protection : seuls expéditeur et destinataire peuvent lire
    if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
        abort(403)

    # Marquer comme lu si destinataire
    if msg.receiver_id == current_user.id and not msg.is_read:
        from datetime import datetime
        msg.read_at = datetime.utcnow()
        db.session.commit()

    return render_template("messages/read.html", msg=msg)


@messages_bp.route("/compose", methods=["GET", "POST"])
@login_required
def compose():
    contacts = _get_allowed_contacts()
    form = MessageForm()
    form.receiver_id.choices = [(u.id, u.username) for u in contacts]

    # Pré-remplir si reply
    reply_to = request.args.get("reply_to", type=int)
    if reply_to and request.method == "GET":
        orig = Message.query.get(reply_to)
        if orig and (orig.receiver_id == current_user.id or orig.sender_id == current_user.id):
            form.receiver_id.data = orig.sender_id
            subject = orig.subject
            form.subject.data = subject if subject.startswith("Re: ") else f"Re: {subject}"

    if form.validate_on_submit():
        receiver_id = form.receiver_id.data
        # Vérifier que le destinataire est dans la liste autorisée
        allowed_ids = {u.id for u in contacts}
        if receiver_id not in allowed_ids:
            abort(403)

        clean_subject = bleach.clean(form.subject.data, tags=[], strip=True)[:200]
        clean_body = bleach.clean(form.body.data, tags=ALLOWED_TAGS, strip=True)[:2000]

        msg = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            subject=clean_subject,
            body=clean_body,
        )
        db.session.add(msg)
        db.session.commit()
        log_audit("message_sent", resource_type="message", resource_id=msg.id)
        flash("Message envoyé.", "success")
        return redirect(url_for("messages.inbox"))

    return render_template("messages/compose.html", form=form, contacts=contacts)


@messages_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id: int):
    msg = Message.query.get_or_404(id)
    if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
        abort(403)
    db.session.delete(msg)
    db.session.commit()
    flash("Message supprimé.", "info")
    return redirect(url_for("messages.inbox"))
