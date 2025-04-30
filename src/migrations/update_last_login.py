import sqlite3
import os
from logger import app_logger
from config import load_config

config = load_config()

def migrate_last_login():
    """
    Migration script to update the last_login column in the users table.
    """
    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()

        # Check if last_login_date exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'last_login_date' in columns:
            # Copy data from last_login_date to last_login
            cursor.execute('''
                UPDATE users 
                SET last_login = last_login_date
                WHERE last_login IS NULL AND last_login_date IS NOT NULL
            ''')
            
            # Drop the old column (SQLite doesn't support DROP COLUMN directly)
            cursor.execute('''
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    loyalty_points INTEGER DEFAULT 0,
                    last_login TEXT,
                    last_purchase_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO users_new 
                SELECT id, username, email, password_hash, role, loyalty_points, last_login, last_purchase_date, created_at 
                FROM users
            ''')
            
            cursor.execute('DROP TABLE users')
            cursor.execute('ALTER TABLE users_new RENAME TO users')
            
        conn.commit()
        app_logger.info("Successfully migrated last_login column")
        
    except Exception as e:
        app_logger.error(f"Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_last_login()
