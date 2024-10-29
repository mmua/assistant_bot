import os
import json
import sqlite3
import logging
import datetime
import openai
import numpy as np
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

from bot.llm import cosine_similarity, split_text, DEFAULT_OPENAI_MODEL
from bot.session import DEFAULT_CONTEXT_TOKENS, SessionContext
from bot.bot_messages import START_TOKEN, FORGET_TOKEN, NEXT_TOKEN, ERROR_TOKEN, ADD_USER_TOKEN, UNAUTHORIZED_TOKEN, get_bot_message
from bot.database import add_user, clear_session, close_session, get_user, get_user_messages, start_new_session, update_tokens

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

def get_relevant_messages(user_id, user_input_embedding, top_n=5, threshold=0.7):
    rows = get_user_messages(user_id)
    relevant_messages = []
    for content, embedding_json in rows:
        embedding = json.loads(embedding_json)
        similarity = cosine_similarity(user_input_embedding, embedding)
        if similarity >= threshold:
            relevant_messages.append((similarity, content))
    relevant_messages.sort(reverse=True)
    return [content for _, content in relevant_messages[:top_n]]

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

MAX_TELEGRAM_MESSAGE_LENGTH = 4096

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY


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


# Message handler
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    # Check if the user is authorized
    if not get_user(user_id):
        await update.message.reply_text(get_bot_message(user_id, UNAUTHORIZED_TOKEN))
        return

    user_message = update.message.text

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
        response = openai.ChatCompletion.create(
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
