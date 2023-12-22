import os
import logging
import tempfile
import platform
from collections import namedtuple

import aiohttp
import asyncpg
import disnake
from disnake import Activity, ActivityType
from disnake.ext import commands

VERSION = "0.0.0"

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
        self.monitored_channels = [1187156262627053608]
    
    async def setup_hook(self):
        # Load cogs
        for extension in [filename[:-3] for filename in os.listdir("cogs") if filename.endswith(".py")]:
            try:
                self.load_extension(f"cogs.{extension}")
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"
                self.logger.exception(f"Failed to load extension {extension}!\t{exception}")

        # Initialize cache directory
        self.cache_dir = tempfile.mkdtemp()
        self.logger.debug(f"Initialized cache directory {self.cache_dir}")

        # Initialize database connection pool
        self.pool = await asyncpg.create_pool(dsn=self.config.DATABASE_URI, loop=self.loop, command_timeout=60)
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
        self.logger.info(f"Running on: {platform.system()} {platform.release()} ({os.name})")
        self.logger.info("------")

    async def close(self):
        self.clear_cache_dir()
        await self.session.close()
        await super().close()

    def clear_cache_dir(self):
        for file in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                self.logger.error(f"Error deleting {file}: {e}")
        os.rmdir(self.cache_dir)
    
    async def execute_query(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)        
