from flask import Blueprint, send_from_directory, current_app, url_for, render_template
import os
from logger import app_logger
from .utils_module import get_album_info

media_bp = Blueprint('media', __name__)

@media_bp.route('/images/<path:filename>')
def serve_image(filename):
    app_logger.debug(f"Serving image: {filename}, from folder: {current_app.config['GENERATED_IMAGES_FOLDER']}")
    # Clean up the filename path if needed
    if filename.startswith('./'):
        filename = filename[2:]  # Remove ./ prefix
    if filename.startswith('output/'):
        filename = filename[7:]  # Remove output/ prefix
    
    app_logger.debug(f"Cleaned image path for serving: {filename}")
    return send_from_directory(current_app.config['GENERATED_IMAGES_FOLDER'], filename)

@media_bp.route('/audio/<path:filename>')
def serve_audio(filename):
    app_logger.debug(f"Serving audio: {filename}")
    # Clean up the filename path if needed
    if filename.startswith('./'):
        filename = filename[2:]  # Remove ./ prefix
    
    # Determine if we're serving a generated audio file or an album
    if 'output/audio' in filename or filename.endswith('.mp3'):
        # Serving generated audio
        audio_dir = os.path.join(current_app.config['GENERATED_IMAGES_FOLDER'], 'audio')
        app_logger.debug(f"Serving generated audio from: {audio_dir}")
        return send_from_directory(audio_dir, os.path.basename(filename))
    else:
        # Serving album audio
        app_logger.debug(f"Serving album audio from: {os.path.join(current_app.root_path, '..', current_app.config['ALBUMS_FOLDER'])}")
        return send_from_directory(os.path.join(current_app.root_path, '..', current_app.config['ALBUMS_FOLDER']), filename)

@media_bp.route('/music')
def music():
    music_data = get_album_info(current_app)
    app_logger.info(f"Music data for template: {music_data}")
    app_logger.debug(f"Genres found: {list(music_data.keys())}")
    for genre, albums in music_data.items():
        app_logger.debug(f"Genre: {genre}, Number of albums: {len(albums)}")
    return render_template('music.html', music=music_data)
