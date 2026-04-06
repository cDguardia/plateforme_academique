from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, func

from app.extensions import db
from app.forms import ProfileProfessorForm
from app.models import Attendance, Enseignement, Grade, Matiere, Student, User, log_audit
from app.rbac import professor_required

professor_bp = Blueprint("professor", __name__)


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@professor_bp.route("/dashboard")
@login_required
@professor_required
def dashboard():
    prof = current_user.professor_profile
    if not prof:
        flash("Profil professeur introuvable.", "danger")
        return redirect(url_for("auth.login"))

    my_ens = prof.enseignements.all()
    my_ens_ids = [e.id for e in my_ens]

    # Une seule requête agrégée au lieu de N+1
    if my_ens_ids:
        grade_stats = (
            db.session.query(
                func.count(Grade.id).label("total"),
                func.count(Grade.grade).label("graded"),
            )
            .filter(Grade.enseignement_id.in_(my_ens_ids))
            .first()
        )
        total_students = grade_stats.total
        grades_given = grade_stats.graded
    else:
        total_students = 0
        grades_given = 0

    pending = total_students - grades_given
    stats = {
        "my_courses": len(my_ens),
        "total_students": total_students,
        "grades_given": grades_given,
        "pending_grades": pending,
    }

    courses_preview = []
    for e in my_ens[:5]:
        sc = Grade.query.filter_by(enseignement_id=e.id).count()
        courses_preview.append({
            "id": e.id, "name": e.name, "code": e.code,
            "class_name": e.class_name, "student_count": sc,
        })

    recent = (
        db.session.query(Grade, Student, User, Enseignement, Matiere)
        .join(Student, Grade.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(Enseignement, Grade.enseignement_id == Enseignement.id)
        .join(Matiere, Enseignement.matiere_id == Matiere.id)
        .filter(Enseignement.professor_id == prof.id)
        .filter(Grade.grade.isnot(None))
        .order_by(desc(Grade.graded_at))
        .limit(8)
        .all()
    )
    recent_grades = [
        {
            "student_name": u.username,
            "course_name": mat.name,
            "value": float(g.grade),
            "graded_at": g.graded_at,
        }
        for g, s, u, ens, mat in recent
    ]

    return render_template(
        "dashboard_professor.html",
        stats=stats,
        my_courses=courses_preview,
        recent_grades=recent_grades,
    )


# ─── COURSES (enseignements du prof) ────────────────────────────────────────

@professor_bp.route("/courses")
@login_required
@professor_required
def courses():
    prof = current_user.professor_profile
    if not prof:
        return redirect(url_for("professor.dashboard"))

    course_list = []
    for e in prof.enseignements.join(Matiere).order_by(Matiere.name).all():
        sc = Grade.query.filter_by(enseignement_id=e.id).count()
        avg = (
            db.session.query(func.avg(Grade.grade))
            .filter_by(enseignement_id=e.id).filter(Grade.grade.isnot(None)).scalar()
        )
        course_list.append({
            "id": e.id, "name": e.name, "code": e.code,
            "class_name": e.class_name, "credits": e.credits,
            "student_count": sc,
            "average": float(avg) if avg else None,
        })
    return render_template("professor/courses.html", courses=course_list)


@professor_bp.route("/courses/<int:id>")
@login_required
@professor_required
def course_detail(id: int):
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    sc = Grade.query.filter_by(enseignement_id=ens.id).count()
    avg = (
        db.session.query(func.avg(Grade.grade))
        .filter_by(enseignement_id=ens.id)
        .filter(Grade.grade.isnot(None))
        .scalar()
    )
    given = (
        Grade.query.filter_by(enseignement_id=ens.id)
        .filter(Grade.grade.isnot(None))
        .count()
    )
    stats = {
        "student_count": sc,
        "average": float(avg) if avg else None,
        "grades_given": given,
        "pending": sc - given,
    }

    rows = (
        db.session.query(Grade, Student, User)
        .join(Student, Grade.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(Grade.enseignement_id == ens.id)
        .order_by(User.username)
        .all()
    )
    students = [
        {
            "student_number": s.student_number,
            "username": u.username,
            "class_name": s.class_name,
            "grade": float(g.grade) if g.grade is not None else None,
            "graded_at": g.graded_at,
        }
        for g, s, u in rows
    ]
    return render_template(
        "professor/course_detail.html", course=ens, stats=stats, students=students
    )


# ─── GRADES ──────────────────────────────────────────────────────────────────

@professor_bp.route("/courses/<int:id>/grades")
@login_required
@professor_required
def course_grades(id: int):
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    rows = (
        db.session.query(Grade, Student, User)
        .join(Student, Grade.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(Grade.enseignement_id == ens.id)
        .order_by(User.username)
        .all()
    )
    students = [
        {
            "student_id": s.id,
            "student_number": s.student_number,
            "username": u.username,
            "class_name": s.class_name,
            "current_grade": float(g.grade) if g.grade is not None else None,
        }
        for g, s, u in rows
    ]
    graded_count = sum(1 for s in students if s["current_grade"] is not None)
    return render_template(
        "professor/course_grades.html",
        course=ens, students=students, graded_count=graded_count,
    )


@professor_bp.route("/courses/<int:id>/grades/save", methods=["POST"])
@login_required
@professor_required
def course_grades_save(id: int):
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    updated = 0
    for key, value in request.form.items():
        if not key.startswith("grade_"):
            continue
        try:
            student_id = int(key.split("_")[1])
            grade_value = float(value) if value.strip() else None
            if grade_value is not None and not (0 <= grade_value <= 20):
                continue
        except (ValueError, IndexError):
            continue

        grade_entry = Grade.query.filter_by(
            student_id=student_id, enseignement_id=ens.id
        ).first()
        if grade_entry:
            grade_entry.grade = grade_value
            grade_entry.graded_by = current_user.id
            grade_entry.graded_at = datetime.utcnow() if grade_value is not None else None
            updated += 1

    db.session.commit()
    log_audit("grades_save", resource_type="enseignement", resource_id=ens.id)
    flash(f"{updated} note(s) enregistrée(s).", "success")
    return redirect(url_for("professor.course_grades", id=ens.id))


# ─── ATTENDANCE (appel) ─────────────────────────────────────────────────────

@professor_bp.route("/attendance")
@login_required
@professor_required
def attendance_list():
    """Liste des enseignements du prof pour faire l'appel."""
    prof = current_user.professor_profile
    if not prof:
        return redirect(url_for("professor.dashboard"))

    course_list = []
    for e in prof.enseignements.join(Matiere).order_by(Matiere.name).all():
        sc = Grade.query.filter_by(enseignement_id=e.id).count()
        course_list.append({
            "id": e.id, "name": e.name, "code": e.code,
            "class_name": e.class_name, "student_count": sc,
        })
    return render_template("professor/attendance_list.html", courses=course_list)


@professor_bp.route("/attendance/<int:id>")
@login_required
@professor_required
def attendance_call(id: int):
    """Page d'appel pour un enseignement donné, à une date donnée."""
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    # Date : par défaut aujourd'hui, sinon paramètre GET
    date_str = request.args.get("date")
    if date_str:
        try:
            selected_date = date.fromisoformat(date_str)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # Récupérer les étudiants inscrits (via Grade)
    rows = (
        db.session.query(Student, User)
        .join(User, Student.user_id == User.id)
        .join(Grade, Grade.student_id == Student.id)
        .filter(Grade.enseignement_id == ens.id)
        .order_by(User.username)
        .all()
    )

    # Récupérer les présences déjà enregistrées pour cette date
    existing = {
        a.student_id: a.status
        for a in Attendance.query.filter_by(
            enseignement_id=ens.id, date=selected_date
        ).all()
    }

    students = []
    for s, u in rows:
        students.append({
            "student_id": s.id,
            "username": u.username,
            "student_number": s.student_number,
            "status": existing.get(s.id, "present"),
        })

    already_saved = len(existing) > 0

    return render_template(
        "professor/attendance_call.html",
        course=ens, students=students,
        selected_date=selected_date, already_saved=already_saved,
    )


@professor_bp.route("/attendance/<int:id>/save", methods=["POST"])
@login_required
@professor_required
def attendance_save(id: int):
    """Enregistre l'appel pour un enseignement à une date."""
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    date_str = request.form.get("date")
    try:
        selected_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        flash("Date invalide.", "danger")
        return redirect(url_for("professor.attendance_call", id=ens.id))

    # Récupérer les étudiants inscrits
    enrolled = (
        db.session.query(Student.id)
        .join(Grade, Grade.student_id == Student.id)
        .filter(Grade.enseignement_id == ens.id)
        .all()
    )
    enrolled_ids = {row[0] for row in enrolled}

    updated = 0
    for student_id in enrolled_ids:
        status = request.form.get(f"status_{student_id}", "present")
        if status not in ("present", "absent", "late"):
            status = "present"

        att = Attendance.query.filter_by(
            student_id=student_id, enseignement_id=ens.id, date=selected_date
        ).first()

        if att:
            att.status = status
            att.recorded_by = current_user.id
            att.recorded_at = datetime.utcnow()
        else:
            att = Attendance(
                student_id=student_id,
                enseignement_id=ens.id,
                date=selected_date,
                status=status,
                recorded_by=current_user.id,
            )
            db.session.add(att)
        updated += 1

    db.session.commit()
    log_audit("attendance_save", resource_type="enseignement", resource_id=ens.id)
    flash(f"Appel enregistré pour {updated} étudiant(s).", "success")
    return redirect(url_for("professor.attendance_call", id=ens.id, date=selected_date.isoformat()))


@professor_bp.route("/attendance/<int:id>/history")
@login_required
@professor_required
def attendance_history(id: int):
    """Historique des appels pour un enseignement."""
    ens = Enseignement.query.get_or_404(id)
    if ens.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    # Dates distinctes d'appels effectués
    dates = (
        db.session.query(Attendance.date)
        .filter_by(enseignement_id=ens.id)
        .distinct()
        .order_by(desc(Attendance.date))
        .all()
    )

    history = []
    for (d,) in dates:
        records = Attendance.query.filter_by(enseignement_id=ens.id, date=d).all()
        total = len(records)
        absents = sum(1 for r in records if r.status == "absent")
        lates = sum(1 for r in records if r.status == "late")
        presents = total - absents - lates
        history.append({
            "date": d,
            "total": total,
            "presents": presents,
            "absents": absents,
            "lates": lates,
        })

    return render_template(
        "professor/attendance_history.html",
        course=ens, history=history,
    )


# ─── PROFILE ─────────────────────────────────────────────────────────────────

@professor_bp.route("/profile")
@login_required
@professor_required
def profile():
    prof = current_user.professor_profile
    form = ProfileProfessorForm(obj=prof)
    return render_template("professor/profile.html", professor=prof, form=form)


@professor_bp.route("/profile/edit", methods=["POST"])
@login_required
@professor_required
def profile_edit():
    prof = current_user.professor_profile
    form = ProfileProfessorForm()
    if form.validate_on_submit():
        prof.department = form.department.data.strip() if form.department.data else None
        prof.specialization = form.specialization.data.strip() if form.specialization.data else None
        db.session.commit()
        log_audit("profile_edit")
        flash("Profil mis à jour.", "success")
    return redirect(url_for("professor.profile"))
