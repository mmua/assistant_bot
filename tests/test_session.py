# tests/test_session.py
import pytest
from datetime import date
import json
from unittest.mock import patch
from bot.session import SessionContext
from bot.database.database import (
    add_user,
    clear_session, 
    start_new_session, 
    get_session_messages,
    save_session_message
)
from bot.database.models import Session, Message

@pytest.fixture
def user_context(db_session, user_id_generator):
    """Create a test user and session context"""
    user_id = user_id_generator()
    add_user(user_id)
    start_new_session(user_id)
    return SessionContext(user_id)

def test_session_context_initialization(user_context, db_session):
    """Test session context initialization"""
    assert user_context.user_id is not None
    assert user_context.session_id is not None
    assert user_context.messages is not None
    assert len(user_context.messages) >= 1  # Should have at least system message

def test_save_message(user_context, db_session):
    """Test message saving"""
    test_message = "Test message"
    user_context.save_message("user", test_message)
    
    # Verify message was saved
    messages = get_session_messages(user_context.session_id)
    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == test_message

def test_load_messages(user_context, db_session):
    """Test message loading"""
    clear_session(user_context.session_id)
    # Add some test messages
    messages = [
        ("user", "Hello"),
        ("assistant", "Hi there"),
        ("user", "How are you?")
    ]
    for role, content in messages:
        save_session_message(
            user_id=user_context.user_id,
            session_id=user_context.session_id,
            role=role,
            content=content,
            compute_embedding=False
        )
    db_session.flush()

    # Load messages and verify
    loaded_messages = user_context.load_messages()
    assert len(loaded_messages) >= len(messages)  # Account for system message
    
    # Verify message order
    user_and_assistant_messages = [
        m for m in loaded_messages 
        if m["role"] in ("user", "assistant")
    ]
    for i, (role, content) in enumerate(messages):
        assert user_and_assistant_messages[i]["role"] == role
        assert user_and_assistant_messages[i]["content"] == content

@pytest.mark.asyncio
async def test_summarize_if_needed(user_context, monkeypatch):
    """Test session summarization"""
    # Mock token calculation to force summarization
    def mock_calculate_total_tokens():
        return 10023000  # Above DEFAULT_CONTEXT_TOKENS
    
    monkeypatch.setattr(
        user_context,
        'calculate_total_tokens',
        mock_calculate_total_tokens
    )
    
    # Add some test messages
    messages = [
        ("user", "Message 1"),
        ("assistant", "Response 1"),
        ("user", "Message 2"),
        ("assistant", "Response 2")
    ]
    for role, content in messages:
        save_session_message(
            user_id=user_context.user_id,
            session_id=user_context.session_id,
            role=role,
            content=content,
            compute_embedding=False
        )
    
    # Mock summarize_session to avoid actual API call
    def mock_summarize(messages):
        return "Summary of conversation"
    
    monkeypatch.setattr(
        'bot.session.summarize_session',
        mock_summarize
    )
    
    # Test summarization
    user_context.summarize_if_needed()
    # messages = get_session_messages(user_context.session_id)
    # assert len(messages) == 1  # Only system message after summarization
    # assert "Summary" in messages[0]["content"]

def test_add_relevant_information(user_context, db_session):
    from bot.llm import get_embedding
    clear_session(user_context.session_id)
    user_context.messages = []
    mock_embedding = json.dumps([0.1, 0.2, 0.3])  # Mock embedding data
    
    # Mock the get_embedding function
    with patch('bot.llm.get_embedding', return_value=mock_embedding):
        save_session_message(
            user_id=user_context.user_id,
            session_id=user_context.session_id,
            role="user",
            content="Test message for embedding",
            compute_embedding=True
        )

        new_message = "Test message for context"
        user_context.add_relevant_information(new_message, 0)

    assert len(user_context.messages) == 1
    system_messages = [
        m for m in user_context.messages 
        if m["role"] == "system" and "Relevant information" in m["content"]
    ]
    assert len(system_messages) > 0

def test_token_calculation(user_context, db_session):
    """Test token calculation"""
    messages = [
        ("user", "Hello"),
        ("assistant", "Hi there"),
        ("user", "How are you?")
    ]
    for role, content in messages:
        save_session_message(
            user_id=user_context.user_id,
            session_id=user_context.session_id,
            role=role,
            content=content,
            compute_embedding=False
        )
    
    token_count = user_context.calculate_total_tokens()
    assert token_count > 0  # Exact number depends on tokenizer

def test_edge_cases(db_session, user_id_generator):
    """Test edge cases for session context"""
    nonexistent_user_id = user_id_generator()
    
    # Test with non-existent user
    context = SessionContext(nonexistent_user_id)
    assert context.messages is not None
    assert len(context.messages) >= 1  # Should still have system message
    
    # Test with empty session
    user_id = user_id_generator()
    add_user(user_id)
    context = SessionContext(user_id)
    assert context.messages is not None
    assert len(context.messages) >= 1  # Should have system message