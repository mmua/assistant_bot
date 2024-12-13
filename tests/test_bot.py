import os
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bot.database.models import Base, User, Session, Message
from bot.database.database import (
    add_user,
    get_user,
    reset_daily_tokens,
    update_tokens,
    start_new_session,
    get_current_session_id,
    save_session_message,
    get_current_session_messages,
    clear_session,
)
from bot.llm import (
    get_embedding,
    cosine_similarity,
    num_tokens_from_messages,
)


def test_add_and_get_user(db_session):
    user_id = 123456
    add_user(user_id)
    user = get_user(user_id)
    assert user is not None
    assert user.user_id == user_id

def test_start_new_session(db_session):
    user_id = 123456
    session_id = start_new_session(user_id)
    assert session_id is not None
    
    session = db_session.query(Session).filter(Session.id == session_id).first()
    assert session.user_id == user_id
    assert session.start_date == date.today()

def test_save_and_get_messages(db_session):
    user_id = 123456
    session_id = get_current_session_id(user_id)
    save_session_message(user_id, session_id, "user", "Hello")
    messages = get_current_session_messages(user_id)
    
    # First message is system role from get_assistant_role()
    assert len(messages) > 1
    # Find our test message
    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Hello"

def test_clear_session(db_session):
    user_id = 123456
    session_id = get_current_session_id(user_id)
    clear_session(session_id)
    messages = get_current_session_messages(user_id)
    # Only system message should remain
    assert len(messages) == 1
    assert messages[0]["role"] == "system"

def test_update_tokens(db_session):
    user_id = 123456
    initial_tokens = 555
    update_tokens(user_id, initial_tokens)
    user = get_user(user_id)
    assert user.tokens_used == initial_tokens
    assert user.daily_tokens_used == initial_tokens

def test_reset_daily_tokens(db_session):
    user_id = 123456
    reset_daily_tokens(user_id)
    user = get_user(user_id)
    assert user.daily_tokens_used == 0
    assert user.last_reset == date.today()

def test_cosine_similarity():
    vec_a = [1, 0, 0]
    vec_b = [0, 1, 0]
    similarity = cosine_similarity(vec_a, vec_b)
    assert similarity == 0

def test_num_tokens_from_messages():
    messages = [{"role": "user", "content": "Hello, world!"}]
    tokens = num_tokens_from_messages(messages)
    assert tokens > 0

def test_get_current_session_id(db_session):
    user_id = 123456
    session_id = get_current_session_id(user_id)
    assert session_id is not None
    
    # Should return the same session if called again
    second_session_id = get_current_session_id(user_id)
    assert session_id == second_session_id

def test_get_current_session_messages_empty(db_session):
    user_id = 999999  # New user
    add_user(user_id)
    messages = get_current_session_messages(user_id)
    # Should only contain system message
    assert len(messages) == 1
    assert messages[0]["role"] == "system"