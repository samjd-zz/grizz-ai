from flask import Blueprint, send_from_directory, current_app, url_for, render_template
import os
from logger import app_logger
from .utils_module import get_album_info

media_bp = Blueprint('media', __name__)

@media_bp.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(current_app.config['GENERATED_IMAGES_FOLDER'], filename)

@media_bp.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(os.path.join(current_app.root_path, '..', current_app.config['ALBUMS_FOLDER']), filename)

@media_bp.route('/music')
def music():
    music_data = get_album_info(current_app)
    app_logger.info(f"Music data for template: {music_data}")
    app_logger.debug(f"Genres found: {list(music_data.keys())}")
    for genre, albums in music_data.items():
        app_logger.debug(f"Genre: {genre}, Number of albums: {len(albums)}")
    return render_template('music.html', music=music_data)
