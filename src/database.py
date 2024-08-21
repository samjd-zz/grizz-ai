import sqlite3
from logger import app_logger
from datetime import datetime

class ComicDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
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
        self.conn.commit()

    def add_comic(self, title, location, original_story, comic_script, story_source_url, image_path):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO comics (title, location, original_story, comic_script, story_source_url, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, location, original_story, comic_script, story_source_url, image_path, current_time))
        self.conn.commit()

    def get_comic_by_story(self, original_story):
        self.cursor.execute('SELECT * FROM comics WHERE original_story = ?', (original_story,))
        return self.cursor.fetchone()

    def get_all_comics(self):
        self.cursor.execute('SELECT * FROM comics ORDER BY created_at DESC')
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()

# Create a global instance of the database
db = ComicDatabase()

def add_comic(title, location, original_story, comic_script, story_source_url, image_path):
    try:
        db.add_comic(title, location, original_story, comic_script, story_source_url, image_path)
        app_logger.debug(f"Added comic to database: {title}")
    except Exception as e:
        app_logger.error(f"Error adding comic to database: {e}")

def get_comic_by_story(original_story):
    try:
        return db.get_comic_by_story(original_story)
    except Exception as e:
        app_logger.error(f"Error getting comic from database: {e}")
        return None

def get_all_comics():
    try:
        return db.get_all_comics()
    except Exception as e:
        app_logger.error(f"Error getting all comics from database: {e}")
        return []

def close_database():
    db.close()
    app_logger.info("Database connection closed")