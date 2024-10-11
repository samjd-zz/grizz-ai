import os
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, send_from_directory, g, jsonify, Response, stream_with_context, redirect, session, flash
from functools import wraps
from main import generate_daily_comic, generate_custom_comic, generate_media_comic, capture_live_video
from psy_researcher import perform_duckduckgo_search
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    app_logger.debug(f"Login route accessed with method: {request.method}")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        app_logger.debug(f"Login attempt for username: {username}")
        app_logger.debug(f"Admin password from config: {config.ADMIN_PASSWORD}")
        db = get_db()
        user = db.get_user_by_username(username)
        app_logger.debug(f"User retrieved from database: {user}")
        if user:
            app_logger.debug(f"Stored password hash: {user['password_hash']}")
            is_valid = db.check_password(username, password)
            app_logger.debug(f"Password check result: {is_valid}")
            if is_valid:
                app_logger.debug(f"Login successful for user: {user}")
                session['user'] = {'username': user['username'], 'role': user['role']}
                app_logger.debug(f"Session after login: {session}")
                flash('Logged in successfully.')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                app_logger.warning(f"Invalid password for username: {username}")
                flash('Invalid username or password')
        else:
            app_logger.warning(f"User not found: {username}")
            flash('Invalid username or password')
    return render_template('login.html')

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

@app.before_first_request
def before_first_request():
    # Create Yogi Bear voice when the application starts
    if config.GENERATE_AUDIO:
        create_yogi_bear_voice()

@app.after_request
def add_csp_header(response):
    csp = ("default-src 'self'; "
           "script-src 'self' 'unsafe-inline' https://code.jquery.com https://unpkg.com; "
           "style-src 'self' 'unsafe-inline' https://unpkg.com; "
           "img-src 'self' https://*.tile.openstreetmap.org https://unpkg.com data:; "
           "connect-src 'self' https://nominatim.openstreetmap.org;")
    response.headers['Content-Security-Policy'] = csp
    return response

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
    return send_from_directory(os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio'), filename)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/daily_comic', methods=['GET', 'POST'])
@login_required
def daily_comic():
    if request.method == 'POST':
        location = request.form['location']
        task_id = str(uuid.uuid4())
        comic_tasks[task_id] = {'status': 'started', 'location': location}
        return jsonify({'task_id': task_id})
    return render_template('daily_comic.html', config=config)

