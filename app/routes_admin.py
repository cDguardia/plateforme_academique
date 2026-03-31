from flask import Blueprint, render_template
from flask_login import login_required

from app.models import User
from app.rbac import role_required


admin_bp = Blueprint('admin', __name__, template_folder='templates')


@admin_bp.route('/')
@login_required
@role_required('admin')
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('dashboard_admin.html', users=users)
