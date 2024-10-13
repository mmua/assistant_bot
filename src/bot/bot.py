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
    Updater,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

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

# Database setup
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/bot.db")
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
cursor = conn.cursor()

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
    return messages


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


def get_embedding(text):
    try:
        embedding = openai.embeddings.create(
            input=[text], model="text-embedding-3-small"
        ).data[0].embedding
        return json.dumps(embedding)
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        return None


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_relevant_messages(user_id, user_input_embedding, top_n=5):
    cursor.execute(
        """
    SELECT content, embedding FROM messages
    WHERE user_id = ? AND embedding IS NOT NULL
    """,
        (user_id,),
    )
    rows = cursor.fetchall()
    relevant_messages = []
    for content, embedding_json in rows:
        embedding = json.loads(embedding_json)
        similarity = cosine_similarity(user_input_embedding, embedding)
        relevant_messages.append((similarity, content))
    relevant_messages.sort(reverse=True)
    return [content for similarity, content in relevant_messages[:top_n]]


def num_tokens_from_messages(messages, model=DEFAULT_OPENAI_MODEL):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens


def summarize_session(messages):
    try:
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
        summary = response["choices"][0]["message"]["content"]
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return ""


# Command handlers
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if get_user(user_id) or user_id == ADMIN_TELEGRAM_ID:
        # Start a new session
        start_new_session(user_id)
        update.message.reply_text(
            "Hello! I'm your GPT-4 assistant. How can I help you today?"
        )
    else:
        update.message.reply_text(
            "You are not authorized to use this bot. Please contact the administrator."
        )


def add_user_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id == ADMIN_TELEGRAM_ID:
        try:
            new_user_id = int(context.args[0])
            add_user(new_user_id)
            update.message.reply_text(f"User {new_user_id} has been added successfully.")
        except (IndexError, ValueError):
            update.message.reply_text("Usage: /add_user <user_id>")
    else:
        update.message.reply_text("You are not authorized to add users.")


def reset_context(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if get_user(user_id):
        cursor.execute(
            "UPDATE sessions SET end_date = ? WHERE user_id = ? AND end_date IS NULL",
            (datetime.date.today(), user_id),
        )
        conn.commit()
        # Start a new session
        start_new_session(user_id)
        update.message.reply_text("Context reset. Starting a new session.")
    else:
        update.message.reply_text("You are not authorized to use this bot.")


def forget_context(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if get_user(user_id):
        clear_session(user_id)
        # Start a new session
        start_new_session(user_id)
        update.message.reply_text("All your session history has been cleared.")
    else:
        update.message.reply_text("You are not authorized to use this bot.")


# Message handler
def handle_message(update: Update, context: CallbackContext):
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
            assistant_message = response["choices"][0]["message"]["content"]
            tokens_used = response["usage"]["total_tokens"]
            update_tokens(user_id, tokens_used)
            save_session_message(user_id, session_id, "assistant", assistant_message)
            update.message.reply_text(assistant_message)
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            update.message.reply_text(
                "Sorry, I'm having trouble accessing my AI brain right now."
            )
    else:
        update.message.reply_text("You are not authorized to use this bot.")


def main():
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("reset_context", reset_context))
    dispatcher.add_handler(CommandHandler("forget_context", forget_context))
    dispatcher.add_handler(CommandHandler("add_user", add_user_command))
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
