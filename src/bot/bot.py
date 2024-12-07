import os
import logging
import openai

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

from bot.llm import split_text, clean_transcript, DEFAULT_OPENAI_MODEL
from bot.session import DEFAULT_CONTEXT_TOKENS, SessionContext
from bot.bot_messages import START_TOKEN, FORGET_TOKEN, NEXT_TOKEN, ERROR_TOKEN, ADD_USER_TOKEN, UNAUTHORIZED_TOKEN, get_bot_message
from bot.database import add_user, clear_session, close_session, get_user, get_user_messages, start_new_session, update_tokens
from bot.voice_handler import VoiceHandler

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SBER_SPEECH_API_KEY = os.getenv("SBER_SPEECH_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

MAX_TELEGRAM_MESSAGE_LENGTH = 4096

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY


# Initialize Voice Handler
voice_handler = VoiceHandler(SBER_SPEECH_API_KEY)


def get_forwarded_message_author(update: Update) -> str:
    """
    Extract the author information from a forwarded message.
    
    Args:
        update: The telegram Update object containing the forwarded message
        
    Returns:
        str: A formatted string containing available author information
    """
    forward_origin = update.message.forward_origin
    if forward_origin:
        if forward_origin.type == "user":
            # Regular user
            author = f"{forward_origin.sender_user.first_name}"
            if forward_origin.sender_user.last_name:
                author += f" {forward_origin.sender_user.last_name}"
            if forward_origin.sender_user.username:
                author += f" (@{forward_origin.sender_user.username})"
        elif forward_origin.type == "chat":
            # Channel or group
            author = forward_origin.chat.title
        elif forward_origin.type == "hidden_user":
            # User who chose to remain anonymous
            author = "Hidden User"
        else:
            author = "Unknown sender"
    else:
        author = None
    return author


# Command handlers
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if get_user(user_id) or user_id == ADMIN_TELEGRAM_ID:
        # Start a new session
        start_new_session(user_id)
        await update.message.reply_text(
            get_bot_message(user_id, START_TOKEN)
        )
    else:
        await update.message.reply_text(
            get_bot_message(user_id, UNAUTHORIZED_TOKEN)
        )


async def add_user_command(update: Update, context: CallbackContext):
    """
    Handle /add_user command to add new authorized users to the bot.

    Can only be executed by the admin user (specified by ADMIN_TELEGRAM_ID).
    Takes a single argument - the Telegram user ID to authorize.

    Args:
        update (Update): The Telegram update containing the command
        context (CallbackContext): The context object containing command arguments

    Example:
        /add_user 123456789
    """
    user_id = update.effective_user.id
    if user_id == ADMIN_TELEGRAM_ID:
        try:
            new_user_id = int(context.args[0])
            add_user(new_user_id)
            await update.message.reply_text(get_bot_message(user_id, ADD_USER_TOKEN))
        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /add_user <user_id>")
    else:
        await update.message.reply_text("You are not authorized to add users.")


async def reset_context(update: Update, context: CallbackContext):
    """
    Handle /next command to preserve and reset the current conversation context.

    Saves the current conversation session and starts a new one, letting the user
    begin a fresh conversation while maintaining history. Only works for authorized users.

    Args:
        update (Update): The Telegram update containing the command
        context (CallbackContext): The context for the command handler

    Note:
        The old session is closed but preserved in history before starting
        a new session. Unlike /forget, this command retains the conversation history.
    """
    user_id = update.effective_user.id
    if get_user(user_id):
        close_session(user_id)
        # Start a new session
        start_new_session(user_id)
        await update.message.reply_text(get_bot_message(user_id, NEXT_TOKEN))
    else:
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))


async def forget_context(update: Update, context: CallbackContext):
    """
    Handle /forget command to completely clear the conversation history and start fresh.

    Deletes all conversation history for the user and starts a new session.
    Only works for authorized users. Unlike /next, this command removes all
    previous context rather than preserving it.

    Args:
        update (Update): The Telegram update containing the command
        context (CallbackContext): The context for the command handler

    Note:
        This command permanently deletes the user's conversation history.
        For preserving history while starting a new conversation, use /next instead.
    """
    user_id = update.effective_user.id
    if get_user(user_id):
        clear_session(user_id)
        # Start a new session
        start_new_session(user_id)
        await update.message.reply_text(get_bot_message(user_id, FORGET_TOKEN))
    else:
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))


