import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, url_for, send_from_directory, g, jsonify, Response, stream_with_context, redirect, session, flash
from functools import wraps
from main import generate_daily_comic, generate_custom_comic, generate_media_comic, capture_live_video
from config import load_config
from database import ComicDatabase
from logger import app_logger
from event_fetcher import get_local_events
from text_analysis import create_yogi_bear_voice
from geopy.geocoders import Nominatim
import json
import time
import uuid

app = Flask(__name__, static_folder='static')
config = load_config()

# Set the secret key for Flask sessions
app.config['SECRET_KEY'] = config.SECRET_KEY
app_logger.debug(f"Secret key set: {config.SECRET_KEY[:5]}...")  # Log first 5 characters of secret key

# Configure image serving for generated images
app.config['GENERATED_IMAGES_FOLDER'] = config.OUTPUT_DIR
os.makedirs(app.config['GENERATED_IMAGES_FOLDER'], exist_ok=True)

# Configure audio serving for albums (using relative path)
app.config['ALBUMS_FOLDER'] = 'audio/albums'

geolocator = Nominatim(user_agent="grizz-ai")

# Store ongoing comic generation tasks
comic_tasks = {}

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app_logger.debug(f"Checking login requirement for {request.path}")
        if 'user' not in session:
            app_logger.debug("User not in session, redirecting to login")
            return redirect(url_for('login', next=request.url))
        app_logger.debug(f"User {session['user']['username']} is logged in")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
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
                award_weekly_login_points(user['id'])
                flash('Logged in successfully.')
                return redirect(url_for('index'))
            else:
                app_logger.warning(f"Invalid password for username: {username}")
                flash('Invalid username or password')
        else:
            app_logger.warning(f"User not found: {username}")
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/ai_services_pricing')
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

def award_daily_purchase_points(user_id):
    db = get_db()
    user = db.get_user_by_id(user_id)
    last_purchase = user['last_purchase_date']
    today = datetime.now().date()
    
    if last_purchase is None or last_purchase < today:
        db.update_user_loyalty_points(user_id, 1)
        db.update_user_last_purchase(user_id)
        app_logger.info(f"Awarded 1 loyalty point to user {user_id} for daily purchase")

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully.')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
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
            return redirect(url_for('login'))
    return render_template('register.html')

def check_and_deduct_points(user_id, action):
    db = get_db()
    user = db.get_user_by_id(user_id)
    point_cost = db.get_loyalty_point_cost(action)
    
    if user['loyalty_points'] >= point_cost:
        db.update_user_loyalty_points(user_id, -point_cost)
        return True
    return False

@app.route('/loyalty_points')
@login_required
def loyalty_points():
    db = get_db()
    user_id = session['user']['id']
    user = db.get_user_by_id(user_id)
    return render_template('loyalty_points.html', loyalty_points=user['loyalty_points'])

def award_weekly_login_points(user_id):
    db = get_db()
    user = db.get_user_by_id(user_id)
    if user:
        last_login = user.get('last_login_date')
        today = datetime.now().date()
        
        if last_login is None or (isinstance(last_login, datetime) and (today - last_login.date()).days >= 7):
            db.update_user_loyalty_points(user_id, 1)
            app_logger.info(f"Awarded 1 loyalty point to user {user_id} for weekly login")

def award_daily_purchase_points(user_id):
    db = get_db()
    user = db.get_user_by_id(user_id)
    last_purchase = user['last_purchase_date']
    today = datetime.now().date()
    
    if last_purchase is None or last_purchase < today:
        db.update_user_loyalty_points(user_id, 1)
        db.update_user_last_purchase(user_id)
        app_logger.info(f"Awarded 1 loyalty point to user {user_id} for daily purchase")

@app.before_first_request
def before_first_request():
    # Create Yogi Bear voice when the application starts
    if config.GENERATE_AUDIO:
        create_yogi_bear_voice()

@app.after_request
def add_csp_header(response):
    csp = ("default-src 'self'; "
           "script-src 'self' 'unsafe-inline' https://code.jquery.com https://unpkg.com https://stackpath.bootstrapcdn.com https://cdn.jsdelivr.net; "
           "style-src 'self' 'unsafe-inline' https://unpkg.com https://stackpath.bootstrapcdn.com; "
           "img-src 'self' https://*.tile.openstreetmap.org https://unpkg.com data:; "
           "font-src 'self' https://stackpath.bootstrapcdn.com; "
           "connect-src 'self' https://nominatim.openstreetmap.org;")
    response.headers['Content-Security-Policy'] = csp
    return response

