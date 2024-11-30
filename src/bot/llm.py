import json
import logging
import numpy as np
import openai
import tiktoken

DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_OPENAI_MINI_MODEL = "gpt-4o-mini"


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_embedding(text):
    try:
        embedding = openai.embeddings.create(
            input=[text], model="text-embedding-3-small"
        ).data[0].embedding
        return json.dumps(embedding)
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        return None


async def clean_transcript(text: str, model="DEFAULT_OPENAI_MINI_MODEL") -> str:
    """Clean transcript from common spoken artifacts."""
    try:
        response = await openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Clean the following text from common spoken artifacts (um, uh, like, you know, etc) and correct any grammar without changing the meaning. Keep the cleaned text natural and conversational. Keep the language original."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error cleaning transcript: {e}")
        return text


def split_text(text, max_length=4096):
    # Split the text into paragraphs using newlines
    paragraphs = text.split('\n')
    
    chunks = []
    current_chunk = ''
    
    for paragraph in paragraphs:
        # Add the paragraph and a newline back to the current_chunk
        # Ensure we don't add an extra newline at the end
        new_chunk = (paragraph + '\n') if paragraph != paragraphs[-1] else paragraph
        
        # Check if adding the new paragraph exceeds max_length
        if len(current_chunk) + len(new_chunk) > max_length:
            # I assume both paragraphs fit within limit
            chunks.append(current_chunk.rstrip('\n'))
            current_chunk = new_chunk
        else:
            current_chunk += new_chunk
    
    # Add any remaining text to chunks
    if current_chunk:
        chunks.append(current_chunk.rstrip('\n'))
    
    return chunks


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
