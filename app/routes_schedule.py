from __future__ import annotations

import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ScheduleForm
from app.models import Course, Grade, Professor, Schedule, Student, log_audit
from app.rbac import admin_required

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")


@schedule_bp.route("/")
@login_required
def view():
    """Vue calendrier par rôle."""
    if current_user.role == "admin":
        entries = Schedule.query.join(Course).order_by(Schedule.day_of_week, Schedule.start_time).all()

    elif current_user.role == "professor":
        prof = current_user.professor_profile
        if not prof:
            abort(403)
        entries = (
            Schedule.query
            .join(Course, Schedule.course_id == Course.id)
            .filter(Course.professor_id == prof.id)
            .order_by(Schedule.day_of_week, Schedule.start_time)
            .all()
        )

    else:  # student
        student = current_user.student_profile
        if not student:
            abort(403)
        # Cours de sa classe uniquement
        enrolled_course_ids = (
            db.session.query(Grade.course_id)
            .filter_by(student_id=student.id)
            .subquery()
        )
        entries = (
            Schedule.query
            .join(Course, Schedule.course_id == Course.id)
            .filter(Schedule.course_id.in_(enrolled_course_ids))
            .order_by(Schedule.day_of_week, Schedule.start_time)
            .all()
        )

    # Organiser par jour
    by_day: dict[int, list] = {i: [] for i in range(6)}
    for e in entries:
        by_day[e.day_of_week].append(e)

    day_names = Schedule.DAY_NAMES[:6]
    return render_template("schedule/view.html", by_day=by_day, day_names=day_names)


# ─── ADMIN CRUD ───────────────────────────────────────────────────────────────

@schedule_bp.route("/admin/create", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = ScheduleForm()
    form.course_id.choices = [
        (c.id, f"{c.code} — {c.name} ({c.class_name})")
        for c in Course.query.order_by(Course.name).all()
    ]
    if form.validate_on_submit():
        entry = Schedule(
            course_id=form.course_id.data,
            day_of_week=form.day_of_week.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            room=form.room.data.strip() if form.room.data else None,
        )
        db.session.add(entry)
        db.session.commit()
        log_audit("schedule_create", resource_type="schedule", resource_id=entry.id)
        flash("Créneau ajouté.", "success")
        return redirect(url_for("schedule.view"))
    return render_template("schedule/form.html", form=form, entry=None)


@schedule_bp.route("/admin/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit(id: int):
    entry = Schedule.query.get_or_404(id)
    form = ScheduleForm(obj=entry)
    form.course_id.choices = [
        (c.id, f"{c.code} — {c.name} ({c.class_name})")
        for c in Course.query.order_by(Course.name).all()
    ]
    if form.validate_on_submit():
        entry.course_id = form.course_id.data
        entry.day_of_week = form.day_of_week.data
        entry.start_time = form.start_time.data
        entry.end_time = form.end_time.data
        entry.room = form.room.data.strip() if form.room.data else None
        db.session.commit()
        log_audit("schedule_edit", resource_type="schedule", resource_id=entry.id)
        flash("Créneau modifié.", "success")
        return redirect(url_for("schedule.view"))
    return render_template("schedule/form.html", form=form, entry=entry)


@schedule_bp.route("/admin/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete(id: int):
    entry = Schedule.query.get_or_404(id)
    db.session.delete(entry)
    db.session.commit()
    log_audit("schedule_delete", resource_type="schedule", resource_id=id)
    flash("Créneau supprimé.", "info")
    return redirect(url_for("schedule.view"))
