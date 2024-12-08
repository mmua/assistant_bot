# tests/test_database.py
import pytest
from unittest.mock import patch
import json
from datetime import date, datetime, timedelta
from bot.database.models import User, Session, Message
from bot.database.database import (
    get_session_messages,
    get_user,
    add_user,
    reset_daily_tokens,
    update_tokens,
    start_new_session,
    get_current_session_id,
    save_session_message,
    get_current_session_messages,
    get_user_messages,
    clear_session,
    close_session,
    DatabaseConnection
)

def test_database_connection_no_url():
    """Test DatabaseConnection raises error with no URL"""
    with pytest.raises(ValueError):
        DatabaseConnection(url=None)

def test_database_connection_invalid_url():
    """Test DatabaseConnection raises error with invalid URL"""
    with pytest.raises(Exception):
        DatabaseConnection(url="invalid://url")

def test_user_operations(db_session):
    """Test user CRUD operations"""
    user_id = 12345
    
    # Test add_user
    add_user(user_id)
    user = get_user(user_id)
    assert user is not None
    assert user.user_id == user_id
    assert user.last_reset == date.today()
    
    # Test add_user idempotency
    add_user(user_id)  # Should not raise error
    assert db_session.query(User).filter_by(user_id=user_id).count() == 1

def test_token_management(db_session):
    """Test token management operations"""
    user_id = 12345
    add_user(user_id)
    
    # Test update_tokens
    update_tokens(user_id, 100)
    user = get_user(user_id)
    assert user.tokens_used == 100
    assert user.daily_tokens_used == 100
    
    # Test reset_daily_tokens
    reset_daily_tokens(user_id)
    user = get_user(user_id)
    assert user.tokens_used == 100  # Total should not change
    assert user.daily_tokens_used == 0  # Daily should reset
    assert user.last_reset == date.today()

def test_session_management(db_session):
    """Test session management operations"""
    user_id = 12345
    add_user(user_id)
    
    # Test start_new_session
    session_id = start_new_session(user_id)
    assert session_id is not None
    db_session.expire_all()  # Clear the session cache
    
    session = db_session.query(Session).filter_by(id=session_id).first()
    assert session is not None
    assert session.user_id == user_id
    assert session.start_date == date.today()
    
    # Test get_current_session_id
    current_session_id = get_current_session_id(user_id)
    assert current_session_id == session_id
    
    # Test close_session
    closed_session_id = close_session(user_id)
    assert closed_session_id == session_id
    
    db_session.expire_all()  # Clear the session cache again
    session = db_session.query(Session).filter_by(id=session_id).first()
    assert session.end_date == date.today()
    
    # Test get_current_session_id creates new session after closing
    new_session_id = get_current_session_id(user_id)
    assert new_session_id != session_id

def test_message_operations(db_session):
    """Test message operations"""
    user_id = 12345
    add_user(user_id)
    session_id = start_new_session(user_id)
    
    # Test save_session_message
    test_message = "Hello, world!"
    save_session_message(user_id, session_id, "user", test_message, compute_embedding=False)
    db_session.expire_all()

    # Verify message in database
    message = db_session.query(Message).filter(
        Message.user_id == user_id,
        Message.session_id == session_id,
        Message.content == test_message
    ).first()
    assert message is not None, "Message not found in database"
    
    # Test get_current_session_messages
    messages = get_session_messages(session_id)
    assert len(messages) > 1  # Account for system message

    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == test_message

    # Test clear_session
    clear_session(user_id)
    db_session.expire_all()

    messages = get_current_session_messages(user_id)
    assert len(messages) == 1  # Only system message remains
    assert messages[0]["role"] == "system"

def test_edge_cases(db_session):
    """Test edge cases and error conditions"""
    nonexistent_user_id = 99999
    
    # Test operations with non-existent user
    assert get_user(nonexistent_user_id) is None
    reset_daily_tokens(nonexistent_user_id)  # Should not raise error
    update_tokens(nonexistent_user_id, 100)  # Should not raise error
    
    # Test clear_session with no existing session
    clear_session(nonexistent_user_id)  # Should not raise error
    
    # Test close_session with no open session
    close_session(nonexistent_user_id)  # Should not raise error

def test_daily_token_reset(db_session):
    """Test automatic daily token reset"""
    user_id = 22345
    add_user(user_id)

    # Initial state
    user = get_user(user_id)
    assert user.tokens_used == 0
    assert user.daily_tokens_used == 0

    # First day: Add initial tokens
    update_tokens(user_id, 101)
    user = get_user(user_id)
    assert user.tokens_used == 101
    assert user.daily_tokens_used == 101
    
    # Simulate next day by updating through the database connection
    user = db_session.query(User).filter(User.user_id == user_id).first()
    user.last_reset = date.today() - timedelta(days=1)
    db_session.flush()  # Ensure the update is written to the database

    # Next day: Add more tokens
    update_tokens(user_id, 50)
    user = get_user(user_id)
    assert user.tokens_used == 151  # Total should accumulate
    assert user.daily_tokens_used == 50  # Daily should reset before adding new tokens
    assert user.last_reset == date.today()  # Should be updated to today

def test_message_with_embedding(db_session):
    """Test message saving with embedding computation"""
    user_id = 54321
    add_user(user_id)
    session_id = start_new_session(user_id)
    
    test_message = "Hello, world!"
    mock_embedding = json.dumps([0.1, 0.2, 0.3])  # Mock embedding data
    
    # Mock the get_embedding function
    with patch('bot.llm.get_embedding', return_value=mock_embedding):
        save_session_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=test_message,
            compute_embedding=True  # Explicitly request embedding
        )
    
    # Verify message was saved with embedding
    message = db_session.query(Message).filter(
        Message.user_id == user_id,
        Message.session_id == session_id,
        Message.content == test_message
    ).first()
    
    assert message is not None
    assert message.content == test_message
    assert message.embedding == mock_embedding  # Verify embedding was saved