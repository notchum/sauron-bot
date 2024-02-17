import os
import asyncio

import disnake
from disnake.ext import commands

from bot import SauronBot
from helpers import ImageProcessor, VideoProcessor
from helpers.utilities import validate_attachment, get_content_type, ContentType

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        """ Called when a Message is created and sent. """
        if message.channel.id not in self.bot.monitored_channels:
            return
        if not message.attachments:
            return
        
        add_reaction = False

        # Process each attachment
        for attachment in message.attachments:
            # Validate the attachment
            if not validate_attachment(attachment):
                continue
            
            # Save the attachment to the cache directory
            try:
                file_path = os.path.join(self.bot.cache_dir, attachment.filename)
                await attachment.save(fp=file_path, use_cached=True)
            except:
                self.bot.logger.exception(f"Failed to save attachment {attachment.filename} from message {message.id}")
                continue

            # Get the content type
            content_type = get_content_type(attachment)
            if content_type is None:
                self.bot.logger.error(f"Message {message.id}: Attachment {attachment.filename} has invalid content type {attachment.content_type}")
                continue

            # Process the image or video
            if content_type == ContentType.IMAGE:
                self.bot.logger.info(f"Message {message.id}: Processing image {attachment.filename}")
                imageproc = ImageProcessor(file_path)
                text_ocr = imageproc.ocr()
                video_transcription = None
                hash = imageproc.hash
            elif content_type == ContentType.VIDEO:
                self.bot.logger.info(f"Message {message.id}: Processing video {attachment.filename}")
                try:
                    videoproc = VideoProcessor(file_path)
                except:
                    self.bot.logger.exception(f"Failed to process video {attachment.filename}")
                    continue
                text_ocr = None # TODO: Implement OCR for video
                video_transcription = videoproc.transcribe(cache_dir=self.bot.cache_dir)
                hash = videoproc.hash
            else:
                self.bot.logger.error(f"Message {message.id}: Attachment {attachment.filename} has invalid content type {attachment.content_type}")
                continue

            # Find exact matches in the database
            query = """
                SELECT *
                FROM media_metadata
                WHERE hash <@ ($1, $2)
                AND guild_id = $3;
            """
            max_hamming_distance = 0
            matches = await self.bot.execute_query(query, hash, max_hamming_distance, message.guild.id)
            if matches:
                add_reaction = True
            self.bot.logger.info(f"Message {message.id}: Found {len(matches)} exact matches.")
            self.bot.logger.debug(f"Exact matches: {matches}")

            # Insert into the database
            query = """
                INSERT INTO media_metadata (hash, text_ocr, video_transcription, content_type, filename, guild_id, channel_id, message_id, author_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *;
            """
            result = await self.bot.execute_query(query, hash, text_ocr, video_transcription, attachment.content_type, attachment.filename, message.guild.id, message.channel.id, message.id, message.author.id)
            for record in result:
                self.bot.logger.info(f"Message {message.id}: Inserted media {record['id']} into database.")
                self.bot.logger.info(f"                      Hash: {hash}")
                self.bot.logger.info(f"                      OCR Text: {repr(text_ocr)}")
                self.bot.logger.info(f"                      Transcription: {repr(video_transcription)}")
        
        # Add a reaction to the message if a repost was detected
        if add_reaction:
            await asyncio.sleep(1)
            for emoji in ["🇷", "🇪", "🇵", "🇴", "🇸", "🇹", "♻️"]:
                await message.add_reaction(emoji)
            
            # TODO add toggle for sending reply message
            # message_urls = []
            # for i, match in enumerate(matches, 1):
            #     user_mention = f"<@{match['author_id']}>"
            #     time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
            #     jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
            #     message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
            # message_urls = "\n".join(message_urls)

            # embed = disnake.Embed(
            #     title=f"Repost Detected!",
            #     description=f"This image has been posted `{len(matches)}` time(s) before.\n{message_urls}",
            #     color=disnake.Color.dark_orange(),
            # ).set_thumbnail(url=attachment.url)
            # await message.reply(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        """ Called when a Message receives an update event.
            This then calls on_message() to process the new edit.
        """
        if after.attachments and before.attachments != after.attachments:
            return await self.on_message(after)

def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))