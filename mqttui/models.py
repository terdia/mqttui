from mqttui.extensions import sa
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


class User(UserMixin, sa.Model):
    __tablename__ = 'users'

    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String(80), unique=True, nullable=False)
    password_hash = sa.Column(sa.String(256), nullable=False)
    api_token = sa.Column(sa.String(64), unique=True, nullable=True)
    is_active_user = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_api_token(self):
        self.api_token = secrets.token_hex(32)
        return self.api_token

    @property
    def is_active(self):
        return self.is_active_user
