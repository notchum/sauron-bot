# Use minimal linux image
FROM python:3.12.8-slim-bookworm

# Update pip
RUN python3.12 -m pip install --upgrade pip

# Install packages
RUN apt-get -y update && apt-get -y install git tesseract-ocr ffmpeg
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN rm requirements.txt

# Configure working directory
RUN mkdir -p /app
WORKDIR /app

# Import app code
COPY ./ /app

# Run the app
ENTRYPOINT python /app/launcher.py
