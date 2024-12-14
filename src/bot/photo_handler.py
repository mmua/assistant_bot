import json
import logging
import os
import random
import tempfile
import base64
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional, Tuple

import requests
from PIL import Image
from telegram import PhotoSize
from telegram.ext import CallbackContext
import openai

class PhotoHandler:
    """Handler for processing photos with various AI capabilities."""

    def __init__(self, openai_api_key: str, yandex_api_key: str, yandex_folder_id: str):
        """
        Initialize PhotoHandler with necessary API keys and models.
        
        Args:
            openai_api_key: OpenAI API key for GPT-4V and analysis
            yandex_api_key: Yandex Cloud API key
            yandex_folder_id: Yandex Cloud folder ID
        """
        self.openai = openai
        self.openai.api_key = openai_api_key
        self.yandex_api_key = yandex_api_key
        self.yandex_folder_id = yandex_folder_id
        self.yandex_ocr_url = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"

    async def download_photo(self, photo: PhotoSize, context: CallbackContext) -> Optional[BinaryIO]:
        """Download photo and return it as a file-like object."""
        try:
            photo_file = await context.bot.get_file(photo.file_id)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                assert os.path.exists(temp_dir_path)
                photo_path = temp_dir_path / f"{photo.file_id}.jpg"
                
                await photo_file.download_to_drive(photo_path)
                assert os.path.exists(photo_path)
                return open(photo_path, "rb")
                
        except Exception as e:
            logging.exception(f"Error downloading photo: {e}")
            return None

    async def analyze_intent(self, caption: Optional[str]) -> Tuple[str, dict]:
        """Analyze caption to determine processing intent."""
        if not caption:
            return "ocr", {}

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """Analyze the image caption and determine the processing intent.
                    Return a JSON object with two fields:
                    - tool: "ocr" | "diagram" | "presentation" | "analyze"
                    - params: additional parameters for processing"""},
                    {"role": "user", "content": caption}
                ]
            )
            result = response.choices[0].message.content
            logging.error(f"{result}")
            intent = eval(result)  # Safe as we control the input
            return intent["tool"], intent.get("params", {})
        except Exception as e:
            logging.error(f"Error analyzing intent: {e}")
            return "ocr", {}

    async def process_photo(self, photo_file: BinaryIO, caption: Optional[str] = None) -> str:
        """Process photo based on caption intent."""
        try:
            tool, params = await self.analyze_intent(caption)
            
            processors = {
                "ocr": self.extract_text,
                "diagram": self.process_diagram,
                "presentation": self.analyze_presentation,
                "analyze": self.analyze_image
            }
            
            processor = processors.get(tool, self.extract_text)
            return await processor(photo_file, params)
            
        except Exception as e:
            logging.error(f"Error processing photo: {e}")
            return self.get_error_message()

    def _prepare_yandex_ocr_request(self, photo_file: BinaryIO) -> Tuple[dict, dict]:
        """Prepare request body and headers for Yandex OCR API."""
        # Read and encode image
        image_content = photo_file.read()
        encoded_image = base64.b64encode(image_content).decode('utf-8')
        
        data = {
            "mimeType": "image/jpeg",
            "languageCodes": ["*"],
            "content": encoded_image
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.yandex_api_key}",
            "x-folder-id": self.yandex_folder_id,
            "x-data-logging-enabled": "true"
        }
        
        return data, headers

    async def extract_text(self, photo_file: BinaryIO, params: dict = None) -> str:
        """Extract text from photo using Yandex OCR API."""
        try:
            data, headers = self._prepare_yandex_ocr_request(photo_file)
            
            response = requests.post(
                self.yandex_ocr_url,
                headers=headers,
                data=json.dumps(data)
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract text from response
            try:
                blocks = result['result']['text_annotation']['blocks']
                extracted_text = []
                
                for block in blocks:
                    for line in block.get('lines', []):
                        # Get the first (best) alternative
                        if line.get('alternatives'):
                            line_text = line['alternatives'][0]['text']
                            extracted_text.append(line_text)
                
                text = '\n'.join(extracted_text)
                return text if text else "No text found in the image"
            except (KeyError, IndexError) as e:
                logging.error(f"Error parsing Yandex OCR response: {e}")
                return "No text found in the image"
                
        except Exception as e:
            logging.error(f"OCR error: {e}")
            return "Error extracting text from image"

    async def process_diagram(self, photo_file: BinaryIO, params: dict = None) -> str:
        """Convert diagram to specified format (e.g., PlantUML)."""
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Convert the diagram to PlantUML notation."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": photo_file},
                            {"type": "text", "text": "Convert this diagram"}
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Diagram processing error: {e}")
            return "Error converting diagram"

    async def analyze_presentation(self, photo_file: BinaryIO, params: dict = None) -> str:
        """Analyze presentation slide content."""
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze this presentation slide content."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": photo_file},
                            {"type": "text", "text": "What's on this slide?"}
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Presentation analysis error: {e}")
            return "Error analyzing presentation"

    async def analyze_image(self, photo_file: BinaryIO, params: dict = None) -> str:
        """Perform general image analysis."""
        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze this image and describe what you see."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": photo_file},
                            {"type": "text", "text": "What's in this image?"}
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Image analysis error: {e}")
            return "Error analyzing image"

    def get_progress_message(self) -> str:
        """Return random progress message."""
        return random.choice([
            "Ah, an image materializes from the frost! Let me examine it...",
            "The winter's light reveals your image. Give me a moment to perceive it...",
            "I see your vision through the snowflakes. Allow me to interpret it...",
        ])

    def get_error_message(self) -> str:
        """Return random error message."""
        return random.choice([
            "Alas! The snow has obscured this image. Might you try again?",
            "Oh dear, the frost has clouded my vision. Another attempt, perhaps?",
            "My frozen friend, this image eludes my understanding. Would you share it once more?",
        ])