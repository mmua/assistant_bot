import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch
import json
import base64
from io import BytesIO
from PIL import Image
from telegram import PhotoSize
from telegram.ext import CallbackContext

from bot.photo_handler import PhotoHandler

# Constants for testing
TEST_OPENAI_KEY = "test-openai-key"
TEST_YANDEX_KEY = "test-yandex-key"
TEST_FOLDER_ID = "test-folder-id"
TEST_PHOTO_ID = "test-photo-123"

@pytest.fixture(scope="session")
def sample_image_bytes() -> bytes:
    """Create a sample image once for the entire test session."""
    img = Image.new('RGB', (100, 100), color='white')
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

@pytest.fixture
def sample_image(sample_image_bytes) -> BytesIO:
    """Provide a fresh BytesIO for each test."""
    return BytesIO(sample_image_bytes)

@pytest.fixture
def mock_telegram_photo() -> PhotoSize:
    """Create a mock Telegram PhotoSize object."""
    return PhotoSize(
        file_id=TEST_PHOTO_ID,
        file_unique_id="unique-" + TEST_PHOTO_ID,
        width=100,
        height=100,
        file_size=1024
    )

@pytest.fixture
def mock_context() -> CallbackContext:
    """Create a mock Telegram context with async methods."""
    context = Mock(spec=CallbackContext)
    context.bot = Mock()
    context.bot.get_file = AsyncMock()
    return context

@pytest.fixture
def handler() -> PhotoHandler:
    """Create a PhotoHandler instance with test credentials."""
    return PhotoHandler(
        openai_api_key=TEST_OPENAI_KEY,
        yandex_api_key=TEST_YANDEX_KEY,
        yandex_folder_id=TEST_FOLDER_ID
    )

