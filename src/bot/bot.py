import os
import json
import sqlite3
import logging
import datetime
import openai
import numpy as np
import tiktoken
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

from .llm import get_embedding

from .bot_messages import START_TOKEN, FORGET_TOKEN, NEXT_TOKEN, ERROR_TOKEN, ADD_USER_TOKEN, UNAUTHORIZED_TOKEN, get_bot_message
from .database import add_user, clear_session, close_session, get_current_session_id, get_current_session_messages, get_user, get_user_messages, save_session_message, start_new_session, update_tokens

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Load environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_SUMMARY_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_CONTEXT_TOKENS = 2000

# Initialize OpenAI API
openai.api_key = OPENAI_API_KEY


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_relevant_messages(user_id, user_input_embedding, top_n=5):
    rows = get_user_messages(user_id)
    relevant_messages = []
    for content, embedding_json in rows:
        embedding = json.loads(embedding_json)
        similarity = cosine_similarity(user_input_embedding, embedding)
        relevant_messages.append((similarity, content))
    relevant_messages.sort(reverse=True)
    return [content for _, content in relevant_messages[:top_n]]


def num_tokens_from_messages(messages, model=DEFAULT_OPENAI_MODEL):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value[1]))
            if key[0] == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens


def summarize_session(messages):
    try:
        logging.debug("summarize session")
        summary_prompt = [
            {
                "role": "system",
                "content": "Please summarize the following conversation briefly, focusing on the key points.",
            },
            {
                "role": "user",
                "content": "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in messages]
                ),
            },
        ]
        response = openai.chat.completions.create(
            model=DEFAULT_SUMMARY_OPENAI_MODEL,
            messages=summary_prompt,
            max_tokens=DEFAULT_CONTEXT_TOKENS,
        )
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return ""


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
    if get_user(user_id):
        user_message = update.message.text

        # Get current session id
        session_id = get_current_session_id(user_id)

        # Save user message
        save_session_message(user_id, session_id, "user", user_message)

        # Get current session messages
        messages = get_current_session_messages(user_id)

        # Calculate token count
        total_tokens = num_tokens_from_messages(messages)
        if total_tokens > DEFAULT_CONTEXT_TOKENS:
            # Summarize session
            session_summary = summarize_session(messages)
            messages = [
                {"role": "system", "content": "Summary of previous conversation: " + session_summary}
            ]

        # Compute embedding of user's input
        user_input_embedding_json = get_embedding(user_message)
        if user_input_embedding_json:
            user_input_embedding = json.loads(user_input_embedding_json)
            # Retrieve relevant messages from past sessions
            relevant_contents = get_relevant_messages(user_id, user_input_embedding)
            # Include relevant messages in context
            for content in relevant_contents:
                messages.append({"role": "system", "content": "Relevant information: " + content})

        # Append user's current message
        messages.append({"role": "user", "content": user_message})

        # OpenAI API call
        try:
            response = openai.chat.completions.create(
                model=DEFAULT_OPENAI_MODEL,
                messages=messages,
            )
            assistant_message = response.choices[0].message.content
            tokens_used = response["usage"]["total_tokens"]
            update_tokens(user_id, tokens_used)
            save_session_message(user_id, session_id, "assistant", assistant_message)
            update.message.reply_text(assistant_message)
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            await update.message.reply_text(
                "Sorry, I'm having trouble accessing my AI brain right now."
            )
    else:
        await update.message.reply_text("You are not authorized to use this bot.")


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
