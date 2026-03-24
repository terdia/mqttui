from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

socketio = SocketIO()
db = None  # Will be set in create_app (MessageDatabase instance)

sa = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
