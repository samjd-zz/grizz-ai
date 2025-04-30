from flask import Blueprint, render_template, request, jsonify, Response, current_app, url_for, flash, redirect, session, g
from flask import stream_with_context
import os
import json
import time
import uuid
import sqlite3
from datetime import datetime
from logger import app_logger
from database import ComicDatabase
from modules import generate_daily_comic, generate_custom_comic, generate_media_comic
from event_fetcher import get_local_events
from .auth_module import login_required
from .loyalty_module import check_and_deduct_points
from .utils_module import format_comic_script, get_unique_locations
from utils import sanitize_location

comic_bp = Blueprint('comic', __name__)

# Store ongoing comic generation tasks
comic_tasks = {}

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

def get_config():
    return current_app.config['APP_CONFIG']

def should_check_loyalty(user_id):
    """Helper function to determine if loyalty points should be checked"""
    db = get_db()
    user = db.get_user_by_id(user_id)
    return user['role'] != 'admin' if user else True

@comic_bp.route('/daily_comic', methods=['GET', 'POST'])
@login_required
def daily_comic():
    app_logger.debug("Accessing daily_comic route")
    if request.method == 'POST':
        try:
            location = request.form.get('location', '').strip()
            if not location:
                app_logger.warning("Daily comic generation attempted with empty location")
                return jsonify({'success': False, 'message': 'Please provide a valid location.'}), 400
                
            comic_artist_style = request.form.get('comic_artist_style', '')
            user_id = session['user']['id']
            
            app_logger.info(f"Generating daily comic for location: {location}")
            
            # Skip loyalty check for admins
            if should_check_loyalty(user_id):
                if not check_and_deduct_points(user_id, 'daily_news_comic'):
                    return jsonify({'success': False, 'message': 'Insufficient loyalty points to generate a daily comic.'}), 400
            
            # Create sanitized location to avoid potential issues
            sanitized_location = sanitize_location(location)
            if not sanitized_location:
                return jsonify({'success': False, 'message': 'Invalid location provided. Please try a different location.'}), 400
            
            task_id = str(uuid.uuid4())
            comic_tasks[task_id] = {
                'status': 'started',
                'location': sanitized_location,
                'comic_artist_style': comic_artist_style,
                'user_id': user_id
            }
            return jsonify({'task_id': task_id}), 200
        except Exception as e:
            app_logger.error(f"Error in daily_comic POST: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'An error occurred while processing your request.'}), 500
            
    app_logger.debug("Rendering daily_comic template")
    return render_template('daily_comic.html', config=current_app.config)

@comic_bp.route('/custom_comic', methods=['GET', 'POST'])
@login_required
def custom_comic():
    if request.method == 'POST':
        try:
            title = request.form['title']
            story = request.form['story']
            location = request.form['location']
            comic_artist_style = request.form.get('comic_artist_style', '')
            user_id = session['user']['id']
            
            # Skip loyalty check for admins
            if should_check_loyalty(user_id):
                if not check_and_deduct_points(user_id, 'custom_comic'):
                    return jsonify({'success': False, 'message': 'Insufficient loyalty points to generate a custom comic.'}), 400
            
            task_id = str(uuid.uuid4())
            comic_tasks[task_id] = {
                'status': 'started',
                'title': title,
                'story': story,
                'location': location,
                'comic_artist_style': comic_artist_style,
                'user_id': user_id
            }
            return jsonify({'task_id': task_id}), 200
        except Exception as e:
            app_logger.error(f"Error in custom_comic POST: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'An error occurred while processing your request.'}), 500
            
    return render_template('custom_comic.html')

@comic_bp.route('/media_comic', methods=['GET', 'POST'])
@login_required
def media_comic():
    if request.method == 'POST':
        try:
            media_type = request.form['media_type']
            location = request.form['location']
            comic_artist_style = request.form.get('comic_artist_style', '')
            user_id = session['user']['id']
            
            # Skip loyalty check for admins
            if should_check_loyalty(user_id):
                if not check_and_deduct_points(user_id, 'media_comic'):
                    return jsonify({'success': False, 'message': 'Insufficient loyalty points to generate a media comic.'}), 400
            
            task_id = str(uuid.uuid4())
            
            if media_type == 'live':
                app_logger.info("Capturing live video")
                video_path = capture_live_video()
                if video_path is None:
                    app_logger.error("Failed to capture live video")
                    return jsonify({'success': False, 'message': 'Failed to capture live video. Please try again.'}), 500
                path = video_path
            else:
                if 'file' not in request.files:
                    app_logger.error("No file part in the request")
                    return jsonify({'success': False, 'message': 'No file part in the request. Please try again.'}), 400
                file = request.files['file']
                if file.filename == '':
                    app_logger.error("No file selected")
                    return jsonify({'success': False, 'message': 'No file selected. Please try again.'}), 400
                if file:
                    filename = file.filename
                    path = os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'uploads', filename)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    file.save(path)
                else:
                    app_logger.error("File upload failed")
                    return jsonify({'success': False, 'message': 'File upload failed. Please try again.'}), 500
            
            comic_tasks[task_id] = {
                'status': 'started',
                'media_type': media_type,
                'path': path,
                'location': location,
                'comic_artist_style': comic_artist_style,
                'user_id': session['user']['id']
            }
            return jsonify({'task_id': task_id}), 200
        except Exception as e:
            app_logger.error(f"Error in media_comic POST: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': 'An error occurred while processing your request.'}), 500
    
    return render_template('media_comic.html')

@comic_bp.route('/daily_comic_progress')
@login_required
def daily_comic_progress():
    task_id = request.args.get('task_id')
    app_logger.debug(f"Daily comic progress requested for task_id: {task_id}")
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        try:
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
            
            # Handle no events case
            if not local_events or (len(local_events) == 1 and "No Current News Events" in local_events[0]['title']):
                app_logger.info(f"No events found for {location}")
                no_news_event = {
                    'title': "No Current News Events",
                    'story': "There are no significant news events to report for this area in the past 7 days.",
                    'full_story_source_url': "Local news monitoring",
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'panel_summaries': ["No news events to report", "Area is currently quiet", "Check back later for updates"]
                }
                
                yield "data: " + json.dumps({"progress": 20, "message": "Generating no news comic...", "stage": "Comic Generation"}) + "\n\n"
                time.sleep(1)
                
                result = generate_daily_comic(location, user_id, comic_artist_style, no_news_event=no_news_event)
                if result and len(result) > 0:
                    # Process image paths for the no news event
                    event = result[0]
                    image_paths = event.get('image_paths', [])
                    if image_paths:
                        # Convert image paths to URLs
                        event['image_paths'] = [
                            url_for('media.serve_image', 
                                   filename=os.path.relpath(path, current_app.config['GENERATED_IMAGES_FOLDER']), 
                                   _external=True) 
                            for path in image_paths
                        ]
                    
                    # Ensure all required fields are present
                    event['created_at'] = event.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    event['comic_script'] = format_comic_script(event.get('comic_script', "No comic script available"))
                    event['story'] = event.get('story', '').replace('-', '').strip()
                    event['full_story_source_url'] = event.get('full_story_source_url', "Local news monitoring")
                    event['panel_summaries'] = event.get('panel_summaries', ["Panel summary not available"] * 3)
                    
                    rendered_html = render_template('daily_comic_result.html', 
                                                 comics=[event], 
                                                 location=location)
                    yield "data: " + json.dumps({"success": True, "html": rendered_html}) + "\n\n"
                    return
                else:
                    yield "data: " + json.dumps({"success": False, "message": "Failed to generate daily comic. Please try again."}) + "\n\n"
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

                            # Convert to URL paths
                            converted_paths = []
                            for path in image_paths:
                                # If path is absolute, make it relative to the GENERATED_IMAGES_FOLDER
                                if os.path.isabs(path):
                                    rel_path = os.path.relpath(path, current_app.config['GENERATED_IMAGES_FOLDER'])
                                # If path already starts with the right folder structure, use as is
                                elif not path.startswith('./'):
                                    rel_path = path
                                # If path starts with './output/', remove that prefix
                                elif path.startswith('./output/'):
                                    rel_path = path[9:]  # Remove './output/' prefix
                                else:
                                    # Otherwise assume it's already relative to GENERATED_IMAGES_FOLDER
                                    rel_path = path
                                
                                url_path = url_for('media.serve_image', filename=rel_path, _external=True)
                                converted_paths.append(url_path)
                            
                            event['image_paths'] = converted_paths
                            app_logger.debug(f"Original image paths for event {event_index + 1}: {image_paths}")
                            app_logger.debug(f"Updated image paths for event {event_index + 1}: {event['image_paths']}")
                        else:
                            app_logger.warning(f"No image paths found for event {event_index + 1}")
                            event['image_paths'] = []

                        # Ensure all necessary keys are present in the event dictionary
                        event['created_at'] = event.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        event['comic_script'] = format_comic_script(event.get('comic_script', "No comic script available"))
                        event['story'] = event.get('story', '').replace('-', '').strip()
                        event['full_story_source_url'] = event.get('full_story_source_url', event.get('story_source', "Source not available"))
                        event['panel_summaries'] = event.get('panel_summaries', ["Panel summary not available"] * 3)
                    else:
                        app_logger.error(f"Unexpected event format for event {event_index + 1}")
                        continue

                rendered_html = render_template('daily_comic_result.html', comics=generated_comics, location=location)
                app_logger.debug(f"Rendered HTML: {rendered_html[:500]}...")  # Log first 500 characters of rendered HTML
                yield "data: " + json.dumps({"success": True, "html": rendered_html}) + "\n\n"
            else:
                app_logger.error("Failed to generate daily comics")
                yield "data: " + json.dumps({"success": False, "message": 'Failed to generate daily comics. Please try again.'}) + "\n\n"

        except Exception as e:
            app_logger.error(f"Error in daily_comic_progress: {str(e)}", exc_info=True)
            yield "data: " + json.dumps({"success": False, "message": 'An error occurred while generating the comic. Please try again.'}) + "\n\n"
        finally:
            if task_id in comic_tasks:
                del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@comic_bp.route('/custom_comic_progress')
@login_required
def custom_comic_progress():
    task_id = request.args.get('task_id')
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        try:
            task = comic_tasks[task_id]
            title = task['title']
            story = task['story']
            location = task['location']
            comic_artist_style = task.get('comic_artist_style', '')
            user_id = task['user_id']

            yield "data: " + json.dumps({"progress": 5, "message": "Initializing custom comic generation...", "stage": "Preparation"}) + "\n\n"
            time.sleep(1)

            yield "data: " + json.dumps({"progress": 10, "message": "Checking for existing comics...", "stage": "Database Check"}) + "\n\n"
            time.sleep(1)
            
            db = get_db()
            existing_comic = db.get_comic_by_title_or_story(title, story)
            if existing_comic:
                app_logger.info(f"Comic already exists for title: {title} or story: {story}")
                
                # Instead of showing an error, retrieve and display the existing comic
                try:
                    # Parse the image paths from the stored comma-separated string
                    image_paths = existing_comic['image_path'].split(',') if existing_comic['image_path'] else []
                    app_logger.debug(f"Retrieved existing comic with image paths: {image_paths}")
                    
                    # Get panel summaries
                    panel_summaries = []
                    if existing_comic['comic_summary']:
                        # Try to parse panel summaries from the comic summary
                        for line in existing_comic['comic_summary'].split('\n'):
                            if line.startswith('Panel ') and ':' in line:
                                panel_summary = line.split(':', 1)[1].strip()
                                panel_summaries.append(panel_summary)
                    
                    # If we couldn't parse panel summaries, create default ones
                    if not panel_summaries or len(panel_summaries) < 3:
                        panel_summaries = [
                            f"Scene 1 from {title}",
                            f"Scene 2 from {title}",
                            f"Scene 3 from {title}"
                        ]
                    
                    # Format the created_at date
                    created_at = existing_comic['created_at'] if 'created_at' in existing_comic else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Prepare the audio path
                    audio_path = None
                    if existing_comic['audio_path']:
                        audio_path = url_for('media.serve_audio', filename=existing_comic['audio_path'])
                    
                    # Render the HTML for the existing comic
                    html = render_template('custom_comic_result.html',
                                          title=existing_comic['title'],
                                          original_story=existing_comic['original_story'],
                                          created_at=created_at,
                                          image_paths=[url_for('media.serve_image', filename=path) for path in image_paths],
                                          panel_summaries=panel_summaries,
                                          audio_path=audio_path,
                                          comic_script=existing_comic['comic_script'])
                    
                    # Return success with the HTML content
                    yield "data: " + json.dumps({"success": True, "html": html}) + "\n\n"
                except Exception as e:
                    app_logger.error(f"Error rendering existing comic: {e}", exc_info=True)
                    yield "data: " + json.dumps({"success": False, "message": f'Error displaying existing comic: {str(e)}'}) + "\n\n"
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
                # Image paths from generate_custom_comic are already relative to OUTPUT_DIR
                image_paths, panel_summaries, comic_script, comic_summary, audio_path = result
                
                for panel_index, path in enumerate(image_paths):
                    yield "data: " + json.dumps({"progress": 50 + (panel_index * 10), "message": f"Generating panel {panel_index + 1}...", "stage": "Image Generation"}) + "\n\n"
                    time.sleep(0.5)
                
                # No need to make them relative again, they already are
                
                yield "data: " + json.dumps({"progress": 80, "message": "Generating audio narration...", "stage": "Audio Generation"}) + "\n\n"
                time.sleep(1)

                relative_audio_path = os.path.relpath(audio_path, os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if audio_path else None
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                yield "data: " + json.dumps({"progress": 90, "message": "Saving comic to database...", "stage": "Database Update"}) + "\n\n"
                time.sleep(1)

                # Direct database insert to avoid parameter issues
                try:
                    image_path_str = ",".join(image_paths)
                    app_logger.debug(f"Saving image paths to database: {image_path_str}")
                    
                    conn = sqlite3.connect(current_app.config['APP_CONFIG'].DB_PATH)
                    cursor = conn.cursor()
                    
                    # Insert using direct SQL
                    cursor.execute('''
                        INSERT INTO comics (user_id, title, location, original_story, comic_script, comic_summary, 
                                           story_source_url, image_path, audio_path, date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, 
                        title, 
                        location, 
                        story, 
                        comic_script, 
                        comic_summary, 
                        "", 
                        image_path_str, 
                        relative_audio_path, 
                        datetime.now().date(), 
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    
                    conn.commit()
                    conn.close()
                    app_logger.debug(f"Successfully saved comic to database with direct SQL: {title}")
                except Exception as e:
                    app_logger.error(f"Error saving to database with direct SQL: {e}")
                    
                    # Fall back to the regular method
                    try:
                        db.add_comic(
                            user_id=user_id,
                            title=title, 
                            location=location, 
                            original_story=story, 
                            comic_script=comic_script, 
                            comic_summary=comic_summary, 
                            story_source_url="",
                            image_path=image_path_str,
                            audio_path=relative_audio_path, 
                            date=datetime.now().date()
                        )
                        app_logger.debug("Fallback to db.add_comic succeeded")
                    except Exception as e2:
                        app_logger.error(f"Both database save methods failed: {e2}")
                
                yield "data: " + json.dumps({"progress": 95, "message": "Finalizing custom comic...", "stage": "Finalization"}) + "\n\n"
                time.sleep(1)
                
                app_logger.info(f"Successfully generated custom comic: {title}")
                yield "data: " + json.dumps({
                    "success": True,
                    "html": render_template('custom_comic_result.html',
                                            title=title,
                                            original_story=story,
                                            created_at=created_at,
                                            image_paths=[url_for('media.serve_image', filename=path) for path in image_paths],
                                            panel_summaries=panel_summaries,
                                            audio_path=url_for('media.serve_audio', filename=relative_audio_path) if relative_audio_path else None,
                                            comic_script=comic_script)
                }) + "\n\n"
            else:
                app_logger.error(f"Failed to generate custom comic: {title}")
                yield "data: " + json.dumps({"success": False, "message": 'Failed to generate custom comic. Please try again.'}) + "\n\n"

        except Exception as e:
            app_logger.error(f"Error in custom_comic_progress: {str(e)}", exc_info=True)
            yield "data: " + json.dumps({"success": False, "message": 'An error occurred while generating the comic. Please try again.'}) + "\n\n"
        finally:
            if task_id in comic_tasks:
                del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@comic_bp.route('/media_comic_progress')
@login_required
def media_comic_progress():
    task_id = request.args.get('task_id')
    if task_id not in comic_tasks:
        return jsonify({'error': 'Invalid task ID'}), 400

    def generate():
        try:
            task = comic_tasks[task_id]
            media_type = task['media_type']
            path = task['path']
            location = task['location']
            comic_artist_style = task.get('comic_artist_style', '')
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

                relative_paths = [os.path.relpath(path, current_app.config['GENERATED_IMAGES_FOLDER']) for path in image_paths]
                relative_audio_paths = [os.path.relpath(path, os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'audio')) if path else None for path in audio_paths]
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
                        'image_paths': [url_for('media.serve_image', filename=path) for path in relative_paths],
                        'panel_summaries': panel_summary,
                        'audio_path': url_for('media.serve_audio', filename=relative_audio_path) if relative_audio_path else None,
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

        except Exception as e:
            app_logger.error(f"Error in media_comic_progress: {str(e)}", exc_info=True)
            yield "data: " + json.dumps({"success": False, "message": 'An error occurred while generating the comic. Please try again.'}) + "\n\n"
        finally:
            if task_id in comic_tasks:
                del comic_tasks[task_id]

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@comic_bp.route('/view_all_comics')
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
                app_logger.debug(f"Processing image paths for comic {title}: {image_paths}")
                
                for path in image_paths:
                    # Clean up any path issues
                    path = path.strip()
                    
                    # Check if path exists directly
                    if os.path.exists(path):
                        app_logger.debug(f"Image exists at absolute path: {path}")
                        relative_path = os.path.relpath(path, current_app.config['GENERATED_IMAGES_FOLDER'])
                        comic['image_paths'].append(url_for('media.serve_image', filename=relative_path))
                        continue
                    
                    # Try with the GENERATED_IMAGES_FOLDER prefix
                    full_path = os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], path)
                    if os.path.exists(full_path):
                        app_logger.debug(f"Image exists at combined path: {full_path}")
                        comic['image_paths'].append(url_for('media.serve_image', filename=path))
                        continue
                        
                    # Try with variations of path formatting
                    if path.startswith('./output/'):
                        # Remove the ./output/ prefix
                        clean_path = path[9:]
                        full_path = os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], clean_path)
                        if os.path.exists(full_path):
                            app_logger.debug(f"Image exists at clean path: {full_path}")
                            comic['image_paths'].append(url_for('media.serve_image', filename=clean_path))
                            continue
                    
                    # If we got here, the image wasn't found
                    app_logger.warning(f"Image file not found for any path variation: {path}")
            else:
                app_logger.warning(f"Comic missing image path: {comic.get('title', 'Unknown')}")
                comic['image_paths'] = []
            
            if 'audio_path' in comic and comic['audio_path']:
                audio_path = comic['audio_path']
                if not os.path.isabs(audio_path):
                    audio_path = os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'audio', audio_path)
                if os.path.exists(audio_path):
                    relative_audio_path = os.path.relpath(audio_path, os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'audio'))
                    comic['audio_path'] = url_for('media.serve_audio', filename=relative_audio_path)
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
