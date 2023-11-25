import os

import disnake
from disnake.ext import commands

from bot import SauronBot

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        """ Called when a Message is created and sent. """
        if message.author.bot:
            return
        if message.channel.id not in self.bot.monitored_channels:
            return
        if not message.attachments:
            return
        for attachment in message.attachments:
            if attachment.content_type is None:
                if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
            elif not attachment.content_type.startswith("image"):
                continue    
            
            try:
                image_path = os.path.join(self.bot.cache_dir, attachment.filename)
                await attachment.save(fp=image_path, use_cached=True)
            except:
                self.bot.logger.exception(f"Failed to save attachment {attachment.filename} from message {message.id}")
                continue

            if not image_path:
                continue
            
            # Extract text and hash from image
            text = self.bot.imageproc.ocr_core(image_path)
            hash = self.bot.imageproc.create_image_hash(image_path)

            # Find similar images in the database
            if "repost" not in message.clean_content.lower():
                query = """
                    SELECT *
                    FROM images
                    WHERE hash <@ ($1, $2)
                    AND guild_id = $3;
                """
                max_hamming_distance = 0
                matches = await self.bot.execute_query(query, hash, max_hamming_distance, message.guild.id)
                self.bot.logger.info(f"Message {message.id}: Found {len(matches)} exact images.")
                self.bot.logger.debug(f"Exact images: {matches}")

                # Send a message to the channel with links to the image matches
                if matches:
                    message_urls = []
                    for i, match in enumerate(matches, 1):
                        user_mention = f"<@{match['author_id']}>"
                        time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
                        jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
                        message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
                    message_urls = "\n".join(message_urls)

                    embed = disnake.Embed(
                        title=f"Repost Detected!",
                        description=f"This image has been posted `{len(matches)}` time(s) before.\n{message_urls}",
                        color=disnake.Color.dark_orange(),
                    ).set_thumbnail(url=attachment.url)
                    await message.reply(embed=embed)

            # Insert this image info into the database
            query = """
                INSERT INTO images (hash, text, guild_id, channel_id, message_id, author_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *;
            """
            result = await self.bot.execute_query(query, hash, text, message.guild.id, message.channel.id, message.id, message.author.id)
            for record in result:
                self.bot.logger.info(f"Message {message.id}: Inserted image {record['id']} into database.")
                self.bot.logger.info(f"                      Hash: {hash}")
                self.bot.logger.info(f"                      Text: {repr(text)}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        """ Called when a Message receives an update event.
            This then calls on_message() to process the new edit.
        """
        if after.attachments and before.attachments != after.attachments:
            return await self.on_message(after)

def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))