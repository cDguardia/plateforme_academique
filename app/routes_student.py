from __future__ import annotations

import secrets
from io import BytesIO

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func

from app.extensions import db, limiter
from app.forms import ProfileStudentForm
from app.models import Attendance, Enseignement, Grade, Matiere, Professor, User, UserSession, log_audit
from app.rbac import student_required

student_bp = Blueprint("student", __name__)


def _get_student_or_403():
    student = current_user.student_profile
    if not student:
        from flask import abort
        abort(403)
    return student


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@student_bp.route("/dashboard")
@login_required
@student_required
def dashboard():
    student = _get_student_or_403()

    enrolled = Grade.query.filter_by(student_id=student.id).count()
    graded = Grade.query.filter_by(student_id=student.id).filter(Grade.grade.isnot(None)).count()
    average = (
        db.session.query(func.avg(Grade.grade))
        .filter_by(student_id=student.id)
        .filter(Grade.grade.isnot(None))
        .scalar()
    )
    pending = enrolled - graded
    stats = {
        "average": float(average) if average else None,
        "enrolled_courses": enrolled,
        "grades_received": graded,
        "pending_grades": pending,
    }

    rows = (
        db.session.query(Grade, Enseignement, Matiere, Professor, User)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .filter(Grade.student_id == student.id)
        .order_by(Matiere.name)
        .limit(5)
        .all()
    )
    my_courses = [
        {
            "course": ens,
            "professor_name": u.username,
            "grade": float(g.grade) if g.grade is not None else None,
        }
        for g, ens, mat, p, u in rows
    ]

    recent = (
        db.session.query(Grade, Enseignement, Matiere)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .filter(Grade.student_id == student.id)
        .filter(Grade.grade.isnot(None))
        .order_by(Grade.graded_at.desc())
        .limit(5)
        .all()
    )
    recent_grades = [
        {"course_name": mat.name, "value": float(g.grade), "graded_at": g.graded_at}
        for g, ens, mat in recent
    ]

    return render_template(
        "dashboard_student.html",
        stats=stats, my_courses=my_courses, recent_grades=recent_grades,
    )


# ─── COURSES ─────────────────────────────────────────────────────────────────

@student_bp.route("/courses")
@login_required
@student_required
def courses():
    student = _get_student_or_403()
    tab = request.args.get("tab", "enrolled")

    enrolled_rows = (
        db.session.query(Grade, Enseignement, Matiere, Professor, User)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .filter(Grade.student_id == student.id)
        .order_by(Matiere.name)
        .all()
    )
    enrolled = [
        {
            "course": ens,
            "professor_name": u.username,
            "grade": float(g.grade) if g.grade is not None else None,
        }
        for g, ens, mat, p, u in enrolled_rows
    ]
    enrolled_ids = {item["course"].id for item in enrolled}

    # Enseignements disponibles pour la classe de l'étudiant (non inscrits)
    if student.classe_id:
        available_rows = (
            db.session.query(Enseignement, Matiere, Professor, User)
            .join(Matiere, Enseignement.matiere_id == Matiere.id)
            .join(Professor, Enseignement.professor_id == Professor.id)
            .join(User, Professor.user_id == User.id)
            .filter(Enseignement.classe_id == student.classe_id)
            .filter(Enseignement.id.notin_(enrolled_ids) if enrolled_ids else True)
            .order_by(Matiere.name)
            .all()
        )
        available_display = []
        for ens, mat, _p, u in available_rows:
            if ens.id not in enrolled_ids:
                available_display.append({
                    "id": ens.id, "name": mat.name, "code": mat.code,
                    "class_name": ens.class_name, "credits": mat.credits,
                    "professor_name": u.username,
                })
    else:
        available_display = []

    return render_template(
        "student/courses.html",
        enrolled=enrolled,
        available=available_display,
        tab=tab,
    )


