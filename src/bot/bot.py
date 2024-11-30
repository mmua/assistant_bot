import os
import logging
import random
import openai
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional
from pydub import AudioSegment

from telegram import Update, Voice
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

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

MAX_TELEGRAM_MESSAGE_LENGTH = 4096

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY


async def download_voice_message(voice: Voice, context: CallbackContext) -> Optional[str]:
    """Download voice message and convert it to mp3."""
    try:
        voice_file = await context.bot.get_file(voice.file_id)
        
        # Create a temporary directory that will be automatically cleaned up
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create temp files inside the temporary directory
            temp_dir_path = Path(temp_dir)
            oga_path = temp_dir_path / f"{voice.file_id}.oga"
            mp3_path = temp_dir_path / f"{voice.file_id}.mp3"
            
            # Download the voice file
            await voice_file.download_to_drive(oga_path)
            
            # Convert to mp3 using pydub
            audio = AudioSegment.from_ogg(str(oga_path))
            audio.export(str(mp3_path), format="mp3")
            
            # Return the MP3 file handle
            return open(mp3_path, "rb")
            
    except Exception as e:
        logging.error(f"Error downloading voice message: {e}")
        return None

async def transcribe_audio(audio_file: BinaryIO) -> Optional[str]:
    """Transcribe audio file using OpenAI Whisper."""
    try:
        transcript = await openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ru"
        )
        return transcript.text
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
        return None
    finally:
        # Clean up the temporary file
        if audio_file:
            audio_file.close()


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
    user_id = update.effective_user.id
    if get_user(user_id):
        close_session(user_id)
        # Start a new session
        start_new_session(user_id)
        await update.message.reply_text(get_bot_message(user_id, NEXT_TOKEN))
    else:
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))


async def forget_context(update: Update, context: CallbackContext):
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
    """Handle voice messages."""
    user_id = update.effective_user.id
    
    if not get_user(user_id):
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))
        return

    is_forwarded = update.message.forward_origin is not None
    
    # Send initial acknowledgment
    await update.message.reply_text(random.choice([
        "Ah, a voice carried by the winter winds! Let me decode its message...",
        "The frost crystallizes your words. Give me but a moment to interpret them...",
        "I hear your call through the snowstorm. Allow me to translate it...",
    ]))

    # Download and process the voice message
    audio_fd = await download_voice_message(update.message.voice, context)
    if not audio_fd:
        await update.message.reply_text(random.choice([
            "Alas! The winter winds have scattered your message to the four corners. Might you try again?",
            "Oh dear, the frost has claimed your words before I could grasp them. Another attempt, perhaps?",
            "My frozen friend, your message was lost in the blizzard. Would you share it once more?",
        ]))
        return

    # Transcribe the audio
    transcript = await transcribe_audio(audio_fd)  # This will also clean up the temp file
    if not transcript:
        await update.message.reply_text(random.choice([
            "By the frozen winds! Your message remains enigmatic to my ears. Might you try again?",
            "The bitter cold has obscured your words from my understanding. Perhaps another attempt?",
            "Even my winter magic couldn't unveil your message this time. Would you grace me with another try?",
        ]))
        return

    if is_forwarded:
        author = get_forwarded_message_author(update)
        await update.message.reply_text(random.choice([
            f"Ah! Through the frost, I hear {author}'s words:\n{transcript}",
            f"The winter winds carry {author}'s message:\n{transcript}",
            f"From the frozen depths, {author} speaks:\n{transcript}",
        ]))
    else:
        cleaned_transcript = await clean_transcript(transcript)
        await update.message.reply_text(f"Transcript:\n{transcript}")
        await handle_message(update, context, override_text=cleaned_transcript)


# Message handler
async def handle_message(update: Update, context: CallbackContext, override_text: str = None):
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
