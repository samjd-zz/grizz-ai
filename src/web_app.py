from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, g
import os
from main import generate_daily_comic, generate_custom_comic, generate_media_comic, perform_duckduckgo_search, capture_live_video
from config import load_config
from database import ComicDatabase, add_comic, get_all_comics
from logger import app_logger

app = Flask(__name__)
config = load_config()

# Configure static file serving for generated images
app.config['GENERATED_IMAGES_FOLDER'] = os.path.join(config.OUTPUT_DIR, 'static')
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

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.config['GENERATED_IMAGES_FOLDER'], filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/daily_comic', methods=['GET', 'POST'])
def daily_comic():
    if request.method == 'POST':
        location = request.form['location']
        app_logger.info(f"Generating daily comic for location: {location}")
        local_events = generate_daily_comic(location)
        if local_events:
            # Update image paths to be relative to the static folder
            for event in local_events:
                event['image_path'] = os.path.relpath(event['image_path'], app.config['GENERATED_IMAGES_FOLDER'])
                event['image_path'] = url_for('static', filename=event['image_path'])
            app_logger.info(f"Successfully generated daily comic for {location}")
            return render_template('daily_comic_result.html', events=local_events, location=location)
        else:
            app_logger.error(f"Failed to generate daily comic for {location}")
            return "Failed to generate daily comic. Please try again."
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
            relative_image_path = os.path.relpath(image_path, app.config['GENERATED_IMAGES_FOLDER'])
            db = get_db()
            db.add_comic(title, location, story, summary, "", relative_image_path)
            app_logger.info(f"Successfully generated custom comic: {title}")
            return render_template('custom_comic_result.html', image_path=url_for('static', filename=relative_image_path), summary=summary)
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
            path = request.form['path']
        
        app_logger.info(f"Generating media comic from {media_type}")
        result = generate_media_comic(media_type, path, location)
        if result:
            image_paths, summary = result
            relative_image_paths = [os.path.relpath(path, app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
            db = get_db()
            for i, image_path in enumerate(relative_image_paths):
                db.add_comic(f"Media Comic {i+1}", location, f"{media_type} comic", summary, "", image_path)
            app_logger.info(f"Successfully generated media comic from {media_type}")
            return render_template('media_comic_result.html', image_paths=[url_for('static', filename=path) for path in relative_image_paths], summary=summary)
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
    for comic in comics:
        comic['image_path'] = url_for('static', filename=comic['image_path'])
    app_logger.info(f"Viewing all comics: {len(comics)} comics found")
    return render_template('view_all_comics.html', comics=comics)

if __name__ == '__main__':
    app_logger.info("Starting Grizz-AI web application")
    app.run(host='0.0.0.0', port=config.WEB_PORT, debug=config.WEB_DEBUG)