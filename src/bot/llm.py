import json
import logging
import openai
import textwrap

def get_embedding(text):
    try:
        embedding = openai.embeddings.create(
            input=[text], model="text-embedding-3-small"
        ).data[0].embedding
        return json.dumps(embedding)
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        return None

def split_text(text, max_length):
    import re

    # Split the text into sentences using regex
    sentence_endings = re.compile(r'(?<=[.!?]) +')
    sentences = sentence_endings.split(text)

    chunks = []
    current_chunk = ''

    for sentence in sentences:
        # Ensure the sentence ends with proper punctuation and whitespace
        if not re.match(r'.*[.!?]$', sentence):
            sentence += '.'

        # Check if adding the sentence would exceed the max_length
        if len(current_chunk) + len(sentence) + 1 > max_length:
            # Wrap the current_chunk using textwrap to handle any long sentences
            wrapped_chunk = '\n'.join(textwrap.wrap(current_chunk.strip(), width=80))
            chunks.append(wrapped_chunk)
            current_chunk = sentence
        else:
            current_chunk += ' ' + sentence

    # Add the last chunk
    if current_chunk:
        wrapped_chunk = '\n'.join(textwrap.wrap(current_chunk.strip(), width=80))
        chunks.append(wrapped_chunk)

    return chunks
