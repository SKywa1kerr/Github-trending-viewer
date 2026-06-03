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
            translation_status TEXT DEFAULT 'pending',
            translation_attempts INTEGER DEFAULT 0,
            translation_next_retry_at TEXT DEFAULT '',
            translation_error TEXT DEFAULT '',
            source_signature TEXT DEFAULT '',
            translated_signature TEXT DEFAULT '',
            translation_provider TEXT DEFAULT '',
            translation_model TEXT DEFAULT '',
            readme_fetched_at TEXT DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS star_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            stars INTEGER DEFAULT 0,
            recorded_date TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, recorded_date)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            score REAL DEFAULT 0.0,
            generated_at TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Add first_seen_at column if missing
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN first_seen_at TEXT DEFAULT ''")
        conn.execute("UPDATE projects SET first_seen_at = fetched_at WHERE first_seen_at = '' OR first_seen_at IS NULL")
    except Exception:
        pass
    for sql in [
        "ALTER TABLE projects ADD COLUMN translation_status TEXT DEFAULT 'pending'",
        "ALTER TABLE projects ADD COLUMN translation_attempts INTEGER DEFAULT 0",
        "ALTER TABLE projects ADD COLUMN translation_next_retry_at TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN translation_error TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN source_signature TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN translated_signature TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN translation_provider TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN translation_model TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN readme_fetched_at TEXT DEFAULT ''",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_projects_category_score
        ON projects(category, score DESC);

        CREATE INDEX IF NOT EXISTS idx_projects_language_score
        ON projects(language, score DESC);

        CREATE INDEX IF NOT EXISTS idx_projects_translation_queue
        ON projects(translation_status, translation_next_retry_at);

        CREATE INDEX IF NOT EXISTS idx_projects_last_updated
        ON projects(last_updated DESC);
    """)
    conn.commit()
    conn.close()


def is_db_empty():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return count == 0
