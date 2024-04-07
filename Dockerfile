FROM python:latest
RUN apt-get -y update && apt-get -y install tesseract-ocr ffmpeg
RUN mkdir -p /app/sauron-bot
WORKDIR /app/sauron-bot
COPY ./ /app/sauron-bot
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT python /app/sauron-bot/launcher.py