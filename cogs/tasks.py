import os

from disnake.ext import commands, tasks

from bot import SauronBot
from helpers import ImageProcessor, VideoProcessor
from helpers.utilities import validate_attachment

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot
        self.check_for_images.start()

    @tasks.loop(hours=1)
    async def check_for_images(self):
        self.bot.logger.debug(f"Checking for absent images... [loop #{self.check_for_images.current_loop}]")

        for channel_id in self.bot.monitored_channels:
            channel = await self.bot.fetch_channel(channel_id)
            self.bot.logger.info(f"Searching channel {channel.name}[{channel.id}] for images...")
            async for message in channel.history():
                if message.author.bot:
                    continue

                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM media_metadata
                        WHERE message_id = $1
                        AND channel_id = $2
                        AND guild_id = $3
                    );
                """
                exists = await self.bot.execute_query(query, message.id, message.channel.id, message.guild.id)
                if exists[0][0]:
                    continue

                jump_url = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                self.bot.logger.info(f"Searching message {jump_url}")
                if not message.attachments:
                    continue
                
                for attachment in message.attachments:
                    if not validate_attachment(attachment):
                        continue

                    # TODO remove when added support for videos
                    if attachment.content_type.startswith("video"):
                        continue
                    
                    try:
                        image_path = os.path.join(self.bot.cache_dir, attachment.filename)
                        await attachment.save(fp=image_path, use_cached=True)
                    except Exception as e:
                        self.bot.logger.exception(f"Failed to save attachment {attachment.filename} from message {message.id}")
                        continue
                    
                    if not image_path:
                        continue
                    
                    imageproc = ImageProcessor(image_path)
                    text = imageproc.ocr()
                    hash = imageproc.hash

                    query = """
                        INSERT INTO images (hash, text, timestamp, guild_id, channel_id, message_id, author_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING *;
                    """
                    await self.bot.execute_query(query, hash, text, message.created_at, message.guild.id, message.channel.id, message.id, message.author.id)
                    self.bot.logger.info(f"Inserted image from message {message.id} into database.")
    
    @check_for_images.before_loop
    async def before_check_for_images(self):
        await self.bot.wait_until_ready()

def setup(bot: commands.Bot):
    bot.add_cog(Tasks(bot))