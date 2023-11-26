import os
import asyncio
import logging
import logging.handlers

import disnake
from dotenv import load_dotenv

from bot import SauronBot, Config

async def main():
    # Load the environment variables
    load_dotenv()

    # Create config
    config = Config(
        DEBUG=os.environ["DEBUG"] in ("1", "True", "true"),
        DISNAKE_LOGGING=os.environ["DISNAKE_LOGGING"] in ("1", "True", "true"),
        TEST_MODE=os.environ["TEST_MODE"] in ("1", "True", "true"),
        DISCORD_BOT_TOKEN=os.environ["DISCORD_BOT_TOKEN"],
        DATABASE_URI=os.environ["DATABASE_URI"],
        TESSERACT_CMD=os.environ["TESSERACT_CMD"],
    )

    # Create logger
    if config.DISNAKE_LOGGING:
        logger = logging.getLogger("disnake")
    else:
        logger = logging.getLogger("sauron-bot")
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    if not os.path.exists("log"):
        os.makedirs("log")
    handler = logging.handlers.TimedRotatingFileHandler(
        filename="log/sauron-bot.log",
        when="midnight",
        encoding="utf-8",
        backupCount=5,  # Rotate through 5 files
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Create intents
    intents = disnake.Intents.default()
    intents.message_content = True
    
    # Create bot
    bot = SauronBot(
        config=config,
        logger=logger,
        test_guilds=[776929597567795247, 759514108625682473],
        intents=intents,
    )
    await bot.setup_hook()
    await bot.start(config.DISCORD_BOT_TOKEN)

asyncio.run(main())