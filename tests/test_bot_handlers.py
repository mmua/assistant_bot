# # tests/test_bot.py
# import pytest
# from unittest.mock import AsyncMock, MagicMock, patch
# from bot.bot import (
#     handle_message,
#     handle_voice,
#     get_forwarded_message_author,
#     start,
#     reset_context,
#     forget_context
# )
# from bot.database.database import add_user, get_current_session_messages

# @pytest.fixture
# def update():
#     """Create a mock telegram update"""
#     update = MagicMock()
#     update.effective_user.id = 12345
#     update.message.text = "Test message"
#     return update

# @pytest.fixture
# def context():
#     """Create a mock telegram context"""
#     return MagicMock()

# @pytest.mark.asyncio
# async def test_handle_message(update, context, session):
#     """Test message handling"""
#     # Add test user
#     add_user(update.effective_user.id)
    
#     # Mock OpenAI response
#     mock_response = MagicMock()
#     mock_response.choices[0].message.content = "Test response"
#     mock_response.usage.total_tokens = 10
    
#     with patch('openai.chat.completions.create', return_value=mock_response):
#         await handle_message(update, context)
    
#     # Verify message was saved
#     messages = get_current_session_messages(update.effective_user.id)
#     assert len(messages) > 1
#     user_messages = [m for m in messages if m["role"] == "user"]
#     assert len(user_messages) == 1
#     assert user_messages[0]["content"] == "Test message"

# @pytest.mark.asyncio
# async def test_handle_voice(update, context, session):
#     """Test voice message handling"""
#     # Mock voice message
#     update.message.voice = MagicMock()
#     update.message.forward_origin = None
    
#     # Mock voice handler
#     mock_voice_handler = MagicMock()
#     mock_voice_handler.download_voice_message = AsyncMock(return_value="test.ogg")
#     mock_voice_handler.transcribe_audio = AsyncMock(return_value="Test transcription")
    
#     with patch('bot.bot.voice_handler', mock_voice_handler):
#         await handle_voice(update, context)
    
#     # Verify transcription was processed
#     messages = get_current_session_messages(update.effective_user.id)
#     assert len(messages) > 1

# def test_get_forwarded_message_author(update):
#     """Test forwarded message author extraction"""
#     # Test user forward
#     update