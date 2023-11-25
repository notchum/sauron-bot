FROM python:3.10.4
RUN apt-get -y update
RUN mkdir -p /opt/sauron-bot
WORKDIR /opt/sauron-bot
COPY ./ /opt/sauron-bot
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT python /opt/sauron-bot/launcher.py