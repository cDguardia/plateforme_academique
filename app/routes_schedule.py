from __future__ import annotations

import re

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ScheduleForm
from app.models import Enseignement, Grade, Matiere, Schedule, log_audit
from app.rbac import admin_required

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")


@schedule_bp.route("/")
@login_required
def view():
    if current_user.role == "admin":
        entries = Schedule.query.join(Enseignement).order_by(Schedule.day_of_week, Schedule.start_time).all()

    elif current_user.role == "professor":
        prof = current_user.professor_profile
        if not prof:
            abort(403)
        entries = (
            Schedule.query
            .join(Enseignement, Schedule.enseignement_id == Enseignement.id)
            .filter(Enseignement.professor_id == prof.id)
            .order_by(Schedule.day_of_week, Schedule.start_time)
            .all()
        )

    else:  # student
        student = current_user.student_profile
        if not student:
            abort(403)
        enrolled_ens_ids = (
            db.session.query(Grade.enseignement_id)
            .filter_by(student_id=student.id)
            .scalar_subquery()
        )
        entries = (
            Schedule.query
            .join(Enseignement, Schedule.enseignement_id == Enseignement.id)
            .filter(Schedule.enseignement_id.in_(enrolled_ens_ids))
            .order_by(Schedule.day_of_week, Schedule.start_time)
            .all()
        )

    by_day: dict[int, list] = {i: [] for i in range(6)}
    for e in entries:
        by_day[e.day_of_week].append(e)

    day_names = Schedule.DAY_NAMES[:6]
    return render_template("schedule/view.html", by_day=by_day, day_names=day_names)


@schedule_bp.route("/api")
@login_required
def api():
    week = request.args.get("week", "").strip()
    if not WEEK_RE.match(week):
        return jsonify({"error": "Format semaine invalide (YYYY-WNN)"}), 400

    from datetime import datetime, timedelta
    year, wnum = map(int, week.split("-W"))
    jan1 = datetime(year, 1, 1)
    monday = jan1 + timedelta(days=(wnum-1)*7 - jan1.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    if current_user.role == "admin":
        schedules = Schedule.query.join(Enseignement).all()

    elif current_user.role == "professor":
        prof = current_user.professor_profile
        if not prof:
            abort(403)
        schedules = (
            Schedule.query
            .join(Enseignement, Schedule.enseignement_id == Enseignement.id)
            .filter(Enseignement.professor_id == prof.id)
            .all()
        )

    else:
        student = current_user.student_profile
        if not student:
            abort(403)
        enrolled_ens_ids = (
            db.session.query(Grade.enseignement_id)
            .filter_by(student_id=student.id)
            .scalar_subquery()
        )
        schedules = (
            Schedule.query
            .join(Enseignement, Schedule.enseignement_id == Enseignement.id)
            .filter(Schedule.enseignement_id.in_(enrolled_ens_ids))
            .all()
        )

    events = []
    for s in schedules:
        ens = s.enseignement
        day_date = week_dates[s.day_of_week]
        start_dt = datetime.combine(day_date, datetime.strptime(s.start_time, "%H:%M").time())
        end_dt = datetime.combine(day_date, datetime.strptime(s.end_time, "%H:%M").time())

        events.append({
            "id": s.id,
            "title": f"{ens.code} - {ens.name}",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "extendedProps": {
                "room": s.room,
                "professor": ens.professor.user.username,
                "class_name": ens.class_name,
            }
        })

    response = jsonify(events)
    response.headers["Cache-Control"] = "private, max-age=300"
    return response


# ─── ADMIN CRUD ──────────────────────────────────────────────────────────────

@schedule_bp.route("/admin/create", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = ScheduleForm()
    form.enseignement_id.choices = [
        (e.id, f"{e.code} — {e.name} ({e.class_name})")
        for e in Enseignement.query.join(Matiere).order_by(Matiere.name).all()
    ]
    if form.validate_on_submit():
        entry = Schedule(
            enseignement_id=form.enseignement_id.data,
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
    form.enseignement_id.choices = [
        (e.id, f"{e.code} — {e.name} ({e.class_name})")
        for e in Enseignement.query.join(Matiere).order_by(Matiere.name).all()
    ]
    if form.validate_on_submit():
        entry.enseignement_id = form.enseignement_id.data
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
