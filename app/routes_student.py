from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.rbac import role_required


student_bp = Blueprint('student', __name__, template_folder='templates')


@student_bp.route('/')
@login_required
@role_required('student')
def dashboard():
    profile = current_user.student_profile
    grades = profile.grades if profile is not None else []
    return render_template('dashboard_student.html', grades=grades, profile=profile)
