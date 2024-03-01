import os

import aiofiles
import disnake
from disnake.ext import commands

from bot import SauronBot
from views import Paginator
from helpers import ImageProcessor, VideoProcessor
from helpers.utilities import get_content_type, is_image_content_type, is_video_content_type

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot

    async def download_media(self, url: str) -> str | None:
        try:
            media_filename = os.path.basename(url).split("?")[0]
            media_path = os.path.join(self.bot.temp_dir, media_filename)

            if not os.path.exists(media_path):
                async with self.bot.session.get(url) as response:
                    if response.status != 200:
                        self.bot.logger.error(f"Downloading media {url} returned status code `{response.status}`")
                        return None
                    async with aiofiles.open(media_path, mode="wb") as f:
                        await f.write(await response.read())
            return media_path
        except Exception as err:
            self.bot.logger.error(f"Downloading media returned invalid data! {err}")
            return None

    async def get_attachment_hash(self, attachment: disnake.Attachment) -> int:
        file_path = os.path.join(self.bot.temp_dir, attachment.filename)
        await attachment.save(fp=file_path, use_cached=True)

        content_type = get_content_type(attachment)
        if content_type is None:
            raise ValueError(f"Attachment {attachment.filename} has invalid content type {attachment.content_type}")

        # Process the image or video
        if is_image_content_type(content_type):
            imageproc = ImageProcessor(file_path)
            hash = imageproc.hash
        elif is_video_content_type(content_type):
            try:
                videoproc = VideoProcessor(file_path, self.bot.temp_dir)
            except:
                raise ValueError(f"Failed to process video {attachment.filename}")
            hash = videoproc.hash
        else:
            raise ValueError(f"Attachment {attachment.filename} has invalid content type {attachment.content_type}")
        
        return hash

    async def find_similar_images(self, hash: int, max_hamming_distance: int, guild_id: int) -> list[dict[str, str]]:
        query = """
            SELECT *
            FROM media_metadata
            WHERE hash <@ ($1, $2)
            AND guild_id = $3;
        """
        matches = await self.bot.execute_query(query, hash, max_hamming_distance, guild_id)
        return matches

    async def send_search_results(self, inter: disnake.ApplicationCommandInteraction, matches: list[dict[str, str]], content: str = "", image_url: str = None):
        if not matches:
            await inter.edit_original_response("No similar images or videos found.")
            return

        matches.sort(key=lambda match: match['timestamp'])
        
        embeds = []
        message_urls = []
        for i, match in enumerate(matches, 1):
            user_mention = f"<@{match['author_id']}>"
            if match["by_bot"]:
                user_mention += f" via <@{match['bot_id']}>"
            time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
            jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
            
            message_urls.append(f"{i}. {jump_url} ({time_sent})\n  - Author: {user_mention}\n  - ID: {match['id']}")
            if i % 10 == 0:
                embed = disnake.Embed(
                    title="Search Results",
                    description="\n".join(message_urls),
                    color=disnake.Color.dark_orange(),
                )
                if image_url:
                    embed.set_thumbnail(url=image_url)
                embeds.append(embed)
                message_urls = []
        if message_urls:
            embed = disnake.Embed(
                title="Search Results",
                description="\n".join(message_urls),
                color=disnake.Color.dark_orange(),
            )
            if image_url:
                embed.set_thumbnail(url=image_url)
            embeds.append(embed)
        
        paginator_view = Paginator(embeds, inter.author)
        message = await inter.edit_original_response(content=f"Found `{len(matches)}` results. {content}", embed=embeds[0], view=paginator_view)
        paginator_view.message = message
        return

    @commands.slash_command()
    async def search_text(
        self,
        inter: disnake.ApplicationCommandInteraction,
        text: str
    ):
        """ Search for an image based on text. """
        await inter.response.defer()
        
        # Find text matches in the database using trigram similarity
        query = """
            SELECT *
            FROM media_metadata
            WHERE text_ocr % $1
            AND guild_id = $2
            ORDER BY text_ocr <-> $1;
        """
        trigram_matches = await self.bot.execute_query(query, f"%{text}%", inter.guild.id)
        
        # Find text matches in the database using full text search
        # query = """
        #     SELECT *
        #     FROM media_metadata
        #     WHERE text_ocr_vector @@ to_tsquery('english', $1)
        #     AND guild_id = $2
        #     ORDER BY ts_rank_cd(text_ocr_vector, to_tsquery('english', $1)) DESC;
        # """
        query = """
            SELECT *
            FROM media_metadata
            WHERE text_ocr_vector @@ plainto_tsquery('english', $1)
            AND guild_id = $2
            ORDER BY ts_rank_cd(text_ocr_vector, plainto_tsquery('english', $1)) DESC;
        """
        fts_matches = await self.bot.execute_query(query, f"%{text}%", inter.guild.id)
        
        # Combine the two lists of matches
        matches = []
        for match in trigram_matches:
            if match not in matches:
                matches.append(match)
        for match in fts_matches:
            if match not in matches:
                matches.append(match)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        await self.send_search_results(inter, matches, content=f"Query:\n> {text}")
    
    @commands.slash_command()
    async def search_attachment(
        self,
        inter: disnake.ApplicationCommandInteraction,
        attachment: disnake.Attachment,
        max_hamming_distance: int = 0
    ):
        """ Search for an image or video based on any message attachment.
        
            Parameters
            ----------
            attachment: `disnake.Attachment`
                The attachment to search for.
            max_hamming_distance: `int`
                The maximum Hamming distance to use when searching.
        """
        await inter.response.defer()

        file_path = os.path.join(self.bot.temp_dir, attachment.filename)
        await attachment.save(fp=file_path, use_cached=True)
        self.bot.logger.info(f"Saved attachment {attachment.filename} to {file_path}")

        hash = await self.get_attachment_hash(attachment)
        self.bot.logger.info(f"Hash: {hash}")

        matches = await self.find_similar_images(hash, max_hamming_distance, inter.guild.id)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        if not matches:
            await inter.edit_original_response("No similar images found.")
            return

        await self.send_search_results(inter, matches, image_url=attachment.url)
        return
    
    @commands.slash_command()
    async def search_url(
        self,
        inter: disnake.ApplicationCommandInteraction,
        media_url: str,
        max_hamming_distance: int = 0
    ):
        """ Search for an image or video with a URL to an image or video.

            Parameters
            ----------
            image_url: `str`
                The URL to the image or video to search for.
            max_hamming_distance: `int`
                The maximum Hamming distance to use when searching.
        """
        await inter.response.defer()
        
        file_path = await self.download_media(media_url)
        self.bot.logger.info(f"Downloaded image {file_path}")

        image_host_channel = await self.bot.fetch_channel(1164613880538992760)
        image_host_msg = await image_host_channel.send(file=disnake.File(file_path))
        attachment = image_host_msg.attachments[0]
        self.bot.logger.info(f"Uploaded image {image_host_msg.attachments[0].url}")

        hash = await self.get_attachment_hash(attachment)
        self.bot.logger.info(f"Hash: {hash}")

        matches = await self.find_similar_images(hash, max_hamming_distance, inter.guild.id)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        await self.send_search_results(inter, matches, image_url=attachment.url)
        return

    @commands.slash_command()
    async def search_message(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message: disnake.Message,
        max_hamming_distance: int = 0
    ):
        """ Search for an image or video based on a message attachment.
        
            Parameters
            ----------
            message: `disnake.Message`
                The message with the attachment to search for.
            max_hamming_distance: `int`
                The maximum Hamming distance to use when searching.
        """
        await inter.response.defer()

        if not message.attachments:
            await inter.edit_original_response(f"No attachments found in {message.jump_url}.")
            return
        attachment = message.attachments[0] #TODO: Add support for multiple attachments
            
        file_path = os.path.join(self.bot.temp_dir, attachment.filename)
        await attachment.save(fp=file_path, use_cached=True)
        self.bot.logger.info(f"Saved attachment {attachment.filename} from message {message.id} to {file_path}")
        
        hash = await self.get_attachment_hash(attachment)
        self.bot.logger.info(f"Hash: {hash}")

        matches = await self.find_similar_images(hash, max_hamming_distance, inter.guild.id)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        await self.send_search_results(inter, matches, image_url=attachment.url)
        return

    @commands.slash_command(default_member_permissions=disnake.Permissions(administrator=True))
    async def view_info(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message: disnake.Message
    ):
        """ View information about an image. """
        await inter.response.defer(ephemeral=True)

        query = """
            SELECT *
            FROM media_metadata
            WHERE message_id = $1
            AND channel_id = $2
            AND guild_id = $3;
        """
        result = await self.bot.execute_query(query, message.id, message.channel.id, message.guild.id)
        if not result:
            await inter.edit_original_response("No image found.")
            return

        record = result[0]
        user_mention = f"<@{record['author_id']}>"
        time_sent = f"<t:{int(record['timestamp'].timestamp())}:F>"
        jump_url = f"https://discord.com/channels/{record['guild_id']}/{record['channel_id']}/{record['message_id']}"

        embed = disnake.Embed(
            title=f"Image Info",
            description=f"By {user_mention} on {time_sent} in {jump_url}",
            color=disnake.Color.dark_orange(),
        ).set_thumbnail(url=message.attachments[0].url)

        # Print each field from the database record
        for field, value in record.items():
            embed.add_field(name=field, value=value, inline=False)

        await inter.edit_original_response(embed=embed)
        return

    @commands.slash_command(default_member_permissions=disnake.Permissions(administrator=True))
    async def delete_record(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message: disnake.Message
    ):
        """ Delete a record from the database. """
        await inter.response.defer(ephemeral=True)

        query = """
            DELETE FROM media_metadata
            WHERE message_id = $1
            AND channel_id = $2
            AND guild_id = $3;
        """
        await self.bot.execute_query(query, message.id, message.channel.id, message.guild.id)

        await inter.edit_original_response("Record deleted.")

    @commands.slash_command(default_member_permissions=disnake.Permissions(administrator=True))
    async def clear_cache(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ):
        """ Clear the files from the bot's temporary directory. """
        await inter.response.defer()
        self.bot.clear_temp_dir()
        await inter.edit_original_response("Cleared temporary directory.")

    @commands.slash_command(default_member_permissions=disnake.Permissions(administrator=True))
    async def execute_full_scrub(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        limit: int = None,
        oldest_first: bool = True,
        update_existing: bool = False,
        starting_message: disnake.Message = None
    ):
        """ Execute a full scrub of all monitored channels. """
        await inter.response.defer()

        if channel.id not in self.bot.monitored_channels:
            await inter.edit_original_response("Channel is not monitored.")
            return
        if starting_message.channel != channel:
            await inter.edit_original_response("Starting message is not within the selected channel.")
            return

        original_message = await inter.edit_original_response(f"Scrubbing {channel.mention}...")
        
        starting_message_found = False
        message_count = 1
        async for message in channel.history(limit=limit, oldest_first=oldest_first):
            if starting_message and not starting_message_found:
                if message.id >= starting_message.id:
                    starting_message_found = True
                else:
                    continue            
            if not message.attachments:
                continue

            if message_count % 100 == 0:
                original_message = await original_message.channel.fetch_message(original_message.id)
                await original_message.edit(f"Scrubbed {message_count} messages. Clearing cache...")
                self.bot.clear_temp_dir()
            
            for attachment_index in range(len(message.attachments)):
                await self.bot.insert_media_record(message, attachment_index, update_existing=update_existing)
            
            message_count += 1
        
        original_message = await original_message.channel.fetch_message(original_message.id)
        await original_message.edit(f"Finished scrubbing {message_count} messages.")

def setup(bot: commands.Bot):
    bot.add_cog(Commands(bot))