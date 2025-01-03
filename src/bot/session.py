import json
import logging

import openai
from bot.database.database import (
    get_current_session_id, get_session_messages,
    get_user_messages, save_session_message
)
from bot.llm import num_tokens_from_messages, cosine_similarity


DEFINE_MIN_CONTEXT_LENGTH = 300
DEFAULT_CONTEXT_TOKENS = 20000
DEFAULT_OUTPUT_TOKENS = 2000
DEFAULT_SUMMARY_OPENAI_MODEL = "gpt-4o-mini"


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
            max_completion_tokens=DEFAULT_OUTPUT_TOKENS,
        )
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return ""


class SessionContext:
    def __init__(self, user_id):
        self.user_id = user_id
        self.session_id = get_current_session_id(user_id)
        self.messages = self.load_messages()

    def load_messages(self):
        # Get current session messages
        return get_session_messages(self.session_id)

    def save_message(self, role, content):
        logging.debug("save message: role: %s, content: %s", role, content)
        # Save message to the database
        save_session_message(self.user_id, self.session_id, role, content)
        # Append message to the session messages
        self.messages.append({"role": role, "content": content})

    def calculate_total_tokens(self):
        return num_tokens_from_messages(self.messages)

    def summarize_if_needed(self):
        total_tokens = self.calculate_total_tokens()
        if total_tokens > DEFAULT_CONTEXT_TOKENS:
            # Summarize session
            session_summary = summarize_session(self.messages)
            self.messages = [
                {
                    "role": "system",
                    "content": "Summary of previous conversation: " + session_summary,
                }
            ]

    def add_relevant_information(self, user_message, min_context_len=DEFINE_MIN_CONTEXT_LENGTH):
        from bot.llm import get_embedding
        # ignore too short messages
        if len(user_message) < min_context_len:
            return

        # Compute embedding of user's input
        user_input_embedding_json = get_embedding(user_message)
        if user_input_embedding_json:
            user_input_embedding = json.loads(user_input_embedding_json)
            # Retrieve relevant messages from past sessions
            relevant_contents = get_relevant_messages(self.user_id, user_input_embedding)
            # Include relevant messages in context
            for content in relevant_contents:
                self.messages.append({"role": "system", "content": "Relevant information: " + content})
