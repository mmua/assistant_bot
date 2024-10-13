# test_bot.py

import os
import sqlite3
import pytest

from bot import (
    add_user,
    get_user,
    reset_daily_tokens,
    update_tokens,
    start_new_session,
    get_current_session_id,
    save_session_message,
    get_current_session_messages,
    clear_session,
    get_embedding,
    cosine_similarity,
    get_relevant_messages,
    num_tokens_from_messages,
    summarize_session,
)

# Set up a test database
TEST_DATABASE_PATH = "./test_bot.db"
conn = sqlite3.connect(TEST_DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

# Override the bot's database connection for testing
def setup_module(module):
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS sessions")
    cursor.execute("DROP TABLE IF EXISTS messages")
    # Create tables
    cursor.execute(
        """
    CREATE TABLE users (
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
    CREATE TABLE sessions (
        user_id INTEGER,
        start_date DATE,
        end_date DATE,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """
    )
    cursor.execute(
        """
    CREATE TABLE messages (
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

def teardown_module(module):
    conn.close()
    os.remove(TEST_DATABASE_PATH)

def test_add_and_get_user():
    user_id = 123456
    add_user(user_id)
    user = get_user(user_id)
    assert user is not None
    assert user[0] == user_id

def test_start_new_session():
    user_id = 123456
    session_id = start_new_session(user_id)
    assert session_id is not None
    cursor.execute("SELECT * FROM sessions WHERE rowid = ?", (session_id,))
    session = cursor.fetchone()
    assert session[0] == user_id

def test_save_and_get_messages():
    user_id = 123456
    session_id = get_current_session_id(user_id)
    save_session_message(user_id, session_id, "user", "Hello")
    messages = get_current_session_messages(user_id)
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello"

def test_clear_session():
    user_id = 123456
    clear_session(user_id)
    messages = get_current_session_messages(user_id)
    assert len(messages) == 0

# def test_get_embedding():
#     text = "This is a test."
#     embedding_json = get_embedding(text)
#     assert embedding_json is not None

def test_cosine_similarity():
    vec_a = [1, 0, 0]
    vec_b = [0, 1, 0]
    similarity = cosine_similarity(vec_a, vec_b)
    assert similarity == 0

def test_num_tokens_from_messages():
    messages = [{"role": "user", "content": "Hello, world!"}]
    tokens = num_tokens_from_messages(messages)
    assert tokens > 0

# def test_summarize_session():
#     messages = [
#         {"role": "user", "content": "Hello"},
#         {"role": "assistant", "content": "Hi, how can I help you?"},
#     ]
#     summary = summarize_session(messages)
#     assert summary != ""

