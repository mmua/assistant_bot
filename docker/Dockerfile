# Dockerfile

FROM python:3.12

# Set work directory
WORKDIR /usr/src/app

# Copy requirements file
COPY . ./

# Install dependencies
RUN apt update && apt install -y ffmpeg && apt clean

# Install dependencies
RUN pip install --no-cache-dir .

# Expose the port (if needed)
EXPOSE 8443

# Run the bot
CMD ["assistant_bot"]