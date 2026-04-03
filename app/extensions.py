from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
bcrypt = Bcrypt()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
jwt = JWTManager()
cors = CORS(resources={r"/api/*": {"origins": "*"}})
