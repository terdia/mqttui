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


class TopicFavorite(sa.Model):
    __tablename__ = 'topic_favorites'

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'), nullable=False)
    topic = sa.Column(sa.String(500), nullable=False)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())

    __table_args__ = (sa.UniqueConstraint('user_id', 'topic', name='uq_user_topic'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'topic': self.topic,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Broker(sa.Model):
    __tablename__ = 'brokers'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(200), nullable=False)
    host = sa.Column(sa.String(500), nullable=False)
    port = sa.Column(sa.Integer, default=1883)
    username = sa.Column(sa.String(200), nullable=True)
    password = sa.Column(sa.String(200), nullable=True)
    mqtt_version = sa.Column(sa.String(10), default='3.1.1')
    topics = sa.Column(sa.String(1000), default='#')
    tls_enabled = sa.Column(sa.Boolean, default=False)
    tls_ca_certs = sa.Column(sa.String(500), nullable=True)
    tls_insecure = sa.Column(sa.Boolean, default=False)
    is_active = sa.Column(sa.Boolean, default=True)
    is_default = sa.Column(sa.Boolean, default=False)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'has_password': bool(self.password),
            'mqtt_version': self.mqtt_version,
            'topics': self.topics,
            'tls_enabled': self.tls_enabled,
            'tls_insecure': self.tls_insecure,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
