import os
import sqlite3
import datetime
import logging

from bot.bot_messages import get_assistant_role
from bot.llm import get_embedding

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/bot.db")

# You might want to handle the connection differently if using threading or async
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

def create_tables():

    # Create tables if they don't exist
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        token_limit INTEGER,
        tokens_used INTEGER DEFAULT 0,
        daily_tokens_used INTEGER DEFAULT 0,
        last_reset DATE
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER,
        start_date DATE,
        end_date DATE,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_id INTEGER,
        role TEXT,
        content TEXT,
        embedding TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(session_id) REFERENCES sessions(rowid)
    )
    """
    )
    conn.commit()

# Helper functions
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def add_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, last_reset) VALUES (?, ?)",
        (user_id, datetime.date.today()),
    )
    conn.commit()


def reset_daily_tokens(user_id):
    cursor.execute(
        "UPDATE users SET daily_tokens_used = 0, last_reset = ? WHERE user_id = ?",
        (datetime.date.today(), user_id),
    )
    conn.commit()


def update_tokens(user_id, tokens):
    cursor.execute("SELECT last_reset FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    last_reset = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
    if last_reset < datetime.date.today():
        reset_daily_tokens(user_id)
    cursor.execute(
        "UPDATE users SET tokens_used = tokens_used + ?, daily_tokens_used = daily_tokens_used + ? WHERE user_id = ?",
        (tokens, tokens, user_id),
    )
    conn.commit()


def start_new_session(user_id):
    cursor.execute(
        "INSERT INTO sessions (user_id, start_date) VALUES (?, ?)",
        (user_id, datetime.date.today()),
    )
    conn.commit()
    return cursor.lastrowid  # This will give us the session_id


def get_current_session_id(user_id):
    cursor.execute(
        "SELECT rowid FROM sessions WHERE user_id = ? AND end_date IS NULL",
        (user_id,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        # Start a new session if none exists
        return start_new_session(user_id)


def save_session_message(user_id, session_id, role, content):
    # Compute embedding for all messages
    embedding = get_embedding(content)
    cursor.execute(
        "INSERT INTO messages (user_id, session_id, role, content, embedding) VALUES (?, ?, ?, ?, ?)",
        (user_id, session_id, role, content, embedding),
    )
    conn.commit()


def get_current_session_messages(user_id):
    # FIXME: refactor out OpenAI pieces
    session_id = get_current_session_id(user_id)
    cursor.execute(
        """
    SELECT role, content FROM messages
    WHERE session_id = ?
    ORDER BY id ASC
    """,
        (session_id,),
    )
    rows = cursor.fetchall()
    messages = [{"role": row[0], "content": row[1]} for row in rows]
    messages.insert(0, {"role": "system", "content": get_assistant_role()})
    return messages


def get_user_messages(user_id):
    cursor.execute(
    """
    SELECT content, embedding FROM messages
    WHERE user_id = ? AND embedding IS NOT NULL
    """,
        (user_id,),
    )
    rows = cursor.fetchall()
    relevant_messages = [(content, embedding) for content, embedding in rows]
    return relevant_messages
    
def clear_session(user_id):
    session_id = get_current_session_id(user_id)
    cursor.execute(
        """
    DELETE FROM messages WHERE session_id = ?
    """,
        (session_id,),
    )
    cursor.execute(
        """
    DELETE FROM sessions WHERE rowid = ?
    """,
        (session_id,),
    )
    conn.commit()

def close_session(user_id):
    cursor.execute(
            "UPDATE sessions SET end_date = ? WHERE user_id = ? AND end_date IS NULL",
            (datetime.date.today(), user_id),
        )
    conn.commit()
