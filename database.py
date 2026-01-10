import sqlite3
import json
from datetime import datetime

DB_FILE = "chat_history.db"

def init_db():
    """Initializes the database table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            session_data TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def save_session(username, session_id, session_data, title=None):
    """Upserts a user session.
    
    If title is None, it won't update the title (useful for auto-saves that shouldn't reset custom names).
    However, if it's a new record, a default title should be provided by the caller or handled here.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    json_data = json.dumps(session_data, ensure_ascii=False)
    
    # Check if exists to determine whether to update title (if title is None)
    c.execute("SELECT title FROM user_sessions WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    
    if row:
        # Update existing
        if title:
            c.execute('''
                UPDATE user_sessions 
                SET title = ?, session_data = ?, updated_at = ?
                WHERE session_id = ?
            ''', (title, json_data, now, session_id))
        else:
            c.execute('''
                UPDATE user_sessions 
                SET session_data = ?, updated_at = ?
                WHERE session_id = ?
            ''', (json_data, now, session_id))
    else:
        # Insert new
        final_title = title if title else "新对话"
        c.execute('''
            INSERT INTO user_sessions (session_id, username, title, created_at, updated_at, session_data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, username, final_title, now, now, json_data))
        
    conn.commit()
    conn.close()

def get_user_sessions(username):
    """Retrieves all sessions for a specific user, sorted by updated_at desc."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Allow dict-like access
    c = conn.cursor()
    
    c.execute('''
        SELECT * FROM user_sessions 
        WHERE username = ? 
        ORDER BY updated_at DESC
    ''', (username,))
    
    rows = c.fetchall()
    conn.close()
    
    sessions = []
    for row in rows:
        sessions.append({
            "id": row["session_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "session_data": json.loads(row["session_data"])
        })
    return sessions

def delete_session(session_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def rename_session(session_id, new_title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE user_sessions SET title = ? WHERE session_id = ?", (new_title, session_id))
    conn.commit()
    conn.close()