@student_bp.route("/courses/<int:id>")
@login_required
@student_required
def course_detail(id: int):
    student = _get_student_or_403()
    ens = Enseignement.query.get_or_404(id)

    my_grade_entry = Grade.query.filter_by(
        student_id=student.id, enseignement_id=ens.id
    ).first()
    if not my_grade_entry:
        from flask import abort
        abort(403)

    my_grade = float(my_grade_entry.grade) if my_grade_entry.grade is not None else None
    professor_name = ens.professor.user.username

    grades_all = (
        db.session.query(Grade.grade)
        .filter_by(enseignement_id=ens.id)
        .filter(Grade.grade.isnot(None))
        .all()
    )
    values = [float(r.grade) for r in grades_all]
    class_stats = {
        "student_count": Grade.query.filter_by(enseignement_id=ens.id).count(),
        "average": sum(values) / len(values) if values else None,
        "highest": max(values) if values else None,
        "lowest": min(values) if values else None,
    }

    return render_template(
        "student/course_detail.html",
        course=ens,
        my_grade=my_grade,
        professor_name=professor_name,
        class_stats=class_stats,
    )


@student_bp.route("/courses/enroll", methods=["GET", "POST"])
@login_required
@student_required
def course_enroll():
    student = _get_student_or_403()
    if request.method == "POST":
        try:
            ens_id = int(request.form.get("course_id", 0))
        except ValueError:
            flash("Cours invalide.", "danger")
            return redirect(url_for("student.courses", tab="available"))

        ens = Enseignement.query.get_or_404(ens_id)

        if not student.classe_id or ens.classe_id != student.classe_id:
            flash("Ce cours n'est pas disponible pour votre classe.", "danger")
            return redirect(url_for("student.courses", tab="available"))

        existing = Grade.query.filter_by(
            student_id=student.id, enseignement_id=ens.id
        ).first()
        if existing:
            flash("Vous êtes déjà inscrit à ce cours.", "warning")
            return redirect(url_for("student.courses"))

        db.session.add(Grade(student_id=student.id, enseignement_id=ens.id))
        db.session.commit()
        log_audit("course_enroll", resource_type="enseignement", resource_id=ens.id)
        flash(f"Inscrit au cours « {ens.name} ».", "success")
        return redirect(url_for("student.courses"))

    return redirect(url_for("student.courses", tab="available"))


@student_bp.route("/courses/<int:id>/drop", methods=["POST"])
@login_required
@student_required
def course_drop(id: int):
    student = _get_student_or_403()
    grade_entry = Grade.query.filter_by(
        student_id=student.id, enseignement_id=id
    ).first_or_404()

    if grade_entry.grade is not None:
        flash("Vous ne pouvez pas vous désinscrire d'un cours déjà noté.", "danger")
        return redirect(url_for("student.courses"))

    course_name = grade_entry.enseignement.name
    log_audit("course_drop", resource_type="enseignement", resource_id=id)
    db.session.delete(grade_entry)
    db.session.commit()
    flash(f"Désinscrit du cours « {course_name} ».", "info")
    return redirect(url_for("student.courses"))


# ─── GRADES ──────────────────────────────────────────────────────────────────

@student_bp.route("/grades")
@login_required
@student_required
def grades():
    student = _get_student_or_403()

    rows = (
        db.session.query(Grade, Enseignement, Matiere, Professor, User)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .filter(Grade.student_id == student.id)
        .order_by(Matiere.name)
        .all()
    )

    grade_list = [
        {
            "course_id": ens.id,
            "course_name": mat.name,
            "course_code": mat.code,
            "professor_name": u.username,
            "credits": mat.credits,
            "grade": float(g.grade) if g.grade is not None else None,
            "graded_at": g.graded_at,
        }
        for g, ens, mat, p, u in rows
    ]

    graded = [x for x in grade_list if x["grade"] is not None]
    total_credits = sum(x["credits"] for x in grade_list)
    validated = [x for x in graded if x["grade"] >= 10]
    validated_credits = sum(x["credits"] for x in validated)
    average = (
        sum(x["grade"] for x in graded) / len(graded)
        if graded else None
    )
    summary = {
        "total_courses": len(grade_list),
        "graded": len(graded),
        "validated": len(validated),
        "total_credits": total_credits,
        "validated_credits": validated_credits,
        "average": average,
    }

    return render_template("student/grades.html", grades=grade_list, summary=summary)