def get_album_info():
    albums_dir = os.path.join(app.root_path, '..', app.config['ALBUMS_FOLDER'])
    app_logger.debug(f"Albums directory: {albums_dir}")
    music = {}
    for genre in os.listdir(albums_dir):
        genre_path = os.path.join(albums_dir, genre)
        app_logger.debug(f"Checking genre: {genre}, path: {genre_path}")
        if os.path.isdir(genre_path):
            normalized_genre = genre.lower()
            if normalized_genre == 'raggae':
                normalized_genre = 'reggae'
            music[normalized_genre] = []
            for album in os.listdir(genre_path):
                if album.endswith('.mp4'):
                    album_info = {
                        'title': ' '.join(album.split('.')[0].split('_')).title(),
                        'filename': album,
                        'url': url_for('serve_audio', filename=f'{genre}/{album}')
                    }
                    music[normalized_genre].append(album_info)
                    app_logger.debug(f"Added album for {normalized_genre}: {album_info}")
    app_logger.debug(f"Final music data: {music}")
    return music

@app.route('/music')
def music():
    music_data = get_album_info()
    app_logger.info(f"Music data for template: {music_data}")
    app_logger.debug(f"Genres found: {list(music_data.keys())}")
    for genre, albums in music_data.items():
        app_logger.debug(f"Genre: {genre}, Number of albums: {len(albums)}")
    return render_template('music.html', music=music_data)

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def format_comic_script(script):
    # Remove extra characters like '+' and '**'
    script = re.sub(r'[+*]', '', script)
    # Split the script into lines
    lines = script.split('\n')
    # Remove empty lines and strip whitespace
    lines = [line.strip() for line in lines if line.strip()]
    # Join the lines back together
    return '\n'.join(lines)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['GENERATED_IMAGES_FOLDER'], filename)

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(os.path.join(app.root_path, '..', app.config['ALBUMS_FOLDER']), filename)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/food_menu')
def food_menu():
    menu_images_dir = os.path.join(app.static_folder, 'images', 'ggs-food-menu')
    menu_images = [f for f in os.listdir(menu_images_dir) if f.endswith('.png') or f.endswith('.jpg')]
    menu_items = [{'name': ' '.join(img.split('_')[:-1]).title(), 'image': f'images/ggs-food-menu/{img}'} for img in menu_images]
    return render_template('food_menu.html', menu_items=menu_items)

@app.route('/purchase', methods=['POST'])
@login_required
def purchase():
    user_id = session['user']['id']
    # Implement your purchase logic here
    # ...
    
    # After successful purchase, award loyalty points
    award_daily_purchase_points(user_id)
    flash('Purchase successful! You\'ve earned a loyalty point for today\'s purchase.', 'success')
    return redirect(url_for('food_menu'))

@app.route('/daily_comic', methods=['GET', 'POST'])
@login_required
def daily_comic():
    app_logger.debug("Accessing daily_comic route")
    if request.method == 'POST':
        location = request.form['location']
        comic_artist_style = request.form.get('comic_artist_style', '')
        user_id = session['user']['id']
        
        if not check_and_deduct_points(user_id, 'daily_news_comic'):
            flash('Insufficient loyalty points to generate a daily comic.', 'error')
            return redirect(url_for('daily_comic'))
        
        task_id = str(uuid.uuid4())
        comic_tasks[task_id] = {
            'status': 'started',
            'location': location,
            'comic_artist_style': comic_artist_style,
            'user_id': user_id
        }
        return jsonify({'task_id': task_id})
    app_logger.debug("Rendering daily_comic template")
    return render_template('daily_comic.html', config=config)

