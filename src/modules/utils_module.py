import re
import os
from datetime import datetime
from flask import g, url_for
from database import ComicDatabase
from logger import app_logger

def get_db():
    if 'db' not in g:
        g.db = ComicDatabase()
    return g.db

def format_comic_script(script):
    # Remove extra characters like '+' and '**'
    script = re.sub(r'[+*]', '', script)
    # Split the script into lines
    lines = script.split('\n')
    # Remove empty lines and strip whitespace
    lines = [line.strip() for line in lines if line.strip()]
    # Join the lines back together
    return '\n'.join(lines)

def get_unique_locations():
    db = get_db()
    return db.get_unique_locations()

def get_album_info(app):
    albums_dir = os.path.join(app.root_path, '..', app.config['ALBUMS_FOLDER'])
    app_logger.debug(f"Albums directory: {albums_dir}")
    music = {}
    for genre in os.listdir(albums_dir):
        genre_path = os.path.join(albums_dir, genre)
        app_logger.debug(f"Checking genre: {genre}, path: {genre_path}")
        if os.path.isdir(genre_path):
            normalized_genre = genre.lower()
            music[normalized_genre] = []
            for album in os.listdir(genre_path):
                if album.endswith('.mp4'):
                    album_info = {
                        'title': ' '.join(album.split('.')[0].split('_')).title(),
                        'filename': album,
                        'url': url_for('media.serve_audio', filename=f'{genre}/{album}')
                    }
                    music[normalized_genre].append(album_info)
                    app_logger.debug(f"Added album for {normalized_genre}: {album_info}")
    app_logger.debug(f"Final music data: {music}")
    return music
