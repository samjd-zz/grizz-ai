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
                comic_summary TEXT,
                story_source_url TEXT,
                image_path TEXT NOT NULL,
                audio_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date DATE NOT NULL
            )
        ''')
        cls.get_connection().commit()

    @classmethod
    def add_comic(cls, title, location, original_story, comic_script, comic_summary, story_source_url, image_path, audio_path=None, date=None):
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if date is None:
                date = datetime.now().date()
            cursor = cls.get_cursor()
            cursor.execute('''
                INSERT INTO comics (title, location, original_story, comic_script, comic_summary, story_source_url, image_path, audio_path, created_at, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, location, original_story, comic_script, comic_summary, story_source_url, image_path, audio_path, current_time, date))
            cls.get_connection().commit()
            app_logger.debug(f"Added comic to database: {title}")
        except Exception as e:
            app_logger.error(f"Error adding comic to database: {e}")

    @classmethod
    def get_comic_by_story(cls, original_story):
        try:
            cursor = cls.get_cursor()
            cursor.execute('SELECT * FROM comics WHERE original_story = ?', (original_story,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            app_logger.error(f"Error getting comic from database: {e}")
            return None

    @classmethod
    def get_all_comics(cls):
        try:
            cursor = cls.get_cursor()
            cursor.execute('SELECT * FROM comics ORDER BY date DESC, created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            app_logger.error(f"Error getting all comics from database: {e}")
            return []

    @classmethod
    def get_filtered_comics(cls, start_date=None, end_date=None, location=None):
        try:
            cursor = cls.get_cursor()
            query = 'SELECT * FROM comics WHERE 1=1'
            params = []
            if start_date:
                query += ' AND date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND date <= ?'
                params.append(end_date)
            if location:
                query += ' AND location = ?'
                params.append(location)
            query += ' ORDER BY date DESC, created_at DESC'
            app_logger.debug(f"Executing query: {query} with params: {params}")
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            app_logger.error(f"Error getting filtered comics from database: {e}")
            return []

    @classmethod
    def get_unique_locations(cls):
        try:
            cursor = cls.get_cursor()
            cursor.execute('SELECT DISTINCT location FROM comics ORDER BY location')
            return [row['location'] for row in cursor.fetchall()]
        except Exception as e:
            app_logger.error(f"Error getting unique locations from database: {e}")
            return []

    @classmethod
    def close(cls):
        if hasattr(cls._local, "connection"):
            cls._local.connection.close()
            del cls._local.connection
        app_logger.info("Database connection closed")

    @classmethod
    def purge_database(cls):
        try:
            cursor = cls.get_cursor()
            cursor.execute('DELETE FROM comics')
            cls.get_connection().commit()
            app_logger.info("Database purged successfully")
        except Exception as e:
            app_logger.error(f"Error purging database: {e}")

    @classmethod
    def add_audio_path_column(cls):
        cursor = cls.get_cursor()
        try:
            cursor.execute('ALTER TABLE comics ADD COLUMN audio_path TEXT')
            cls.get_connection().commit()
            app_logger.debug("Added audio_path column to comics table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                app_logger.debug("audio_path column already exists in comics table")
            else:
                raise e

    @classmethod
    def add_date_column(cls):
        cursor = cls.get_cursor()
        try:
            cursor.execute('ALTER TABLE comics ADD COLUMN date DATE')
            cls.get_connection().commit()
            app_logger.debug("Added date column to comics table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                app_logger.debug("date column already exists in comics table")
            else:
                raise e

    @classmethod
    def add_comic_summary_column(cls):
        cursor = cls.get_cursor()
        try:
            cursor.execute('ALTER TABLE comics ADD COLUMN comic_summary TEXT')
            cls.get_connection().commit()
            app_logger.debug("Added comic_summary column to comics table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                app_logger.debug("comic_summary column already exists in comics table")
            else:
                raise e

    @classmethod
    def populate_from_output_folder(cls):
        output_dir = config.OUTPUT_DIR
        for location_folder in os.listdir(output_dir):
            location_path = os.path.join(output_dir, location_folder)
            if os.path.isdir(location_path):
                location = location_folder.replace('_', ' ')
                for date_folder in os.listdir(location_path):
                    date_path = os.path.join(location_path, date_folder)
                    if os.path.isdir(date_path):
                        date = datetime.strptime(date_folder, "%Y_%m_%d").date()
                        for file in os.listdir(date_path):
                            if file.endswith('.png'):
                                image_path = os.path.join(date_path, file)
                                title = file.replace('ggs_grizzly_news_', '').replace('.png', '').replace('_', ' ')
                                summary_file = file.replace('.png', '_summary.txt')
                                summary_path = os.path.join(date_path, summary_file)
                                if os.path.exists(summary_path):
                                    with open(summary_path, 'r') as f:
                                        original_story = f.read()
                                else:
                                    original_story = "Summary not available"
                                
                                # Check for audio file
                                audio_file = file.replace('.png', '.mp3')
                                audio_path = os.path.join(date_path, audio_file)
                                if not os.path.exists(audio_path):
                                    audio_path = None
                                
                                cls.add_comic(title, location, original_story, "Comic script not available", "Comic summary not available", "", image_path, audio_path, date)
        app_logger.info("Database populated from output folder")

    @classmethod
    def initialize_database(cls):
        cls.create_table()
        cls.add_audio_path_column()
        cls.add_date_column()
        cls.add_comic_summary_column()
        cls.purge_database()
        cls.populate_from_output_folder()

# Initialize the database
ComicDatabase.initialize_database()
