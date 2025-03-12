# Use minimal linux image
FROM python:3.12.8-alpine

# Update pip
RUN python3.12 -m pip install --upgrade pip

# Install packages
RUN apk add git tesseract-ocr ffmpeg
RUN pip install openai-whisper
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN rm requirements.txt
RUN apk del git

# Configure working directory
RUN mkdir -p /app
WORKDIR /app

# Import app code
COPY ./ /app

# Run the app
ENTRYPOINT python /app/launcher.py
