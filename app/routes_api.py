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

    if not user.is_active:
        return jsonify({"error": "Compte désactivé"}), 423

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }
    }), 200


@api_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def api_refresh():
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    return jsonify({"access_token": access_token}), 200


# ─── COURSES (enseignements) ────────────────────────────────────────────────

@api_bp.route("/courses", methods=["GET"])
@jwt_required()
def api_courses():
    from app.models import Enseignement
    ens_list = Enseignement.query.all()
    return jsonify([{
        "id": e.id,
        "name": e.name,
        "code": e.code,
        "class_name": e.class_name,
        "credits": e.credits,
        "description": e.description,
        "professor": e.professor.user.username,
    } for e in ens_list]), 200


@api_bp.route("/courses/<int:id>", methods=["GET"])
@jwt_required()
def api_course_detail(id):
    from app.models import Enseignement
    ens = Enseignement.query.get_or_404(id)
    return jsonify({
        "id": ens.id,
        "name": ens.name,
        "code": ens.code,
        "class_name": ens.class_name,
        "credits": ens.credits,
        "description": ens.description,
        "professor": ens.professor.user.username,
    }), 200


# ─── GRADES ──────────────────────────────────────────────────────────────────

@api_bp.route("/grades", methods=["GET"])
@jwt_required()
def api_grades():
    from app.models import Grade, Student
    current_user_id = get_jwt_identity()
    # Récupérer le profil étudiant à partir du user_id (pas le même que student_id)
    student = Student.query.filter_by(user_id=current_user_id).first()
    if not student:
        return jsonify({"error": "Profil étudiant introuvable"}), 403
    grades = Grade.query.filter_by(student_id=student.id).all()
    return jsonify([{
        "course": g.enseignement.name,
        "grade": float(g.grade) if g.grade else None,
        "graded_at": g.graded_at.isoformat() if g.graded_at else None,
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
        "role": u.role,
        "is_active": u.is_active,
    } for u in users]), 200
