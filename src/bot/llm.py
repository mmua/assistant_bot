import json
import logging
import openai

def get_embedding(text):
    try:
        embedding = openai.embeddings.create(
            input=[text], model="text-embedding-3-small"
        ).data[0].embedding
        return json.dumps(embedding)
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        return None

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