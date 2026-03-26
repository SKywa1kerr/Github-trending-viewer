import sqlite3
import os
from app.config import config


def get_db_path():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return config.DB_PATH


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_full_name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            description_zh TEXT DEFAULT '',
            readme_summary_zh TEXT DEFAULT '',
            stars INTEGER DEFAULT 0,
            stars_gained INTEGER DEFAULT 0,
            language TEXT DEFAULT '',
            topics TEXT DEFAULT '[]',
            category TEXT DEFAULT 'other',
            repo_url TEXT DEFAULT '',
            score REAL DEFAULT 0.0,
            last_updated TEXT DEFAULT '',
            translated_at TEXT DEFAULT '',
            fetched_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT DEFAULT 'other',
            created_at TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


def is_db_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return count == 0
