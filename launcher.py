import os
import asyncio

import disnake
from loguru import logger
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

    # Create logging file
    logger.add(
        "logs/sauron-bot.log",
        level="DEBUG" if config.DEBUG else "INFO",
        rotation="12:00",
    )
    if config.DISNAKE_LOGGING:
        pass  # TODO

    # Create intents
    intents = disnake.Intents.default()
    intents.message_content = True

    # Create bot
    bot = SauronBot(
        config=config,
        test_guilds=[759514108625682473, 776929597567795247],
        intents=intents,
    )
    await bot.setup_hook()
    await bot.start(config.DISCORD_BOT_TOKEN)


asyncio.run(main())
