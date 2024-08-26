from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, g
import os
from main import generate_daily_comic, generate_custom_comic, generate_media_comic, perform_duckduckgo_search, capture_live_video
from config import load_config
from database import ComicDatabase, add_comic, get_all_comics
from logger import app_logger
from event_fetcher import get_local_events

app = Flask(__name__)
config = load_config()

# Configure image serving for generated images
app.config['GENERATED_IMAGES_FOLDER'] = config.OUTPUT_DIR
os.makedirs(app.config['GENERATED_IMAGES_FOLDER'], exist_ok=True)

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['GENERATED_IMAGES_FOLDER'], filename)

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
            return render_template('daily_comic_result.html', events=[], location=location, message="No events found for today. Please try again later.")
        
        app_logger.debug(f"Generating daily comic for location: {location}")
        generated_comics = generate_daily_comic(location)
        if generated_comics:
            # Update image paths to use the custom image route
            for event in generated_comics:
                if 'image_path' in event:
                    relative_path = os.path.relpath(event['image_path'], app.config['GENERATED_IMAGES_FOLDER'])
                    event['image_path'] = url_for('serve_image', filename=relative_path)
            app_logger.info(f"Successfully generated daily comic for {location}")
            return render_template('daily_comic_result.html', events=generated_comics, location=location)
        else:
            app_logger.error(f"Failed to generate daily comic for {location}")
            return render_template('daily_comic_result.html', events=[], location=location, message="Failed to generate daily comic. Please try again later.")
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
            image_path, summary = result
            relative_path = os.path.relpath(image_path, app.config['GENERATED_IMAGES_FOLDER'])
            db = get_db()
            db.add_comic(title, location, story, summary, "", relative_path)
            app_logger.info(f"Successfully generated custom comic: {title}")
            return render_template('custom_comic_result.html', image_path=url_for('serve_image', filename=relative_path), summary=summary)
        else:
            app_logger.error(f"Failed to generate custom comic: {title}")
            return "Failed to generate custom comic. Please try again."
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
            image_paths, summary = result
            relative_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            db = get_db()
            for i, relative_path in enumerate(relative_paths):
                db.add_comic(f"Media Comic {i+1}", location, f"{media_type} comic", summary, "", relative_path)
            app_logger.info(f"Successfully generated media comic from {media_type}")
            return render_template('media_comic_result.html', image_paths=[url_for('serve_image', filename=path) for path in relative_paths], summary=summary)
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

@app.route('/view_all_comics')
def view_all_comics():
    db = get_db()
    comics = db.get_all_comics()
    app_logger.info(f"Viewing all comics: {len(comics)} comics found")
    
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
    
    return render_template('view_all_comics.html', comics=comics)

if __name__ == '__main__':
    app_logger.info("Starting Grizz-AI web application")
    app.run(host='0.0.0.0', port=config.WEB_PORT, debug=config.WEB_DEBUG)