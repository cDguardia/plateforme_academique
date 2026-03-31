import os
from flask import Flask, render_template

from app.config import DevelopmentConfig, ProductionConfig
from app.extention import db, login_manager, csrf, bcrypt

from app.auth import auth_bp
from app.routes_admin import admin_bp
from app.routes_professor import professor_bp
from app.routes_student import student_bp


def create_app(config_name=None):
    app = Flask(__name__, template_folder='templates')
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'DevelopmentConfig')
    config = DevelopmentConfig if config_name == 'DevelopmentConfig' else ProductionConfig
    app.config.from_object(config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(professor_bp, url_prefix='/professor')
    app.register_blueprint(student_bp, url_prefix='/student')

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template('500.html'), 500

    with app.app_context():
        from app import models  # register SQLAlchemy models
        db.create_all()

    return app
