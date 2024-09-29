import os
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, send_from_directory, g, jsonify, make_response
from main import generate_daily_comic, generate_custom_comic, generate_media_comic, capture_live_video
from psy_researcher import perform_duckduckgo_search
from config import load_config
from database import ComicDatabase
from logger import app_logger
from event_fetcher import get_local_events
from text_analysis import create_yogi_bear_voice

app = Flask(__name__)
config = load_config()

# Configure image serving for generated images
app.config['GENERATED_IMAGES_FOLDER'] = config.OUTPUT_DIR
os.makedirs(app.config['GENERATED_IMAGES_FOLDER'], exist_ok=True)

@app.before_first_request
def before_first_request():
    # Create Yogi Bear voice when the application starts
    if config.GENERATE_AUDIO:
        create_yogi_bear_voice()

@app.after_request
def add_csp_header(response):
    csp = "default-src 'self'; script-src 'self' 'unsafe-inline' https://code.jquery.com; style-src 'self' 'unsafe-inline';"
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
def index():
    return render_template('index.html')

@app.route('/daily_comic', methods=['GET', 'POST'])
def daily_comic():
    if request.method == 'POST':
        location = request.form['location']
        app_logger.debug(f"Checking for local events in: {location}")
        local_events = get_local_events(location)
        if not local_events or (len(local_events) == 1 and local_events[0]['title'] == "No Current News Events Reported"):
            app_logger.info(f"No events found for {location}")
            return jsonify({'success': False, 'message': 'No events found for today. Please try again later.'})
        
        app_logger.debug(f"Generating daily comic for location: {location}")
        generated_comics = generate_daily_comic(location)
        if generated_comics:
            # Update image paths to use the custom image route
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
                # Ensure story_source is included
                if 'story_source' not in event:
                    event['story_source'] = "Source not available"
            app_logger.info(f"Successfully generated daily comic for {location}")
            return jsonify({'success': True, 'html': render_template('daily_comic_result.html', events=generated_comics, location=location)})
        else:
            app_logger.error(f"Failed to generate daily comic for {location}")
            return jsonify({'success': False, 'message': 'Failed to generate daily comic. Please try again later.'})
    return render_template('daily_comic.html')

@app.route('/custom_comic', methods=['GET', 'POST'])
def custom_comic():
    if request.method == 'POST':
        title = request.form['title']
        story = request.form['story']
        location = request.form['location']
        app_logger.info(f"Generating custom comic: {title}")
        result = generate_custom_comic(title, story, location)
        if result:
            image_path, summary, comic_script, audio_path = result
            relative_path = os.path.relpath(image_path, app.config['GENERATED_IMAGES_FOLDER'])
            relative_audio_path = os.path.relpath(audio_path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if audio_path else None
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db = get_db()
            db.add_comic(title, location, story, comic_script, "", relative_path, relative_audio_path, datetime.now().date())
            app_logger.info(f"Successfully generated custom comic: {title}")
            return jsonify({
                'success': True,
                'html': render_template('custom_comic_result.html', 
                                        title=title,
                                        original_story=story,
                                        created_at=created_at,
                                        image_path=url_for('serve_image', filename=relative_path),
                                        audio_path=url_for('serve_audio', filename=relative_audio_path) if relative_audio_path else None,
                                        comic_script=comic_script)
            })
        else:
            app_logger.error(f"Failed to generate custom comic: {title}")
            return jsonify({'success': False, 'message': 'Failed to generate custom comic. Please try again.'})
    return render_template('custom_comic.html')

@app.route('/media_comic', methods=['GET', 'POST'])
def media_comic():
    if request.method == 'POST':
        media_type = request.form['media_type']
        location = request.form['location']
        
        if media_type == 'live':
            app_logger.info("Capturing live video")
            video_path = capture_live_video()
            if video_path is None:
                app_logger.error("Failed to capture live video")
                return "Failed to capture live video. Please try again."
            path = video_path
        else:
            if 'file' not in request.files:
                app_logger.error("No file part in the request")
                return "No file part in the request. Please try again."
            file = request.files['file']
            if file.filename == '':
                app_logger.error("No file selected")
                return "No file selected. Please try again."
            if file:
                filename = file.filename
                path = os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'uploads', filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                file.save(path)
            else:
                app_logger.error("File upload failed")
                return "File upload failed. Please try again."
        
        app_logger.info(f"Generating media comic from {media_type}")
        result = generate_media_comic(media_type, path, location)
        if result:
            image_paths, summary, comic_scripts, audio_paths = result
            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            relative_audio_paths = [os.path.relpath(path, os.path.join(app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if path else None for path in audio_paths]
            db = get_db()
            comics = []
            for i, (relative_path, comic_script, relative_audio_path) in enumerate(zip(relative_paths, comic_scripts, relative_audio_paths)):
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                title = f"Media Comic {i+1}"
                db.add_comic(title, location, f"{media_type} comic", comic_script, "", relative_path, relative_audio_path, datetime.now().date())
                comics.append({
                    'title': title,
                    'original_story': f"{media_type} comic",
                    'created_at': created_at,
                    'image_path': url_for('serve_image', filename=relative_path),
                    'audio_path': url_for('serve_audio', filename=relative_audio_path) if relative_audio_path else None,
                    'comic_script': comic_script,
                    'story_source_url': ''
                })
            app_logger.info(f"Successfully generated media comic from {media_type}")
            return render_template('media_comic_result.html', comics=comics)
        else:
            app_logger.error(f"Failed to generate media comic from {media_type}")
            return "Failed to generate media comic. Please try again."
    return render_template('media_comic.html')

@app.route('/search', methods=['GET', 'POST'])
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
    
    for comic in comics:
        if 'image_path' in comic and comic['image_path']:
            app_logger.debug(f"Original image path: {comic['image_path']}")
            # Use os.path.relpath to get the relative path from OUTPUT_DIR
            relative_path = os.path.relpath(comic['image_path'], config.OUTPUT_DIR)
            app_logger.debug(f"Relative image path: {relative_path}")
            full_path = os.path.join(config.OUTPUT_DIR, relative_path)
            app_logger.debug(f"Full image path: {full_path}")
            if os.path.exists(full_path):
                comic['image_path'] = url_for('serve_image', filename=relative_path)
                app_logger.debug(f"Updated image path: {comic['image_path']}")
            else:
                app_logger.warning(f"Image file not found: {full_path}")
                comic['image_path'] = None
        else:
            app_logger.warning(f"Comic missing image path: {comic.get('title', 'Unknown')}")
        
        if 'audio_path' in comic and comic['audio_path']:
            relative_audio_path = os.path.relpath(comic['audio_path'], os.path.join(config.OUTPUT_DIR, 'audio'))
            comic['audio_path'] = url_for('serve_audio', filename=relative_audio_path)
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
    
    locations = get_unique_locations()
    return render_template('view_all_comics.html', 
                           comics=comics, 
                           locations=locations, 
                           start_date=start_date.strftime('%Y-%m-%d') if start_date else '',
                           end_date=end_date.strftime('%Y-%m-%d') if end_date else '',
                           selected_location=location)

if __name__ == '__main__':
    app_logger.info("Starting Grizz-AI web application")
    app.run(host='0.0.0.0', port=config.WEB_PORT, debug=config.WEB_DEBUG)