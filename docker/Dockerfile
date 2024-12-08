FROM python:3.10-slim

# Install ffmpeg with minimal additional files
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /usr/src/app

# Copy just the requirements first to leverage Docker cache
COPY pyproject.toml ./

# Copy the rest of the application
COPY . . 

RUN pip install --no-cache-dir .

# Expose the port (if needed)
EXPOSE 8443

# Run the bot
CMD ["assistant_bot"]