import os
import shutil
import logging
import tempfile
import platform
from collections import namedtuple

import aiohttp
import asyncpg
import disnake
from disnake import Activity, ActivityType
from disnake.ext import commands

from helpers import ImageProcessor, VideoProcessor
from helpers.utilities import (
    get_content_type,
    is_image_content_type,
    is_video_content_type,
)

VERSION = "1.0.1"

Config = namedtuple(
    "Config",
    [
        "DEBUG",
        "DISNAKE_LOGGING",
        "TEST_MODE",
        "DISCORD_BOT_TOKEN",
        "DATABASE_URI",
        "TESSERACT_CMD",
    ],
)


class SauronBot(commands.InteractionBot):
    def __init__(self, *args, **kwargs):
        self.config: Config = kwargs.pop("config", None)
        self.logger: logging.Logger = kwargs.pop("logger", None)
        super().__init__(*args, **kwargs)
        self.activity = Activity(type=ActivityType.watching, name="you")
        self.monitored_channels = [788962609235886090, 759521817735725126]

    async def setup_hook(self):
        # Load cogs
        for extension in [
            filename[:-3] for filename in os.listdir("cogs") if filename.endswith(".py")
        ]:
            try:
                self.load_extension(f"cogs.{extension}")
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"
                self.logger.exception(
                    f"Failed to load extension {extension}!\t{exception}"
                )

        # Initialize temporary directory
        self.create_temp_dir()
        self.logger.debug(f"Initialized temp directory {self.temp_dir}")

        # Initialize database connection pool
        self.pool = await asyncpg.create_pool(
            dsn=self.config.DATABASE_URI, loop=self.loop, command_timeout=60
        )
        if self.config.TEST_MODE:
            self.logger.warning("Running in test mode. Using test database.")
        else:
            self.logger.info("Connected to database.")

        # Initialize aiohttp session
        self.session = aiohttp.ClientSession()

    async def on_ready(self):
        self.logger.info("------")
        self.logger.info(f"{self.user.name} v{VERSION}")
        self.logger.info(f"ID: {self.user.id}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Disnake API version: {disnake.__version__}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("------")

    def exit_handler(self):
        self.logger.info("Shutting down Sauron...")
        self.clear_temp_dir()
        os.rmdir(self.temp_dir)

    async def close(self):
        await self.session.close()
        await super().close()

    def create_temp_dir(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), "tmp-sauron-bot")
        if not os.path.exists(self.temp_dir):
            os.mkdir(self.temp_dir)

    def clear_temp_dir(self):
        for file in os.listdir(self.temp_dir):
            file_path = os.path.join(self.temp_dir, file)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                self.logger.error(f"Error deleting {file}: {e}")

    async def execute_query(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def insert_media_record(
        self,
        message: disnake.Message,
        attachment_index: int,
        update_existing: bool = False,
        record_id: int = None,
    ) -> None | list[dict]:
        # Error checking
        if not update_existing and record_id:
            raise ValueError(
                "Cannot specify a Record Identifier without setting `update_existing` parameter."
            )

        self.logger.info(f"[{attachment_index}] {message.jump_url}")

        # Get the attachment
        attachment = message.attachments[attachment_index]

        # Check if the attachment already exists in the database
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM media_metadata
                WHERE message_id = $1
                AND channel_id = $2
                AND guild_id = $3
                AND filename = $4
            );
        """
        exists = await self.execute_query(
            query, message.id, message.channel.id, message.guild.id, attachment.filename
        )
        exists: bool = exists[0][0]
        if exists and not update_existing:
            self.logger.info(
                f"└ Attachment {attachment.filename} already exists in the database."
            )
            return

        # Get the content type
        content_type = get_content_type(attachment)
        if content_type is None:
            self.logger.error(
                f"└ Attachment {attachment.filename} has invalid content type {attachment.content_type}"
            )
            return

        # Determine if the message was posted via a bot
        author_id = message.author.id
        posted_by_bot = False
        bot_id = None
        if message.author.bot:
            posted_by_bot = True
            bot_id = author_id
            if message.type == disnake.MessageType.application_command:
                author_id = message.interaction.user.id

        # Save the attachment to the cache directory
        try:
            file_path = os.path.join(self.temp_dir, attachment.filename)
            await attachment.save(fp=file_path, use_cached=True)
        except Exception as e:
            self.logger.exception(
                f"└ Failed to save attachment {attachment.filename}: {e}"
            )
            return

        # Process the image or video
        if is_image_content_type(content_type):
            self.logger.info(f"├ Processing image {attachment.filename}")
            imageproc = ImageProcessor(file_path)
            text_ocr = imageproc.ocr()
            video_transcription = None
            hash = imageproc.hash
        elif is_video_content_type(content_type):
            self.logger.info(f"├ Processing video {attachment.filename}")
            try:
                videoproc = VideoProcessor(file_path, self.temp_dir)
            except Exception as e:
                self.logger.exception(f"└ Failed to process video: {e}")
                return
            text_ocr = None  # TODO: Implement OCR for video
            video_transcription = videoproc.transcribe()
            hash = videoproc.hash
        else:
            self.logger.error(
                f"└ Attachment {attachment.filename} has invalid content type {attachment.content_type}"
            )
            return

        # Update the record if specified
        if record_id and update_existing:
            query = """
                UPDATE media_metadata
                SET hash = $1, text_ocr = $2, video_transcription = $3, content_type = $4, filename = $5, url = $6, timestamp = $7, attachment_index = $8
                WHERE id = $8;
            """
            await self.execute_query(
                query,
                hash,
                text_ocr,
                video_transcription,
                content_type,
                attachment.filename,
                attachment.url,
                message.created_at,
                attachment_index,
                record_id,
            )
            self.logger.info(
                f"└ Record {record_id}: Updated attachment {attachment.filename} in the database."
            )
            return
        elif exists and update_existing:
            query = """
                UPDATE media_metadata
                SET hash = $1, text_ocr = $2, video_transcription = $3, content_type = $4, filename = $5, url = $6, timestamp = $7, attachment_index = $8
                WHERE message_id = $9
                AND channel_id = $10
                AND guild_id = $11;
            """
            await self.execute_query(
                query,
                hash,
                text_ocr,
                video_transcription,
                content_type,
                attachment.filename,
                attachment.url,
                message.created_at,
                attachment_index,
                message.id,
                message.channel.id,
                message.guild.id,
            )
            self.logger.info(
                f"└ Updated attachment {attachment.filename} in the database."
            )
            return

        # Find exact matches in the database
        query = """
            SELECT *
            FROM media_metadata
            WHERE hash <@ ($1, $2)
            AND guild_id = $3;
        """
        max_hamming_distance = 0
        matches = await self.execute_query(
            query, hash, max_hamming_distance, message.guild.id
        )
        self.logger.info(f"├ Found {len(matches)} exact matches.")
        self.logger.debug(f"├ Exact matches: {[match['id'] for match in matches]}")

        # Insert into the database
        query = """
            INSERT INTO media_metadata (hash, text_ocr, video_transcription, content_type, filename, attachment_index, url, timestamp, guild_id, channel_id, message_id, author_id, by_bot, bot_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING *;
        """
        result = await self.execute_query(
            query,
            hash,
            text_ocr,
            video_transcription,
            content_type,
            attachment.filename,
            attachment_index,
            attachment.url,
            message.created_at,
            message.guild.id,
            message.channel.id,
            message.id,
            author_id,
            posted_by_bot,
            bot_id,
        )
        for record in result:
            self.logger.info(f"├ Inserted media {record['id']} into database.")
            self.logger.info(f"├ Hash: {hash}")
            self.logger.info(f"├ OCR Text: {repr(text_ocr)}")
            self.logger.info(f"└ Transcription: {repr(video_transcription)}")

        return matches
