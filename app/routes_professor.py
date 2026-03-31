from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.rbac import role_required


professor_bp = Blueprint('professor', __name__, template_folder='templates')


@professor_bp.route('/')
@login_required
@role_required('professor')
def dashboard():
    profile = current_user.professor_profile
    courses = profile.courses if profile is not None else []
    return render_template('dashboard_professor.html', courses=courses, profile=profile)
