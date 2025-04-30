from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
from datetime import datetime
from logger import app_logger
from database import ComicDatabase
from .auth_module import admin_required, login_required

loyalty_bp = Blueprint('loyalty', __name__)

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

def check_and_deduct_points(user_id, action):
    db = get_db()
    user = db.get_user_by_id(user_id)
    
    # Admins don't need to spend points
    if user['role'] == 'admin':
        app_logger.debug(f"Admin user {user_id} bypassing loyalty point check")
        return True
        
    point_cost = db.get_loyalty_point_cost(action)
    
    if user['loyalty_points'] >= point_cost:
        db.update_user_loyalty_points(user_id, -point_cost)
        return True
    return False

def award_weekly_login_points(user_id):
    db = get_db()
    user = db.get_user_by_id(user_id)
    if user and user['role'] != 'admin':  # Don't award points to admins
        last_login = user.get('last_login')
        today = datetime.now().date()
        
        if last_login is None or (isinstance(last_login, str) and datetime.strptime(last_login, "%Y-%m-%d %H:%M:%S").date() <= today - timedelta(days=7)):
            db.update_user_loyalty_points(user_id, 1)
            app_logger.info(f"Awarded 1 loyalty point to user {user_id} for weekly login")

def award_daily_purchase_points(user_id):
    db = get_db()
    user = db.get_user_by_id(user_id)
    if not user or user['role'] == 'admin':  # Don't award points to admins
        return
        
    last_purchase = user['last_purchase_date']
    today = datetime.now().date()
    
    if last_purchase is None or last_purchase < today:
        db.update_user_loyalty_points(user_id, 1)
        db.update_user_last_purchase(user_id)
        app_logger.info(f"Awarded 1 loyalty point to user {user_id} for daily purchase")

@loyalty_bp.route('/loyalty_points')
@login_required
def loyalty_points():
    db = get_db()
    user_id = session['user']['id']
    user = db.get_user_by_id(user_id)
    return render_template('loyalty_points.html', loyalty_points=user['loyalty_points'])

@loyalty_bp.route('/admin/loyalty_config', methods=['GET', 'POST'])
@admin_required
def admin_loyalty_config():
    db = get_db()
    if request.method == 'POST':
        for action, cost in request.form.items():
            if action.startswith('cost_'):
                action_name = action[5:]
                try:
                    cost = int(cost)
                    db.update_loyalty_point_cost(action_name, cost)
                except ValueError:
                    flash(f'Invalid cost value for {action_name}', 'error')
        flash('Loyalty point costs updated successfully', 'success')
        return redirect(url_for('loyalty.admin_loyalty_config'))
    
    point_costs = {
        'daily_news_comic': db.get_loyalty_point_cost('daily_news_comic'),
        'custom_comic': db.get_loyalty_point_cost('custom_comic'),
        'media_comic': db.get_loyalty_point_cost('media_comic'),
        'voice_narration': db.get_loyalty_point_cost('voice_narration'),
        'custom_voice_narration': db.get_loyalty_point_cost('custom_voice_narration'),
        'extra_comic_story': db.get_loyalty_point_cost('extra_comic_story'),
        'extra_image': db.get_loyalty_point_cost('extra_image'),
        'theme_song': db.get_loyalty_point_cost('theme_song'),
        'custom_song': db.get_loyalty_point_cost('custom_song'),
        'boost_lyrics': db.get_loyalty_point_cost('boost_lyrics')
    }
    return render_template('admin_loyalty_config.html', point_costs=point_costs)

@loyalty_bp.route('/ai_services_pricing')
def ai_services_pricing():
    db = get_db()
    prices = {
        'Daily News Comic': db.get_loyalty_point_cost('daily_news_comic'),
        'Custom Comic': db.get_loyalty_point_cost('custom_comic'),
        'Media Comic': db.get_loyalty_point_cost('media_comic'),
        'Voice Narration': db.get_loyalty_point_cost('voice_narration'),
        'Custom Voice Narration': db.get_loyalty_point_cost('custom_voice_narration'),
        'Extra Comic Story': db.get_loyalty_point_cost('extra_comic_story'),
        'Extra Image': db.get_loyalty_point_cost('extra_image'),
        'Theme Song': db.get_loyalty_point_cost('theme_song'),
        'Custom Song': db.get_loyalty_point_cost('custom_song'),
        'Boost Lyrics': db.get_loyalty_point_cost('boost_lyrics')
    }
    return render_template('ai_services_pricing.html', prices=prices)
