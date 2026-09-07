from pathlib import Path
import sqlite3

# 1. Get the absolute path of the directory containing THIS file (agent/)
# .parent gives you the 'agent/' folder.
# Use .parent.parent if you want the DB file in the root project folder instead!
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "agent_data.db"

table_creation_query = """
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

def init_db():
    db_exists = DB_PATH.is_file()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if not db_exists:
        cur.execute(table_creation_query)
        conn.commit()
        print("Tables initialized")
    return conn, cur

def save_message(role: str, content: str):
    conn, cur = init_db()
    try:
        cur.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content)
        )
        conn.commit()
        return "Message saved"
    finally:
        conn.close()

def get_recent_messages(limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # ← magic line
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, role, content, created_at "
            "FROM messages "
            "ORDER BY created_at DESC "
            "LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
