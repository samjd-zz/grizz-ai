from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from functools import wraps
from datetime import datetime
from logger import app_logger
from database import ComicDatabase

auth_bp = Blueprint('auth', __name__)

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app_logger.debug(f"Checking login requirement for {request.path}")
        if 'user' not in session:
            app_logger.debug("User not in session, redirecting to login")
            return redirect(url_for('auth.login', next=request.url))
        app_logger.debug(f"User {session['user']['username']} is logged in")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('routes.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    app_logger.debug(f"Login route accessed with method: {request.method}")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        app_logger.debug(f"Login attempt for username: {username}")
        db = get_db()
        user = db.get_user_by_username(username)
        app_logger.debug(f"User retrieved from database: {user}")
        if user:
            is_valid = db.check_password(username, password)
            app_logger.debug(f"Password check result: {is_valid}")
            if is_valid:
                app_logger.debug(f"Login successful for user: {user}")
                session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role']}
                app_logger.debug(f"Session after login: {session}")
                db.update_user_last_login(user['id'])
                from loyalty_module import award_weekly_login_points
                award_weekly_login_points(user['id'])
                flash('Logged in successfully.')
                return redirect(url_for('routes.index'))
            else:
                app_logger.warning(f"Invalid password for username: {username}")
                flash('Invalid username or password')
        else:
            app_logger.warning(f"User not found: {username}")
            flash('Invalid username or password')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully.')
    return redirect(url_for('routes.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        if db.get_user_by_username(username):
            flash('Username already exists')
        elif db.get_user_by_email(email):
            flash('Email already registered')
        else:
            db.add_user(username, email, password, 'user')
            flash('Registration successful. Please log in.')
            return redirect(url_for('auth.login'))
    return render_template('register.html')
