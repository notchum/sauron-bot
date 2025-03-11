# sauron-bot
A reverse image search Discord bot. This bot will monitor any given channel(s) for images/videos sent by users and hash/OCR them for reverse searching later.

The meat of this application is the custom database. The steps to manually set up this PostgreSQL database are outlined in [@KDJDEV's tutorial](https://github.com/KDJDEV/imagehash-reverse-image-search-tutorial). I have a custom Docker image pre-made with PostgreSQL 16 [here](https://hub.docker.com/repository/docker/notchum/postgres-spgist-bktree) that is used for this bot.

## Setup (Docker Compose)
Docker Compose is the recommended method to run sauron-bot in production. Below are the steps to deploy sauron-bot with Docker Compose.

### Step 1 - Download the required files
Create a directory of your choice (e.g. `/srv/sauron-bot`) to hold the `docker-compose.yml` and `.env` files.

Move to the directory you created:
```sh
mkdir /srv/sauron-bot
cd /srv/sauron-bot
```

Download `docker-compose.yml` and `.env.template` from this repo to the directory you created:
```sh
wget -O docker-compose.yml https://raw.githubusercontent.com/notchum/sauron-bot/main/docker-compose.yml
```

```sh
wget -O .env https://raw.githubusercontent.com/notchum/sauron-bot/main/.env.template
```

> [!NOTE]
> Notice how the `wget` command above renames `.env.template` to `.env`.

Download the database initialization script(s) in [`init-scripts/`](https://github.com/notchum/sauron-bot/tree/main/init-scripts) to a new directory. This directory must be separate from the Postgres data directory. Here we are putting it in the `/srv/sauron-bot` directory that we used above:
```sh
git clone https://raw.githubusercontent.com/notchum/sauron-bot /tmp/sauron-bot
mv /tmp/sauron-bot/init-scripts /srv/sauron-bot/postgres-data-init-scripts
```

### Step 2 - Populate the .env file with custom values
- `DISCORD_BOT_TOKEN` - Your Discord bot token.
- `DATABASE_URI` - The URI of the database, in this format: `postgres://postgres:YOUR_POSTGRES_PASSWORD@HOSTNAME:PORT/postgres`.
- `TESSERACT_CMD` - The path to the Tesseract executable within the Docker container. This is usually `/usr/bin/tesseract`.
- `POSTGRES_PASSWORD` - The password initialized for the Postgres database. Postgres is not publically exposed, so this password is only used for local authentication. To avoid issues with Docker parsing this value, it is best to use only the characters `A-Za-z0-9`.

### Step 3 - Start the containers
From the directory you created in Step 1, (which should now contain your customized `docker-compose.yml` and `.env` files) run `docker compose up -d`.
```sh
docker compose up -d
```

### Step 4 - Upgrading
When a new version of sauron-bot is released, the application can be upgraded with the following commands, run in the directory with the `docker-compose.yml` file:
```sh
docker compose pull && docker compose up -d
```
