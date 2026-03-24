"""SQLAlchemy model for plugin configuration persistence."""
from mqttui.extensions import sa


class PluginConfig(sa.Model):
    __tablename__ = 'plugin_configs'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(200), unique=True, nullable=False)
    entry_point = sa.Column(sa.String(500), nullable=False)
    enabled = sa.Column(sa.Boolean, default=False)
    config_json = sa.Column(sa.Text, default='{}')
    version = sa.Column(sa.String(50), nullable=True)
    description = sa.Column(sa.Text, nullable=True)
    installed_at = sa.Column(sa.DateTime, server_default=sa.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'entry_point': self.entry_point,
            'enabled': self.enabled,
            'config_json': self.config_json,
            'version': self.version,
            'description': self.description,
            'installed_at': self.installed_at.isoformat() if self.installed_at else None,
        }