# handle voice messages
async def handle_voice(update: Update, context: CallbackContext):
    """
    Process voice messages sent to the bot, handling both direct and forwarded messages.

    For direct voice messages:
    - Downloads and transcribes the audio using Whisper API
    - Cleans the transcript from speech artifacts
    - Processes the cleaned text through the bot's conversation flow

    For forwarded voice messages:
    - Transcribes the audio and attributes it to the original sender
    - Saves the attributed transcript to the conversation history
    - Displays the transcript without further processing

    Args:
        update (Update): The Telegram update containing the voice message
        context (CallbackContext): The context for handling the message

    Note:
        - Requires user authorization
        - Temporary files are automatically cleaned up after transcription
        - Progress and error messages maintain the bot's personality
        - For forwarded messages, preserves the original speaker's attribution
    """
    
    user_id = update.effective_user.id
    
    if not get_user(user_id):
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))
        return

    is_forwarded = update.message.forward_origin is not None
    
    await update.message.reply_text(voice_handler.get_progress_message())

    audio_fd = await voice_handler.download_voice_message(update.message.voice, context)
    if not audio_fd:
        await update.message.reply_text(voice_handler.get_error_message())
        return

    transcript = await voice_handler.transcribe_audio(audio_fd)
    if transcript is None:
        await update.message.reply_text(voice_handler.get_transcription_error_message())
        return

    if is_forwarded:
        author = get_forwarded_message_author(update)
        session_context = SessionContext(user_id)
        session_context.save_message("assistant", f"{author} сказал:\n\n{transcript}")
        await update.message.reply_text(voice_handler.get_forwarded_message(author, transcript))
    else:
        cleaned_transcript = clean_transcript(transcript)
        await update.message.reply_text(f"Вот, что я услышал:\n{transcript}")
        await handle_message(update, context, override_text=cleaned_transcript)

# Message handler
async def handle_message(update: Update, context: CallbackContext, override_text: str = None):
    """
    Process text messages and generate responses using the OpenAI chat API.

    Manages the conversation flow by:
    - Verifying user authorization
    - Maintaining conversation context and history
    - Summarizing long conversations when needed
    - Adding relevant context from embeddings
    - Generating and sending AI responses

    Args:
        update (Update): The Telegram update containing the message
        context (CallbackContext): The context for handling the message
        override_text (str, optional): Text to process instead of the update's message text.
            Used for processing cleaned voice transcripts or other modified inputs.

    Notes:
        - Uses SessionContext to manage conversation state and history
        - Automatically splits long responses to comply with Telegram's message length limits
        - Updates token usage statistics for the user
        - Handles API errors gracefully with user-friendly messages

    Raises:
        Logs but doesn't raise OpenAI API errors, sending an error message to the user instead
    """
    user_id = update.effective_user.id

    # Check if the user is authorized
    if not get_user(user_id):
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))
        return

    # Use override_text if provided, otherwise use the original message text
    user_message = override_text if override_text is not None else update.message.text

    # Initialize session context
    session_context = SessionContext(user_id)

    # Summarize session if needed
    session_context.summarize_if_needed()

    # Add relevant information based on embeddings
    session_context.add_relevant_information(user_message)

    # Save user's message
    session_context.save_message("user", user_message)

    # OpenAI API call
    try:
        response = openai.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            messages=session_context.messages,
        )
        assistant_message = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        update_tokens(user_id, tokens_used)
        # Save assistant's message
        session_context.save_message("assistant", assistant_message)

        # Split the assistant's message if necessary and send via Telegram
        messages_to_send = split_text(assistant_message, MAX_TELEGRAM_MESSAGE_LENGTH)
        for msg in messages_to_send:
            await update.message.reply_text(msg)
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        await update.message.reply_text(get_bot_message(user_id, ERROR_TOKEN))



def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("next", reset_context))
    application.add_handler(CommandHandler("forget", forget_context))
    application.add_handler(CommandHandler("add_user", add_user_command))

    # Add voice message handler
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