@app.route('/daily_comic_progress')
@login_required
def daily_comic_progress():
    task_id = request.args.get('task_id')
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        task = comic_tasks[task_id]
        location = task['location']

        yield "data: " + json.dumps({"progress": 10, "message": "Checking for local events..."}) + "\n\n"
        time.sleep(1)
        
        app_logger.debug(f"Checking for local events in: {location}")
        local_events = get_local_events(location)
        if not local_events or (len(local_events) == 1 and local_events[0]['title'] == "No Current News Events Reported"):
            app_logger.info(f"No events found for {location}")
            yield "data: " + json.dumps({"progress": 100, "message": "No events found for today. Please try again later."}) + "\n\n"
            return

        yield "data: " + json.dumps({"progress": 30, "message": "Generating daily comic..."}) + "\n\n"
        time.sleep(1)
        
        app_logger.debug(f"Generating daily comic for location: {location}")
        generated_comics = generate_daily_comic(location)
        
        if generated_comics:
            yield "data: " + json.dumps({"progress": 60, "message": "Processing generated comics..."}) + "\n\n"
            time.sleep(1)
            
            # Update image paths and process comics
            for event in generated_comics:
                if 'image_paths' in event:
                    event['image_paths'] = [url_for('serve_image', filename=os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']), _external=True) for path in event['image_paths']]
                elif 'image_path' in event:
                    event['image_paths'] = [url_for('serve_image', filename=os.path.relpath(event['image_path'], app.config['GENERATED_IMAGES_FOLDER']), _external=True)]
                if 'audio_path' in event and event['audio_path']:
                    relative_audio_path = os.path.relpath(event['audio_path'], os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio'))
                    event['audio_path'] = url_for('serve_audio', filename=relative_audio_path, _external=True)
                else:
                    event['audio_path'] = None
                event['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if 'comic_script' not in event:
                    event['comic_script'] = "No comic script available"
                event['story'] = event['story'].replace('-', '').strip()
                event['comic_script'] = format_comic_script(event['comic_script'])
                if 'story_source' not in event:
                    event['story_source'] = "Source not available"
                if 'panel_summaries' not in event:
                    event['panel_summaries'] = ["Panel summary not available"] * 3

            yield "data: " + json.dumps({"progress": 90, "message": "Finalizing daily comic..."}) + "\n\n"
            time.sleep(1)
            
            app_logger.info(f"Successfully generated daily comic for {location}")
            yield "data: " + json.dumps({"success": True, "html": render_template('daily_comic_result.html', events=generated_comics, location=location)}) + "\n\n"
        else:
            app_logger.error(f"Failed to generate daily comic for {location}")
            yield "data: " + json.dumps({"success": False, "message": 'Failed to generate daily comic. Please try again later.'}) + "\n\n"

        del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/custom_comic', methods=['GET', 'POST'])
@login_required
def custom_comic():
    if request.method == 'POST':
        title = request.form['title']
        story = request.form['story']
        location = request.form['location']
        task_id = str(uuid.uuid4())
        comic_tasks[task_id] = {'status': 'started', 'title': title, 'story': story, 'location': location}
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

        yield "data: " + json.dumps({"progress": 10, "message": "Checking for existing comics..."}) + "\n\n"
        time.sleep(1)
        
        db = get_db()
        existing_comic = db.get_comic_by_title_or_story(title, story)
        if existing_comic:
            app_logger.info(f"Comic already exists for title: {title} or story: {story}")
            yield "data: " + json.dumps({"success": False, "message": 'A comic with this title or story already exists.'}) + "\n\n"
            return

        yield "data: " + json.dumps({"progress": 30, "message": "Generating custom comic..."}) + "\n\n"
        time.sleep(1)
        
        app_logger.info(f"Generating custom comic: {title}")
        result = generate_custom_comic(title, story, location)
        
        if result:
            yield "data: " + json.dumps({"progress": 60, "message": "Processing generated comic..."}) + "\n\n"
            time.sleep(1)
            
            image_paths, panel_summaries, comic_script, comic_summary, audio_path = result
            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            relative_audio_path = os.path.relpath(audio_path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if audio_path else None
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.add_comic(title, location, story, comic_script, comic_summary, ",".join(relative_paths), relative_audio_path, datetime.now().date())
            
            yield "data: " + json.dumps({"progress": 90, "message": "Finalizing custom comic..."}) + "\n\n"
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
        
        comic_tasks[task_id] = {'status': 'started', 'media_type': media_type, 'path': path, 'location': location}
        return jsonify({'task_id': task_id})
    
    return render_template('media_comic.html')

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

        yield "data: " + json.dumps({"progress": 10, "message": "Processing media input..."}) + "\n\n"
        time.sleep(1)

        yield "data: " + json.dumps({"progress": 30, "message": "Generating media comic..."}) + "\n\n"
        time.sleep(1)
        
        app_logger.info(f"Generating media comic from {media_type}")
        result = generate_media_comic(media_type, path, location)
        
        if result:
            yield "data: " + json.dumps({"progress": 60, "message": "Processing generated comic..."}) + "\n\n"
            time.sleep(1)
            
            image_paths, summary, comic_scripts, panel_summaries, audio_paths = result
            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            relative_audio_paths = [os.path.relpath(path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if path else None for path in audio_paths]
            db = get_db()
            comics = []
            for i, (relative_path, comic_script, panel_summary, relative_audio_path) in enumerate(zip(relative_paths, comic_scripts, panel_summaries, relative_audio_paths)):
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                title = f"Media Comic {i+1}"
                image_paths_str = ",".join(relative_paths)
                db.add_comic(title, location, f"{media_type} comic", comic_script, summary, image_paths_str, relative_audio_path, datetime.now().date())
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

            yield "data: " + json.dumps({"progress": 90, "message": "Finalizing media comic..."}) + "\n\n"
            time.sleep(1)
            
            app_logger.info(f"Successfully generated media comic from {media_type}")
            yield "data: " + json.dumps({"success": True, "html": render_template('media_comic_result.html', comics=comics)}) + "\n\n"
        else:
            app_logger.error(f"Failed to generate media comic from {media_type}")
            yield "data: " + json.dumps({"success": False, "message": 'Failed to generate media comic. Please try again.'}) + "\n\n"

        del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

    return render_template('media_comic.html')

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        query = request.form['query']
        num_queries = int(request.form['num_queries'])
        num_results = int(request.form['num_results'])
        app_logger.info(f"Performing DuckDuckGo search: {query}")
        results = perform_duckduckgo_search(query, num_queries, num_results)
        return render_template('search_results.html', results=results)
    return render_template('search.html')

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
    
    comics = db.get_filtered_comics(start_date, end_date, location)
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
                if not comic['image_paths']:
                    comic['image_paths'] = None
            else:
                app_logger.warning(f"Comic missing image path: {comic.get('title', 'Unknown')}")
                comic['image_paths'] = None
            
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
