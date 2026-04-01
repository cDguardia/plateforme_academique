from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import CourseForm, ProfileProfessorForm
from app.models import Course, Grade, Professor, Student, User, log_audit
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

    my_courses = prof.courses.all()

    # Stats
    total_students = sum(
        Grade.query.filter_by(course_id=c.id).count() for c in my_courses
    )
    grades_given = sum(
        Grade.query.filter_by(course_id=c.id).filter(Grade.grade.isnot(None)).count()
        for c in my_courses
    )
    pending = total_students - grades_given
    stats = {
        "my_courses": len(my_courses),
        "total_students": total_students,
        "grades_given": grades_given,
        "pending_grades": pending,
    }

    # Aperçu des cours avec stats légères
    courses_preview = []
    for c in my_courses[:5]:
        sc = Grade.query.filter_by(course_id=c.id).count()
        courses_preview.append({
            "id": c.id, "name": c.name, "code": c.code,
            "class_name": c.class_name, "student_count": sc,
        })

    # Dernières notes
    from sqlalchemy import desc
    recent = (
        db.session.query(Grade, Student, User, Course)
        .join(Student, Grade.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(Course, Grade.course_id == Course.id)
        .filter(Course.professor_id == prof.id)
        .filter(Grade.grade.isnot(None))
        .order_by(desc(Grade.graded_at))
        .limit(8)
        .all()
    )
    recent_grades = [
        {
            "student_name": u.username,
            "course_name": c.name,
            "value": float(g.grade),
            "graded_at": g.graded_at,
        }
        for g, s, u, c in recent
    ]

    return render_template(
        "dashboard_professor.html",
        stats=stats,
        my_courses=courses_preview,
        recent_grades=recent_grades,
    )


# ─── COURSES ─────────────────────────────────────────────────────────────────

@professor_bp.route("/courses")
@login_required
@professor_required
def courses():
    prof = current_user.professor_profile
    if not prof:
        return redirect(url_for("professor.dashboard"))

    from sqlalchemy import func
    course_list = []
    for c in prof.courses.order_by(Course.name).all():
        sc = Grade.query.filter_by(course_id=c.id).count()
        avg = db.session.query(func.avg(Grade.grade)).filter_by(course_id=c.id).filter(Grade.grade.isnot(None)).scalar()
        course_list.append({
            "id": c.id, "name": c.name, "code": c.code,
            "class_name": c.class_name, "credits": c.credits,
            "student_count": sc,
            "average": float(avg) if avg else None,
        })
    return render_template("professor/courses.html", courses=course_list)


@professor_bp.route("/courses/create", methods=["GET", "POST"])
@login_required
@professor_required
def course_create():
    form = CourseForm()
    if form.validate_on_submit():
        prof = current_user.professor_profile
        # Vérifier unicité du code
        if Course.query.filter_by(code=form.code.data.upper().strip()).first():
            flash("Ce code de cours existe déjà.", "danger")
            return render_template("professor/course_form.html", form=form, course=None)
        course = Course(
            professor_id=prof.id,
            name=form.name.data.strip(),
            code=form.code.data.upper().strip(),
            class_name=form.class_name.data.strip().upper(),
            credits=form.credits.data,
            description=form.description.data.strip() if form.description.data else None,
        )
        db.session.add(course)
        db.session.commit()
        log_audit("course_create", resource_type="course", resource_id=course.id)
        flash(f"Cours « {course.name} » créé.", "success")
        return redirect(url_for("professor.courses"))
    return render_template("professor/course_form.html", form=form, course=None)


@professor_bp.route("/courses/<int:id>/edit", methods=["GET", "POST"])
@login_required
@professor_required
def course_edit(id: int):
    course = Course.query.get_or_404(id)
    # Vérifier propriété
    if course.professor.user_id != current_user.id:
        from flask import abort
        abort(403)
    form = CourseForm(obj=course)
    if form.validate_on_submit():
        course.name = form.name.data.strip()
        course.class_name = form.class_name.data.strip().upper()
        course.credits = form.credits.data
        course.description = form.description.data.strip() if form.description.data else None
        db.session.commit()
        log_audit("course_edit", resource_type="course", resource_id=course.id)
        flash("Cours mis à jour.", "success")
        return redirect(url_for("professor.courses"))
    return render_template("professor/course_form.html", form=form, course=course)


@professor_bp.route("/courses/<int:id>")
@login_required
@professor_required
def course_detail(id: int):
    course = Course.query.get_or_404(id)
    if course.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    from sqlalchemy import func
    sc = Grade.query.filter_by(course_id=course.id).count()
    avg = db.session.query(func.avg(Grade.grade)).filter_by(course_id=course.id).filter(Grade.grade.isnot(None)).scalar()
    given = Grade.query.filter_by(course_id=course.id).filter(Grade.grade.isnot(None)).count()
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
        .filter(Grade.course_id == course.id)
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
        "professor/course_detail.html", course=course, stats=stats, students=students
    )


# ─── GRADES ──────────────────────────────────────────────────────────────────

@professor_bp.route("/courses/<int:id>/grades")
@login_required
@professor_required
def course_grades(id: int):
    course = Course.query.get_or_404(id)
    if course.professor.user_id != current_user.id:
        from flask import abort
        abort(403)

    rows = (
        db.session.query(Grade, Student, User)
        .join(Student, Grade.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(Grade.course_id == course.id)
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
        course=course, students=students, graded_count=graded_count,
    )


@professor_bp.route("/courses/<int:id>/grades/save", methods=["POST"])
@login_required
@professor_required
def course_grades_save(id: int):
    course = Course.query.get_or_404(id)
    if course.professor.user_id != current_user.id:
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
                continue  # Ignorer valeurs hors plage
        except (ValueError, IndexError):
            continue

        grade_entry = Grade.query.filter_by(
            student_id=student_id, course_id=course.id
        ).first()
        if grade_entry:
            grade_entry.grade = grade_value
            grade_entry.graded_by = current_user.id
            grade_entry.graded_at = datetime.utcnow() if grade_value is not None else None
            updated += 1

    db.session.commit()
    log_audit("grades_save", resource_type="course", resource_id=course.id)
    flash(f"{updated} note(s) enregistrée(s).", "success")
    return redirect(url_for("professor.course_grades", id=course.id))


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