@pytest.fixture
def mock_ocr_response() -> dict:
    """Sample OCR response fixture."""
    return {
        "result": {
            "text_annotation": {
                "width": "100",
                "height": "100",
                "blocks": [
                    {
                        "lines": [
                            {
                                "alternatives": [
                                    {
                                        "text": "Hello",
                                        "words": [{"text": "Hello"}]
                                    }
                                ]
                            },
                            {
                                "alternatives": [
                                    {
                                        "text": "World",
                                        "words": [{"text": "World"}]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
    }

class TestPhotoHandlerDownload:
    """Tests for photo downloading functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_download(self, handler, mock_telegram_photo, mock_context, sample_image_bytes):
        # Arrange
        async def fake_download(path):
            """Simulate file download by actually creating the file."""
            with open(path, 'wb') as f:
                f.write(sample_image_bytes)
        
        mock_context.bot.get_file.return_value.download_to_drive = AsyncMock(side_effect=fake_download)
        
        # Act
        result = await handler.download_photo(mock_telegram_photo, mock_context)
        
        # Assert
        assert result is not None
        mock_context.bot.get_file.assert_called_once_with(TEST_PHOTO_ID)

    @pytest.mark.asyncio
    async def test_failed_download(self, handler, mock_telegram_photo, mock_context):
        # Arrange
        mock_context.bot.get_file.side_effect = Exception("Network error")
        
        # Act
        result = await handler.download_photo(mock_telegram_photo, mock_context)
        
        # Assert
        assert result is None

class TestPhotoHandlerOCR:
    """Tests for OCR functionality."""

    def test_request_preparation(self, handler, sample_image):
        # Act
        data, headers = handler._prepare_yandex_ocr_request(sample_image)
        
        # Assert
        assert all(key in data for key in ["mimeType", "languageCodes", "content"])
        assert data["mimeType"] == "image/jpeg"
        assert isinstance(data["content"], str)
        
        assert all(key in headers for key in [
            "Content-Type",
            "Authorization",
            "x-folder-id",
            "x-data-logging-enabled"
        ])
        assert headers["Authorization"] == f"Bearer {TEST_YANDEX_KEY}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("response_data,expected_text", [
        ({"result": {"text_annotation": {"blocks": []}}}, "No text found in the image"),
        ({"result": {"text_annotation": {"blocks": [{"lines": []}]}}}, "No text found in the image"),
        ({"invalid": "format"}, "No text found in the image"),
    ])
    async def test_extract_text_edge_cases(self, handler, sample_image, response_data, expected_text):
        # Arrange
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(
                json=Mock(return_value=response_data),
                raise_for_status=Mock()
            )
            
            # Act
            result = await handler.extract_text(sample_image)
            
            # Assert
            assert result == expected_text

    @pytest.mark.asyncio
    async def test_successful_text_extraction(self, handler, sample_image, mock_ocr_response):
        # Arrange
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(
                json=Mock(return_value=mock_ocr_response),
                raise_for_status=Mock()
            )
            
            # Act
            result = await handler.extract_text(sample_image)
            
            # Assert
            assert result == "Hello\nWorld"

class TestPhotoHandlerIntentAnalysis:
    """Tests for caption intent analysis."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("caption,expected", [
        (None, ("ocr", {})),
        ("", ("ocr", {})),
    ])
    async def test_default_intent(self, handler, caption, expected):
        # Act
        result = await handler.analyze_intent(caption)
        
        # Assert
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("caption,gpt_response,expected", [
        (
            "convert to diagram",
            "{'tool': 'diagram', 'params': {'format': 'plantuml'}}",
            ("diagram", {"format": "plantuml"})
        ),
        (
            "analyze this presentation",
            "{'tool': 'presentation', 'params': {}}",
            ("presentation", {})
        ),
    ])
    async def test_specific_intents(self, handler, caption, gpt_response, expected):
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=gpt_response))]
        
        with patch.object(handler.openai_client.chat.completions, 'create', return_value=mock_response):
            # Act
            result = await handler.analyze_intent(caption)
            
            # Assert
            assert result == expected

class TestPhotoHandlerMessages:
    """Tests for user-facing messages."""

    @pytest.mark.parametrize("message_type", ["progress", "error"])
    def test_message_format(self, handler, message_type):
        # Arrange
        message_getter = getattr(handler, f"get_{message_type}_message")
        
        # Act
        message = message_getter()
        
        # Assert
        assert isinstance(message, str)
        assert len(message) > 0
        # Messages should be conversational and end with punctuation
        assert message.endswith(('.', '?', '!'))

    def test_unique_progress_messages(self, handler):
        # Get multiple messages and check they're not all the same
        messages = {handler.get_progress_message() for _ in range(10)}
        assert len(messages) > 1  # Should have some variety

    def test_winter_theme_presence(self, handler):
        # Check that winter-themed words appear in messages
        winter_words = {"frost", "snow", "winter", "frozen"}
        message = handler.get_progress_message().lower()
        assert any(word in message for word in winter_words)

class TestImageContentPreparation:
    """Tests for image content preparation methods."""

    def test_encode_image(self, handler, sample_image):
        # Act
        result = handler._encode_image(sample_image)
        
        # Assert
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify it's valid base64
        assert base64.b64decode(result)
        
    @pytest.mark.parametrize("detail,expected_detail", [
        ("auto", "auto"),
        ("high", "high"),
        ("low", "low")
    ])
    def test_prepare_image_content(self, handler, sample_image, detail, expected_detail):
        # Act
        result = handler._prepare_image_content(sample_image, detail=detail)
        
        # Assert
        assert result["type"] == "image_url"
        assert result["image_url"]["detail"] == expected_detail
        assert result["image_url"]["url"].startswith("data:image/jpeg;base64,")
        
        # Verify file pointer is reset
        assert sample_image.tell() == 0
        
class TestProcessDiagram:
    """Tests for diagram processing functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_diagram_processing(self, handler, sample_image):
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="@startuml\nclass Test\n@enduml"))]
        
        with patch.object(handler.openai_client.chat.completions, 'create', return_value=mock_response):
            # Act
            result = await handler.process_diagram(sample_image)
            
            # Assert
            assert "@startuml" in result
            assert "@enduml" in result
            
    @pytest.mark.asyncio
    async def test_failed_diagram_processing(self, handler, sample_image):
        # Arrange
        with patch.object(handler.openai_client.chat.completions, 'create', side_effect=Exception("API Error")):
            # Act
            result = await handler.process_diagram(sample_image)
            
            # Assert
            assert "Error" in result

class TestPresentationAnalysis:
    """Tests for presentation slide analysis."""
    
    @pytest.mark.asyncio
    async def test_successful_presentation_analysis(self, handler, sample_image):
        # Arrange
        expected_analysis = "The slide contains a title and three bullet points..."
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=expected_analysis))]
        
        with patch.object(handler.openai_client.chat.completions, 'create', return_value=mock_response):
            # Act
            result = await handler.analyze_presentation(sample_image)
            
            # Assert
            assert result == expected_analysis
            
    @pytest.mark.asyncio
    async def test_failed_presentation_analysis(self, handler, sample_image):
        # Arrange
        with patch.object(handler.openai_client.chat.completions, 'create', side_effect=Exception("API Error")):
            # Act
            result = await handler.analyze_presentation(sample_image)
            
            # Assert
            assert "Error" in result

class TestImageAnalysis:
    """Tests for general image analysis."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("params,expected_detail", [
        (None, "auto"),
        ({}, "auto"),
        ({"detail": "high"}, "high"),
        ({"detail": "low"}, "low"),
    ])
    async def test_image_analysis_detail_levels(self, handler, sample_image, params, expected_detail):
        # Arrange
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Image analysis result"))]
        
        with patch.object(handler.openai_client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_response
            
            # Act
            await handler.analyze_image(sample_image, params)
            
            # Assert
            args = mock_create.call_args[1]
            content = args["messages"][1]["content"][1]["image_url"]["detail"]
            assert content == expected_detail
            
    @pytest.mark.asyncio
    async def test_successful_image_analysis(self, handler, sample_image):
        # Arrange
        expected_analysis = "The image shows a white background..."
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=expected_analysis))]
        
        with patch.object(handler.openai_client.chat.completions, 'create', return_value=mock_response):
            # Act
            result = await handler.analyze_image(sample_image)
            
            # Assert
            assert result == expected_analysis
            
    @pytest.mark.asyncio
    async def test_failed_image_analysis(self, handler, sample_image):
        # Arrange
        with patch.object(handler.openai_client.chat.completions, 'create', side_effect=Exception("API Error")):
            # Act
            result = await handler.analyze_image(sample_image)
            
            # Assert
            assert "Error" in result

