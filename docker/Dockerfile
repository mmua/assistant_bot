# Dockerfile

FROM python:3.9-slim

# Set work directory
WORKDIR /usr/src/app

# Copy requirements file
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY bot.py ./

# Expose the port (if needed)
EXPOSE 8443

# Set environment variables (use .env file for sensitive data)
ENV TELEGRAM_TOKEN=<your-telegram-token>
ENV OPENAI_API_KEY=<your-openai-api-key>
ENV ADMIN_TELEGRAM_ID=<your-admin-id>

# Run the bot
CMD ["python", "bot/bot.py"]