@app.route('/daily_comic_progress')
@login_required
def daily_comic_progress():
    task_id = request.args.get('task_id')
    app_logger.debug(f"Daily comic progress requested for task_id: {task_id}")
    if task_id not in comic_tasks:
        app_logger.error(f"Invalid task ID: {task_id}")
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        task = comic_tasks[task_id]
        location = task['location']
        comic_artist_style = task.get('comic_artist_style', '')
        user_id = task['user_id']

        app_logger.debug(f"Starting daily comic generation for location: {location}, style: {comic_artist_style}")

        yield "data: " + json.dumps({"progress": 5, "message": "Initializing daily comic generation...", "stage": "Preparation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 10, "message": "Checking for local events...", "stage": "Event Fetching"}) + "\n\n"
        time.sleep(1)
        
        app_logger.debug(f"Checking for local events in: {location}")
        local_events = get_local_events(location)
        app_logger.debug(f"Local events found: {local_events}")
        if not local_events or (len(local_events) == 1 and local_events[0]['title'] == "No Current News Events Reported"):
            app_logger.info(f"No events found for {location}")
            yield "data: " + json.dumps({"progress": 100, "message": "No events found for today. Please try again later.", "stage": "Completed"}) + "\n\n"
            return

        yield "data: " + json.dumps({"progress": 20, "message": "Local events found. Analyzing...", "stage": "Event Analysis"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 30, "message": "Generating comic ideas...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)
        
        yield "data: " + json.dumps({"progress": 40, "message": "Creating comic script...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 50, "message": "Generating daily comic...", "stage": "Comic Generation"}) + "\n\n"
        time.sleep(1)
        
        app_logger.debug(f"Generating daily comic for location: {location}, style: {comic_artist_style}")
        generated_comics = generate_daily_comic(location, user_id, comic_artist_style)
        
        if generated_comics:
            app_logger.debug(f"Generated comics: {generated_comics}")
            total_events = len(generated_comics)
            for event_index, event in enumerate(generated_comics):
                yield "data: " + json.dumps({"progress": 50 + (event_index * 40 // total_events), "message": f"Generating event {event_index + 1} of {total_events}...", "stage": "Comic Generation"}) + "\n\n"
                time.sleep(1)

                if isinstance(event, dict):
                    image_paths = event.get('image_paths', [])
                    app_logger.debug(f"Image paths for event {event_index + 1}: {image_paths}")
                    if image_paths:
                        for panel_index, path in enumerate(image_paths):
                            yield "data: " + json.dumps({"progress": 50 + (event_index * 40 // total_events) + (panel_index * 10 // len(image_paths)), "message": f"Generating panel {panel_index + 1} for event {event_index + 1}...", "stage": "Image Generation"}) + "\n\n"
                            time.sleep(0.5)

                        event['image_paths'] = [url_for('serve_image', filename=os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']), _external=True) for path in image_paths]
                        app_logger.debug(f"Updated image paths for event {event_index + 1}: {event['image_paths']}")
                    else:
                        app_logger.warning(f"No image paths found for event {event_index + 1}")
                        event['image_paths'] = []

                    # Ensure all necessary keys are present in the event dictionary
                    event['created_at'] = event.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    event['comic_script'] = event.get('comic_script', "No comic script available")
                    event['story'] = event.get('story', '').replace('-', '').strip()
                    event['comic_script'] = format_comic_script(event.get('comic_script', ''))
                    event['story_source'] = event.get('story_source', "Source not available")
                    event['panel_summaries'] = event.get('panel_summaries', ["Panel summary not available"] * 3)
                else:
                    app_logger.error(f"Unexpected event format for event {event_index + 1}")
                    continue

            app_logger.debug(f"Final generated comics: {generated_comics}")
            rendered_html = render_template('daily_comic_result.html', events=generated_comics, location=location)
            app_logger.debug(f"Rendered HTML: {rendered_html[:500]}...")  # Log first 500 characters of rendered HTML
            yield "data: " + json.dumps({"success": True, "html": rendered_html}) + "\n\n"
        else:
            app_logger.error("Failed to generate daily comics")
            yield "data: " + json.dumps({"success": False, "message": 'Failed to generate daily comics. Please try again.'}) + "\n\n"

        del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/custom_comic', methods=['GET', 'POST'])
@login_required
def custom_comic():
    if request.method == 'POST':
        title = request.form['title']
        story = request.form['story']
        location = request.form['location']
        comic_artist_style = request.form.get('comic_artist_style', '')
        user_id = session['user']['id']
        
        if not check_and_deduct_points(user_id, 'custom_comic'):
            flash('Insufficient loyalty points to generate a custom comic.', 'error')
            return redirect(url_for('custom_comic'))
        
        task_id = str(uuid.uuid4())
        comic_tasks[task_id] = {
            'status': 'started',
            'title': title,
            'story': story,
            'location': location,
            'comic_artist_style': comic_artist_style,
            'user_id': user_id
        }
        return jsonify({'task_id': task_id})
    return render_template('custom_comic.html')

@app.route('/custom_comic_progress')
@login_required
def custom_comic_progress():
    task_id = request.args.get('task_id')
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        task = comic_tasks[task_id]
        title = task['title']
        story = task['story']
        location = task['location']
        comic_artist_style = task.get('comic_artist_style', '')  # Make it optional
        user_id = task['user_id']

        yield "data: " + json.dumps({"progress": 5, "message": "Initializing custom comic generation...", "stage": "Preparation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 10, "message": "Checking for existing comics...", "stage": "Database Check"}) + "\n\n"
        time.sleep(1)
        
        db = get_db()
        existing_comic = db.get_comic_by_title_or_story(title, story)
        if existing_comic:
            app_logger.info(f"Comic already exists for title: {title} or story: {story}")
            yield "data: " + json.dumps({"success": False, "message": 'A comic with this title or story already exists.'}) + "\n\n"
            return

        yield "data: " + json.dumps({"progress": 20, "message": "Analyzing story...", "stage": "Text Analysis"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 30, "message": "Generating comic ideas...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 40, "message": "Creating comic script...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 50, "message": "Generating custom comic...", "stage": "Comic Generation"}) + "\n\n"
        time.sleep(1)
        
        app_logger.info(f"Generating custom comic: {title}")
        result = generate_custom_comic(title, story, location, user_id, comic_artist_style)
        
        if result:
            image_paths, panel_summaries, comic_script, comic_summary, audio_path = result
            
            for panel_index, path in enumerate(image_paths):
                yield "data: " + json.dumps({"progress": 50 + (panel_index * 10), "message": f"Generating panel {panel_index + 1}...", "stage": "Image Generation"}) + "\n\n"
                time.sleep(0.5)

            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            
            yield "data: " + json.dumps({"progress": 80, "message": "Generating audio narration...", "stage": "Audio Generation"}) + "\n\n"
            time.sleep(1)

            relative_audio_path = os.path.relpath(audio_path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if audio_path else None
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            yield "data: " + json.dumps({"progress": 90, "message": "Saving comic to database...", "stage": "Database Update"}) + "\n\n"
            time.sleep(1)

            db.add_comic(user_id, title, location, story, comic_script, comic_summary, ",".join(relative_paths), relative_audio_path, datetime.now().date())
            
            yield "data: " + json.dumps({"progress": 95, "message": "Finalizing custom comic...", "stage": "Finalization"}) + "\n\n"
            time.sleep(1)
            
            app_logger.info(f"Successfully generated custom comic: {title}")
            yield "data: " + json.dumps({
                "success": True,
                "html": render_template('custom_comic_result.html',
                                        title=title,
                                        original_story=story,
                                        created_at=created_at,
                                        image_paths=[url_for('serve_image', filename=path) for path in relative_paths],
                                        panel_summaries=panel_summaries,
                                        audio_path=url_for('serve_audio', filename=relative_audio_path) if relative_audio_path else None,
                                        comic_script=comic_script)
            }) + "\n\n"
        else:
            app_logger.error(f"Failed to generate custom comic: {title}")
            yield "data: " + json.dumps({"success": False, "message": 'Failed to generate custom comic. Please try again.'}) + "\n\n"

        del comic_tasks[task_id]


    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/media_comic', methods=['GET', 'POST'])
@login_required
def media_comic():
    if request.method == 'POST':
        media_type = request.form['media_type']
        location = request.form['location']
        comic_artist_style = request.form.get('comic_artist_style', '')
        user_id = session['user']['id']
        
        if not check_and_deduct_points(user_id, 'media_comic'):
            flash('Insufficient loyalty points to generate a media comic.', 'error')
            return redirect(url_for('media_comic'))
        
        task_id = str(uuid.uuid4())
        
        if media_type == 'live':
            app_logger.info("Capturing live video")
            video_path = capture_live_video()
            if video_path is None:
                app_logger.error("Failed to capture live video")
                return jsonify({'success': False, 'message': 'Failed to capture live video. Please try again.'})
            path = video_path
        else:
            if 'file' not in request.files:
                app_logger.error("No file part in the request")
                return jsonify({'success': False, 'message': 'No file part in the request. Please try again.'})
            file = request.files['file']
            if file.filename == '':
                app_logger.error("No file selected")
                return jsonify({'success': False, 'message': 'No file selected. Please try again.'})
            if file:
                filename = file.filename
                path = os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'uploads', filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                file.save(path)
            else:
                app_logger.error("File upload failed")
                return jsonify({'success': False, 'message': 'File upload failed. Please try again.'})
        
        comic_tasks[task_id] = {
            'status': 'started',
            'media_type': media_type,
            'path': path,
            'location': location,
            'comic_artist_style': comic_artist_style,
            'user_id': session['user']['id']
        }
        return jsonify({'task_id': task_id})
    
    return render_template('media_comic.html')

@app.route('/admin/loyalty_config', methods=['GET', 'POST'])
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
        return redirect(url_for('admin_loyalty_config'))
    
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

@app.route('/media_comic_progress')
@login_required
def media_comic_progress():
    task_id = request.args.get('task_id')
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        task = comic_tasks[task_id]
        media_type = task['media_type']
        path = task['path']
        location = task['location']
        comic_artist_style = task.get('comic_artist_style', '')  # Make it optional
        user_id = task['user_id']

        yield "data: " + json.dumps({"progress": 5, "message": "Initializing media comic generation...", "stage": "Preparation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 10, "message": "Processing media input...", "stage": "Media Analysis"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 20, "message": "Analyzing media content...", "stage": "Content Analysis"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 30, "message": "Generating comic ideas...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 40, "message": "Creating comic script...", "stage": "Text Generation"}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 50, "message": "Generating media comic...", "stage": "Comic Generation"}) + "\n\n"
        time.sleep(1)
        
        app_logger.info(f"Generating media comic from {media_type}")
        result = generate_media_comic(media_type, path, location, user_id, comic_artist_style)
        
        if result:
            image_paths, summary, comic_scripts, panel_summaries, audio_paths = result
            
            for panel_index, path in enumerate(image_paths):
                yield "data: " + json.dumps({"progress": 50 + (panel_index * 10), "message": f"Generating panel {panel_index + 1}...", "stage": "Image Generation"}) + "\n\n"
                time.sleep(0.5)

            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            relative_audio_paths = [os.path.relpath(path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if path else None for path in audio_paths]
            db = get_db()
            comics = []

            yield "data: " + json.dumps({"progress": 80, "message": "Generating audio narration...", "stage": "Audio Generation"}) + "\n\n"
            time.sleep(1)

            yield "data: " + json.dumps({"progress": 90, "message": "Saving comics to database...", "stage": "Database Update"}) + "\n\n"
            time.sleep(1)

            for i, (relative_path, comic_script, panel_summary, relative_audio_path) in enumerate(zip(relative_paths, comic_scripts, panel_summaries, relative_audio_paths)):
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                title = f"Media Comic {i+1}"
                image_paths_str = ",".join(relative_paths)
                db.add_comic(user_id, title, location, f"{media_type} comic", comic_script, summary, image_paths_str, relative_audio_path, datetime.now().date())
                comics.append({
                    'title': title,
                    'original_story': f"{media_type} comic",
                    'created_at': created_at,
                    'image_paths': [url_for('serve_image', filename=path) for path in relative_paths],
                    'panel_summaries': panel_summary,
                    'audio_path': url_for('serve_audio', filename=relative_audio_path) if relative_audio_path else None,
                    'comic_script': comic_script,
                    'story_source_url': ''
                })

            yield "data: " + json.dumps({"progress": 95, "message": "Finalizing media comic...", "stage": "Finalization"}) + "\n\n"
            time.sleep(1)
            
            app_logger.info(f"Successfully generated media comic from {media_type}")
            yield "data: " + json.dumps({"success": True, "html": render_template('media_comic_result.html', comics=comics)}) + "\n\n"
        else:
            app_logger.error(f"Failed to generate media comic from {media_type}")
            yield "data: " + json.dumps({"success": False, "message": 'Failed to generate media comic. Please try again.'}) + "\n\n"

        del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

def get_unique_locations():
    db = get_db()
    return db.get_unique_locations()

@app.route('/view_all_comics')
@login_required
def view_all_comics():
    db = get_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    location = request.args.get('location')
    
    # Convert date strings to datetime objects
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    app_logger.debug(f"Filtering comics - Start Date: {start_date}, End Date: {end_date}, Location: {location}")
    
    user_id = session['user']['id']
    is_admin = session['user']['role'] == 'admin'
    comics = db.get_filtered_comics(user_id, is_admin, start_date, end_date, location)
    app_logger.info(f"Viewing filtered comics: {len(comics)} comics found")
    
    unique_comics = []
    seen_titles = set()
    seen_stories = set()

    for comic in comics:
        title = comic.get('title', '')
        story = comic.get('story', comic.get('original_story', ''))
        
        if title not in seen_titles and story not in seen_stories:
            seen_titles.add(title)
            seen_stories.add(story)

            if 'image_path' in comic and comic['image_path']:
                app_logger.debug(f"Original image path: {comic['image_path']}")
                # Handle both comma-separated strings and list of paths
                if isinstance(comic['image_path'], str):
                    image_paths = [path.strip() for path in comic['image_path'].split(',') if path.strip()]
                elif isinstance(comic['image_path'], list):
                    image_paths = comic['image_path']
                else:
                    image_paths = [comic['image_path']]
                
                comic['image_paths'] = []
                for path in image_paths:
                    if not os.path.isabs(path):
                        path = os.path.join(config.OUTPUT_DIR, path)
                    if os.path.exists(path):
                        relative_path = os.path.relpath(path, config.OUTPUT_DIR)
                        comic['image_paths'].append(url_for('serve_image', filename=relative_path))
                    else:
                        app_logger.warning(f"Image file not found: {path}")
            else:
                app_logger.warning(f"Comic missing image path: {comic.get('title', 'Unknown')}")
                comic['image_paths'] = []
            
            if 'audio_path' in comic and comic['audio_path']:
                audio_path = comic['audio_path']
                if not os.path.isabs(audio_path):
                    audio_path = os.path.join(config.OUTPUT_DIR, 'audio', audio_path)
                if os.path.exists(audio_path):
                    relative_audio_path = os.path.relpath(audio_path, os.path.join(config.OUTPUT_DIR, 'audio'))
                    comic['audio_path'] = url_for('serve_audio', filename=relative_audio_path)
                else:
                    app_logger.warning(f"Audio file not found: {audio_path}")
                    comic['audio_path'] = None
            else:
                comic['audio_path'] = None
            
            if 'comic_script' not in comic or not comic['comic_script']:
                comic['comic_script'] = "No comic script available"
            
            # Ensure date is in the correct format for display
            if 'date' in comic and comic['date']:
                try:
                    if isinstance(comic['date'], str):
                        # If it's already a string, try to parse it as a date
                        comic['date'] = datetime.strptime(comic['date'], '%Y-%m-%d').strftime('%Y-%m-%d')
                    elif isinstance(comic['date'], datetime):
                        comic['date'] = comic['date'].strftime('%Y-%m-%d')
                    else:
                        app_logger.warning(f"Unexpected date format for comic: {comic.get('title', 'Unknown')}")
                        comic['date'] = str(comic['date'])  # Convert to string as a fallback
                    app_logger.debug(f"Successfully processed date for comic: {comic.get('title', 'Unknown')}, Date: {comic['date']}")
                except ValueError:
                    app_logger.error(f"Invalid date format for comic: {comic.get('title', 'Unknown')}")
                    comic['date'] = "Unknown Date"
            else:
                comic['date'] = "Unknown Date"
            
            # Ensure story is properly populated
            if 'story' not in comic or not comic['story']:
                comic['story'] = comic.get('original_story', "Story not available")
            
            # Parse panel summaries from comic_summary
            if 'comic_summary' in comic and comic['comic_summary']:
                panel_summaries = []
                summary_lines = comic['comic_summary'].split('\n')
                for i, line in enumerate(summary_lines):
                    if line.startswith('Panel '):
                        parts = line.split(': ', 1)
                        if len(parts) > 1:
                            panel_summaries.append(parts[1])
                        else:
                            # If the current line doesn't have a summary, check the next line
                            if i + 1 < len(summary_lines):
                                panel_summaries.append(summary_lines[i + 1].strip())
                            else:
                                panel_summaries.append("Panel summary not available")
                comic['panel_summaries'] = panel_summaries if panel_summaries else ["Panel summary not available"] * 3
            else:
                comic['panel_summaries'] = ["Panel summary not available"] * 3
            
            # Ensure we always have exactly 3 panel summaries
            while len(comic['panel_summaries']) < 3:
                comic['panel_summaries'].append("Panel summary not available")
            comic['panel_summaries'] = comic['panel_summaries'][:3]

            unique_comics.append(comic)
    
    locations = get_unique_locations()
    return render_template('view_all_comics.html', 
                           comics=unique_comics, 
                           locations=locations, 
                           start_date=start_date.strftime('%Y-%m-%d') if start_date else '',
                           end_date=end_date.strftime('%Y-%m-%d') if end_date else '',
                           selected_location=location)

if __name__ == '__main__':
    app_logger.info("Starting Grizz-AI web application")
    app.run(host='0.0.0.0', port=config.WEB_PORT, debug=config.WEB_DEBUG)
