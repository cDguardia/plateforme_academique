from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required

from app.extensions import limiter
from app.models import User
from app.rbac import admin_required, student_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@api_bp.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def api_login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Nom d'utilisateur et mot de passe requis"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Identifiants invalides"}), 401

    if user.is_locked:
        return jsonify({"error": "Compte verrouillé"}), 423

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role.value
        }
    }), 200


@api_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def api_refresh():
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    return jsonify({"access_token": access_token}), 200


# ─── COURSES ─────────────────────────────────────────────────────────────────

@api_bp.route("/courses", methods=["GET"])
@jwt_required()
def api_courses():
    from app.models import Course
    courses = Course.query.all()
    return jsonify([{
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "professor": c.professor.user.username if c.professor else None
    } for c in courses]), 200


@api_bp.route("/courses/<int:course_id>", methods=["GET"])
@jwt_required()
def api_course_detail(course_id):
    from app.models import Course
    course = Course.query.get_or_404(course_id)
    return jsonify({
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "professor": course.professor.user.username if course.professor else None
    }), 200


# ─── GRADES ──────────────────────────────────────────────────────────────────

@api_bp.route("/grades", methods=["GET"])
@jwt_required()
@student_required
def api_grades():
    from app.models import Grade
    current_user_id = get_jwt_identity()
    grades = Grade.query.filter_by(student_id=current_user_id).all()
    return jsonify([{
        "course": g.course.title,
        "grade": g.grade,
        "date": g.created_at.isoformat() if g.created_at else None
    } for g in grades]), 200


# ─── ADMIN ───────────────────────────────────────────────────────────────────

@api_bp.route("/admin/users", methods=["GET"])
@jwt_required()
@admin_required
def api_users():
    users = User.query.all()
    return jsonify([{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role.value,
        "is_locked": u.is_locked
    } for u in users]), 200
