# AI Assistant Bot

A sophisticated Telegram bot that provides intelligent conversational assistance powered by GPT-4o. Transform your Telegram experience with context-aware conversations, voice message support, image processing capabilities, and seamless multi-session management.

## Key Features

### 🧠 Intelligent Conversations
- Powered by OpenAI's GPT-4o for human-like interactions
- Context-aware responses that maintain conversation coherence
- Automatic conversation summarization to maintain meaningful long-term discussions
- Natural language understanding with semantic search

### 🎙️ Voice Interaction
- Advanced voice message processing with Salute Speech recognition
- Support for both direct and forwarded voice messages
- Automatic cleaning of speech artifacts from transcriptions
- Multi-language support (Russian and English)
- Winter-themed conversational responses

### 📸 Image Processing
- Intelligent intent detection from image captions
- OCR capabilities using Yandex OCR API
- Diagram to PlantUML conversion with GPT-4V
- Presentation slide analysis and summarization
- General image content analysis
- Support for both camera shots and uploaded images
- Multi-language OCR support

### 💡 Smart Context Management
- Intelligent session management with conversation history
- Automatic summarization of long conversations
- Semantic search across past conversations using embeddings
- Relevant context retrieval for more informed responses
- Token-aware optimization

### 🛡️ Security & Control
- User authentication system
- Admin-controlled access management
- Separate conversation sessions with /next and /forget commands
- Token usage tracking and management
- Secure file handling

## Setup Instructions

1. **Clone the repository**:
```bash
git clone https://github.com/mmua/assistant_bot.git
cd assistant_bot
```

2. **Set up environment variables**:
Create a `.env` file with the following variables:
```
TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
SBER_SPEECH_API_KEY=your_sber_speech_api_key
YANDEX_API_KEY=your_yandex_api_key
YANDEX_FOLDER_ID=your_yandex_folder_id
ADMIN_TELEGRAM_ID=your_telegram_id
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Database Setup**:
```bash
python -m bot.database.init_db
```

## Usage

### Basic Commands
- `/start` - Begin a new conversation session
- `/next` - Start a new session while preserving history
- `/forget` - Clear all history and start fresh
- `/add_user <user_id>` - (Admin only) Add new authorized users

### Voice Messages
The bot accepts voice messages and provides winter-themed responses during processing:
1. Send a voice message
2. Wait for transcription
3. Review the transcribed text
4. Get the bot's response

The bot supports both direct messages and forwarded voice messages, maintaining attribution for forwarded content.

### Image Processing
Send any image to the bot with an optional caption to process it. The bot automatically determines the best processing method based on the caption:

1. **Text Extraction**: 
   - Send an image containing text
   - Supports multiple languages
   - Preserves text layout and structure
   - Ideal for documents, screenshots, and presentations

2. **Diagram Conversion**: 
   - Send a diagram with caption like "convert to plantuml"
   - Supports various diagram types (flowcharts, UML, etc.)
   - Generates editable PlantUML code
   - Maintains diagram relationships and structure

3. **Presentation Analysis**: 
   - Send a presentation slide for content analysis
   - Extracts key points and structure
   - Provides summaries and insights
   - Identifies main themes and topics

4. **General Analysis**: 
   - Send any image for content description
   - Detailed scene understanding
   - Object identification
   - Context interpretation

The bot understands natural language captions and chooses the appropriate processing method automatically.

### Session Management
- Each conversation is managed in sessions
- Long conversations are automatically summarized
- Previous context is intelligently retrieved when relevant
- Use /next to start a new session while keeping history
- Use /forget to completely reset the conversation

## Technical Details

### Dependencies
- OpenAI GPT-4o for conversation generation and image analysis
- Salute Speech API for voice recognition
- Yandex OCR API for text extraction from images
- Telegram Bot API for messaging interface
- tiktoken for token counting
- numpy for embedding calculations

### Architecture
- Modular design with separate handlers for voice, text, and images
- Session-based conversation management
- Embedding-based context retrieval system
- Token usage tracking and management
- Error handling with user-friendly messages

### Performance Features
- Automatic message splitting for long responses
- Efficient token management
- Smart context summarization
- Optimized embedding storage and retrieval
- Temporary file management for image processing

## Services Used

### OpenAI API
- Uses GPT-4o for primary conversation
- GPT-4o-mini for intent detection and text cleaning
- GPT-4V for image analysis and diagram conversion
- Text embeddings for semantic search
- Required permissions: Chat completions, Embeddings

**Links:**
- [OpenAI Platform](https://platform.openai.com/)
- [API Documentation](https://platform.openai.com/docs/api-reference)
- [Models Overview](https://platform.openai.com/docs/models)
- [Pricing](https://openai.com/pricing)
- [Usage Guidelines](https://platform.openai.com/docs/guides/rate-limits)

### SberDevices Salute Speech
- Used for voice message transcription
- Supports Russian language
- High accuracy for conversational speech
- Real-time processing capabilities
- Required permissions: Speech recognition

**Links:**
- [Salute Speech Service](https://developers.sber.ru/portal/products/salutespeech)
- [API Documentation](https://developers.sber.ru/docs/ru/salutespeech/overview)
- [Quick Start](https://developers.sber.ru/docs/ru/salutespeech/quick-start)
- [API Methods](https://developers.sber.ru/docs/ru/salutespeech/api-methods)
- [Getting Access](https://developers.sber.ru/docs/ru/salutespeech/getting-started)

### Yandex Vision OCR
- Text extraction from images
- Multi-language support
- Layout preservation
- High accuracy for various text types
- Detailed response with text positioning
- Required permissions: Vision API access

**Links:**
- [Yandex Cloud Vision](https://cloud.yandex.com/en/services/vision)
- [API Documentation](https://yandex.cloud/en/docs/vision/operations/ocr/text-detection-image)
- [Getting Started](https://yandex.cloud/en/docs/vision/quickstart)
- [Pricing](https://cloud.yandex.com/en/prices#vision)
- [API Methods](https://yandex.cloud/en/docs/vision/api-ref/Vision/)

## Development

### Running Tests
```bash
# Run all tests
pytest

# Run specific test class
pytest tests/test_photo_handler.py::TestPhotoHandlerDownload -v

# Run with coverage
pytest --cov=bot tests/
```

### Adding New Features
1. Create new handler in appropriate module
2. Add tests with proper mocking
3. Update README with new functionality
4. Submit PR with changes

## License

MIT

## Support

For issues and feature requests, please use the GitHub issue tracker.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request