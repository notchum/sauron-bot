from disnake.ext import commands, tasks
from loguru import logger

from bot import SauronBot


class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot
        self.clean_temp_dir.start()
        self.check_for_media.start()

    @tasks.loop(hours=1.0)
    async def clean_temp_dir(self):
        """Clears all files from the bot's temporary directory."""
        if self.clean_temp_dir.current_loop == 0:
            return
        logger.debug(
            f"Cleaning temp directory... [loop #{self.clean_temp_dir.current_loop}]"
        )
        self.bot.clear_temp_dir()
        logger.info("Finished clearing temp directory.")

    @tasks.loop(hours=1.0)
    async def check_for_media(self):
        logger.debug(
            f"Checking for absent media... [loop #{self.check_for_media.current_loop}]"
        )

        for channel_id in self.bot.monitored_channels:
            channel = await self.bot.fetch_channel(channel_id)
            logger.info(
                f"Searching channel {channel.name}[{channel.id}] for media..."
            )
            async for message in channel.history(limit=20):
                if not message.attachments:
                    continue

                for attachment_index in range(len(message.attachments)):
                    await self.bot.insert_media_record(message, attachment_index)

        logger.info("Finished checking for absent media.")

    @clean_temp_dir.before_loop
    @check_for_media.before_loop
    async def wait_before_tasks(self):
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    bot.add_cog(Tasks(bot))
