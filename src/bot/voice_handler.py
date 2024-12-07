import logging
import random
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional
from telegram import Voice
from telegram.ext import CallbackContext
from salute_speech.speech_recognition import SaluteSpeechClient

class VoiceHandler:
    def __init__(self, sber_speech_api_key: str):
        self.salute = SaluteSpeechClient(client_credentials=sber_speech_api_key)

    async def download_voice_message(self, voice: Voice, context: CallbackContext) -> Optional[BinaryIO]:
        """Download voice message and convert it to mp3."""
        try:
            voice_file = await context.bot.get_file(voice.file_id)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                oga_path = temp_dir_path / f"{voice.file_id}.oga"
                
                await voice_file.download_to_drive(oga_path)
            
                return open(oga_path, "rb")
                
        except Exception as e:
            logging.error(f"Error downloading voice message: {e}")
            return None

    async def transcribe_audio(self, audio_file: BinaryIO) -> Optional[str]:
        """Transcribe audio file using Salute Speech API."""
        try:
            transcript = await self.salute.audio.transcriptions.create(
                file=audio_file,
                model="general",
                language="ru-RU",
                response_format="text"
            )
            return transcript.text
        except Exception as e:
            logging.error(f"Error transcribing audio: {e}")
            return None
        finally:
            if audio_file:
                audio_file.close()

    def get_progress_message(self) -> str:
        """Return random progress message."""
        return random.choice([
            "Ah, a voice carried by the winter winds! Let me decode its message...",
            "The frost crystallizes your words. Give me but a moment to interpret them...",
            "I hear your call through the snowstorm. Allow me to translate it...",
        ])

    def get_error_message(self) -> str:
        """Return random error message."""
        return random.choice([
            "Alas! The winter winds have scattered your message to the four corners. Might you try again?",
            "Oh dear, the frost has claimed your words before I could grasp them. Another attempt, perhaps?",
            "My frozen friend, your message was lost in the blizzard. Would you share it once more?",
        ])

    def get_transcription_error_message(self) -> str:
        """Return random transcription error message."""
        return random.choice([
            "By the frozen winds! Your message remains enigmatic to my ears. Might you try again?",
            "The bitter cold has obscured your words from my understanding. Perhaps another attempt?",
            "Even my winter magic couldn't unveil your message this time. Would you grace me with another try?",
        ])

    def get_forwarded_message(self, author: str, transcript: str) -> str:
        """Return random forwarded message format."""
        return random.choice([
            f"Ah! Through the frost, I hear {author}'s words:\n{transcript}",
            f"The winter winds carry {author}'s message:\n{transcript}",
            f"From the frozen depths, {author} speaks:\n{transcript}",
        ])
