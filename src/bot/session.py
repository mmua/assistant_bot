import json
import logging

import openai
from bot.bot import get_relevant_messages
from bot.database import get_current_session_id, get_current_session_messages, save_session_message
from bot.llm import get_embedding, num_tokens_from_messages


DEFINE_MIN_CONTEXT_LENGTH = 300
DEFAULT_CONTEXT_TOKENS = 2000
DEFAULT_SUMMARY_OPENAI_MODEL = "gpt-4o-mini"


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


class SessionContext:
    def __init__(self, user_id):
        self.user_id = user_id
        self.session_id = get_current_session_id(user_id)
        self.messages = self.load_messages()

    def load_messages(self):
        # Get current session messages
        return get_current_session_messages(self.user_id)

    def save_message(self, role, content):
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

    def add_relevant_information(self, user_message):
        # ignore too short messages
        if len(user_message) < DEFINE_MIN_CONTEXT_LENGTH:
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
