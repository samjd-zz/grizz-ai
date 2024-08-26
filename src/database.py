import os
import sqlite3
from datetime import datetime
from config import load_config
from logger import app_logger
import threading

config = load_config()

class ComicDatabase:
    _local = threading.local()

    @classmethod
    def get_connection(cls):
        if not hasattr(cls._local, "connection"):
            cls._local.connection = sqlite3.connect(config.DB_PATH)
            cls._local.connection.row_factory = sqlite3.Row
        return cls._local.connection

    @classmethod
    def get_cursor(cls):
        return cls.get_connection().cursor()

    @classmethod
    def create_table(cls):
        cursor = cls.get_cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comics (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                original_story TEXT NOT NULL,
                comic_script TEXT NOT NULL,
                story_source_url TEXT,
                image_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cls.get_connection().commit()

    @classmethod
    def add_comic(cls, title, location, original_story, comic_script, story_source_url, image_path):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = cls.get_cursor()
        cursor.execute('''
            INSERT INTO comics (title, location, original_story, comic_script, story_source_url, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, location, original_story, comic_script, story_source_url, image_path, current_time))
        cls.get_connection().commit()

    @classmethod
    def get_comic_by_story(cls, original_story):
        cursor = cls.get_cursor()
        cursor.execute('SELECT * FROM comics WHERE original_story = ?', (original_story,))
        result = cursor.fetchone()
        return dict(result) if result else None

    @classmethod
    def get_all_comics(cls):
        cursor = cls.get_cursor()
        cursor.execute('SELECT * FROM comics ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def close(cls):
        if hasattr(cls._local, "connection"):
            cls._local.connection.close()
            del cls._local.connection

    @classmethod
    def purge_database(cls):
        cursor = cls.get_cursor()
        cursor.execute('DELETE FROM comics')
        cls.get_connection().commit()
        app_logger.info("Database purged")

# Ensure the table is created
ComicDatabase.create_table()

def add_comic(title, location, original_story, comic_script, story_source_url, image_path):
    try:
        ComicDatabase.add_comic(title, location, original_story, comic_script, story_source_url, image_path)
        app_logger.debug(f"Added comic to database: {title}")
    except Exception as e:
        app_logger.error(f"Error adding comic to database: {e}")

def get_comic_by_story(original_story):
    try:
        return ComicDatabase.get_comic_by_story(original_story)
    except Exception as e:
        app_logger.error(f"Error getting comic from database: {e}")
        return None

def get_all_comics():
    try:
        return ComicDatabase.get_all_comics()
    except Exception as e:
        app_logger.error(f"Error getting all comics from database: {e}")
        return []

def close_database():
    ComicDatabase.close()
    app_logger.info("Database connection closed")

def purge_database():
    try:
        ComicDatabase.purge_database()
        app_logger.info("Database purged successfully")
    except Exception as e:
        app_logger.error(f"Error purging database: {e}")