import os
import logging

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from mqttui.models import User
from mqttui.extensions import sa, login_manager

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.before_app_request
def load_user_from_api_key():
    """Check X-API-Key header before session auth."""
    api_key = request.headers.get('X-API-Key')
    if api_key:
        user = User.query.filter_by(api_token=api_key).first()
        if user and user.is_active:
            login_user(user)


@login_manager.user_loader
def load_user(user_id):
    return sa.session.get(User, int(user_id))


def seed_admin_user(app):
    """Create default admin user from environment variables if not exists."""
    admin_username = os.environ.get('MQTTUI_ADMIN_USER', app.config.get('MQTTUI_ADMIN_USER', 'admin'))
    admin_password = os.environ.get('MQTTUI_ADMIN_PASSWORD', app.config.get('MQTTUI_ADMIN_PASSWORD', 'admin'))

    with app.app_context():
        existing = User.query.filter_by(username=admin_username).first()
        if existing:
            logger.info("Admin user already exists")
            return

        user = User(username=admin_username)
        user.set_password(admin_password)
        user.generate_api_token()
        sa.session.add(user)
        sa.session.commit()
        logger.info("Admin user seeded")


@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '')
    password = request.form.get('password', '')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or '/')

    flash('Invalid username or password', 'error')
    return render_template('login.html'), 200


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