@student_bp.route("/grades/export")
@login_required
@student_required
@limiter.limit("5 per minute", error_message="Trop d'exports. Réessayez dans 1 minute.")
def grades_export():
    student = _get_student_or_403()

    rows = (
        db.session.query(Grade, Enseignement, Matiere, Professor, User)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .join(Professor, Enseignement.professor_id == Professor.id)
        .join(User, Professor.user_id == User.id)
        .filter(Grade.student_id == student.id)
        .order_by(Matiere.name)
        .all()
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
    )
    normal_style = styles['Normal']

    story = []
    story.append(Paragraph("Relevé de Notes", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Étudiant: {current_user.username}", normal_style))
    story.append(Paragraph(f"Numéro étudiant: {student.student_number}", normal_style))
    story.append(Paragraph(f"Classe: {student.class_name or 'N/A'}", normal_style))
    story.append(Spacer(1, 12))

    data = [["Cours", "Code", "Crédits", "Note", "Date"]]
    for g, ens, mat, _p, _u in rows:
        grade_val = f"{float(g.grade):.2f}" if g.grade is not None else "En attente"
        date_val = g.graded_at.strftime("%d/%m/%Y") if g.graded_at else "\u2014"
        data.append([mat.name, mat.code, str(mat.credits), grade_val, date_val])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    doc.build(story)

    filename = f"releve_{secrets.token_hex(8)}.pdf"
    log_audit("grades_export_pdf", resource_type="student", resource_id=student.id)
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )


# ─── ATTENDANCE (vue étudiant) ───────────────────────────────────────────────

@student_bp.route("/attendance")
@login_required
@student_required
def attendance():
    student = _get_student_or_403()

    rows = (
        db.session.query(Attendance, Enseignement, Matiere)
        .join(Enseignement, Attendance.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .filter(Attendance.student_id == student.id)
        .order_by(Attendance.date.desc())
        .all()
    )

    records = [
        {
            "date": a.date,
            "course_name": mat.name,
            "course_code": mat.code,
            "status": a.status,
        }
        for a, ens, mat in rows
    ]

    total = len(records)
    absents = sum(1 for r in records if r["status"] == "absent")
    lates = sum(1 for r in records if r["status"] == "late")
    presents = total - absents - lates

    summary = {
        "total": total,
        "presents": presents,
        "absents": absents,
        "lates": lates,
    }

    return render_template("student/attendance.html", records=records, summary=summary)


# ─── PROFILE ─────────────────────────────────────────────────────────────────

@student_bp.route("/profile")
@login_required
@student_required
def profile():
    student = _get_student_or_403()

    graded = Grade.query.filter_by(student_id=student.id).filter(Grade.grade.isnot(None)).all()
    avg = sum(float(g.grade) for g in graded) / len(graded) if graded else None
    validated = [g for g in graded if float(g.grade) >= 10]
    total_credits = sum(g.enseignement.credits for g in Grade.query.filter_by(student_id=student.id).all())
    validated_credits = sum(g.enseignement.credits for g in validated)

    academic = {
        "average": avg,
        "total_credits": total_credits,
        "validated_credits": validated_credits,
    }
    form = ProfileStudentForm(
        username=current_user.username,
        email=current_user.email,
    )
    return render_template(
        "student/profile.html", student=student, form=form, academic=academic
    )


@student_bp.route("/profile/edit", methods=["POST"])
@login_required
@student_required
def profile_edit():
    form = ProfileStudentForm()
    if form.validate_on_submit():
        new_username = form.username.data.strip()
        new_email = form.email.data.strip().lower()

        if new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash("Ce nom d'utilisateur est déjà pris.", "danger")
                return redirect(url_for("student.profile"))
        if new_email != current_user.email:
            if User.query.filter_by(email=new_email).first():
                flash("Cet email est déjà utilisé.", "danger")
                return redirect(url_for("student.profile"))

        current_user.username = new_username
        current_user.email = new_email
        db.session.commit()
        log_audit("profile_edit")
        flash("Profil mis à jour.", "success")
    return redirect(url_for("student.profile"))


# ─── SESSIONS ────────────────────────────────────────────────────────────────

@student_bp.route("/profile/sessions")
@login_required
@student_required
def sessions():
    user_sessions = UserSession.query.filter_by(
        user_id=current_user.id, revoked=False
    ).order_by(UserSession.created_at.desc()).all()
    return render_template("student/sessions.html", sessions=user_sessions)


@student_bp.route("/profile/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
@student_required
def revoke_session(session_id):
    session_to_revoke = UserSession.query.filter_by(
        id=session_id, user_id=current_user.id, revoked=False
    ).first()
    if not session_to_revoke:
        flash("Session introuvable.", "danger")
        return redirect(url_for("student.sessions"))

    session_to_revoke.revoked = True
    db.session.commit()
    log_audit("session_revoked")
    flash("Session révoquée.", "success")
    return redirect(url_for("student.sessions"))
