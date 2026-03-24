from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

socketio = SocketIO()
db = None  # Will be set in create_app (MessageDatabase instance)

sa = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
