from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import os
from logger import app_logger
from .auth_module import login_required
from .loyalty_module import award_daily_purchase_points

routes_bp = Blueprint('routes', __name__)

def get_config():
    return current_app.config['APP_CONFIG']

@routes_bp.route('/')
@login_required
def index():
    return render_template('index.html')

@routes_bp.route('/food_menu')
def food_menu():
    menu_images_dir = os.path.join(current_app.static_folder, 'images', 'ggs-food-menu')
    menu_images = [f for f in os.listdir(menu_images_dir) if f.endswith('.png') or f.endswith('.jpg')]
    menu_items = [{'name': ' '.join(img.split('_')[:-1]).title(), 'image': f'images/ggs-food-menu/{img}'} for img in menu_images]
    return render_template('food_menu.html', menu_items=menu_items)

@routes_bp.route('/purchase', methods=['POST'])
@login_required
def purchase():
    user_id = session['user']['id']
    # Implement your purchase logic here
    # ...
    
    # After successful purchase, award loyalty points
    award_daily_purchase_points(user_id)
    flash('Purchase successful! You\'ve earned a loyalty point for today\'s purchase.', 'success')
    return redirect(url_for('routes.food_menu'))
