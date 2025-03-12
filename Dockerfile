# Use minimal linux image
FROM python:3.12.8-alpine

# Install packages
RUN apk add git tesseract-ocr ffmpeg
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --ignore-installed openai-whisper
RUN rm requirements.txt
RUN apk del git

# Configure working directory
RUN mkdir -p /app
WORKDIR /app

# Import app code
COPY ./ /app

# Run the app
ENTRYPOINT python /app/launcher.py