class TestPhotoProcessing:
    """Tests for the main photo processing pipeline."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("caption,tool,expected_result", [
        (None, "ocr", "Hello\nWorld"),
        ("convert to diagram", "diagram", "@startuml\nclass Test\n@enduml"),
        ("analyze slide", "presentation", "Slide analysis"),
        ("what's in this image", "analyze", "Image description"),
    ])
    async def test_process_photo_pipeline(self, handler, sample_image, caption, tool, expected_result):
        # Arrange
        mock_intent_response = Mock()
        mock_intent_response.choices = [Mock(message=Mock(content=f"{{'tool': '{tool}', 'params': {{}}}}"))]
        
        mock_processing_response = Mock()
        mock_processing_response.choices = [Mock(message=Mock(content=expected_result))]
        
        # Mock for Yandex OCR
        mock_ocr_response = {
            "result": {
                "text_annotation": {
                    "blocks": [{
                        "lines": [{
                            "alternatives": [{
                                "text": "Hello"
                            }]
                        }, {
                            "alternatives": [{
                                "text": "World"
                            }]
                        }]
                    }]
                }
            }
        }
        
        with patch.object(handler.openai_client.chat.completions, 'create', side_effect=[mock_intent_response, mock_processing_response]), \
             patch('requests.post') as mock_post:
            
            mock_post.return_value = Mock(
                json=Mock(return_value=mock_ocr_response),
                raise_for_status=Mock()
            )
            
            # Act
            result = await handler.process_photo(sample_image, caption)
            
            # Assert
            assert result == expected_result
            
    @pytest.mark.asyncio
    async def test_process_photo_with_intent_error(self, handler, sample_image):
        # Arrange
        with patch.object(handler.openai_client.chat.completions, 'create', side_effect=Exception("API Error")):
            # Act
            result = await handler.process_photo(sample_image, "invalid caption")
            
            # Assert
            assert any(err in result for err in ["Error", "Alas", "Oh dear"])