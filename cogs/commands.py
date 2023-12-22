import os

import aiofiles
import disnake
from disnake.ext import commands

from bot import SauronBot
from helpers import VideoProcessor

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot

    async def download_image(self, url: str) -> str | None:
        try:
            image_filename = os.path.basename(url).split("?")[0]
            image_path = os.path.join(self.cache_dir, image_filename)

            if not os.path.exists(image_path):
                async with self.session.get(url) as response:
                    if response.status != 200:
                        self.logger.error(f"Downloading image {url} returned status code `{response.status}`")
                        return None
                    async with aiofiles.open(image_path, mode="wb") as f:
                        await f.write(await response.read())
                    self.logger.info(f"Downloaded image {image_path}")
            return image_path
        except Exception as err:
            self.logger.error(f"Downloading image returned invalid data! {err}")
            return None

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

        if not matches:
            await inter.edit_original_response("No similar images found.")
            return
        
        message_urls = []
        for i, match in enumerate(matches, 1):
            user_mention = f"<@{match['author_id']}>"
            time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
            jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
            message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
        message_urls = "\n".join(message_urls)

        embed = disnake.Embed(
            title=f"Search Results",
            description=f"Found `{len(matches)}` similar images.\n{message_urls}",
            color=disnake.Color.dark_orange(),
        )
        await inter.edit_original_response(embed=embed)
        return
    
    @commands.slash_command()
    async def search_image(
        self,
        inter: disnake.ApplicationCommandInteraction,
        image: disnake.Attachment,
        max_hamming_distance: int = 10
    ):
        """ Search for an image based on an image. """
        await inter.response.defer()

        image_path = os.path.join(self.bot.cache_dir, image.filename)
        await image.save(fp=image_path, use_cached=True)
        
        hash = self.bot.imageproc.create_image_hash(image_path)

        query = """
            SELECT *
            FROM media_metadata
            WHERE hash <@ ($1, $2)
            AND guild_id = $3;
        """
        matches = await self.bot.execute_query(query, hash, max_hamming_distance, inter.guild.id)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        if not matches:
            await inter.edit_original_response("No similar images found.")
            return

        message_urls = []
        for i, match in enumerate(matches, 1):
            user_mention = f"<@{match['author_id']}>"
            time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
            jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
            message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
        message_urls = "\n".join(message_urls)
        
        embed = disnake.Embed(
            title=f"Search Results",
            description=f"Found `{len(matches)}` similar images.\n{message_urls}",
            color=disnake.Color.dark_orange(),
        ).set_thumbnail(url=image.url)
        await inter.edit_original_response(embed=embed)
        return
    
    @commands.slash_command()
    async def search_url(
        self,
        inter: disnake.ApplicationCommandInteraction,
        image_url: str,
        max_hamming_distance: int = 10
    ):
        """ Search for an image based on any image URL. """
        await inter.response.defer()
        
        image_path = await self.download_image(image_url)

        hash = self.bot.imageproc.create_image_hash(image_path)

        query = """
            SELECT *
            FROM media_metadata
            WHERE hash <@ ($1, $2)
            AND guild_id = $3;
        """
        matches = await self.bot.execute_query(query, hash, max_hamming_distance, inter.guild.id)
        self.bot.logger.info(f"Found {len(matches)} similar images.")

        if not matches:
            await inter.edit_original_response("No similar images found.")
            return

        message_urls = []
        for i, match in enumerate(matches, 1):
            user_mention = f"<@{match['author_id']}>"
            time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
            jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
            message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
        message_urls = "\n".join(message_urls)
        
        embed = disnake.Embed(
            title=f"Search Results",
            description=f"Found `{len(matches)}` similar images.\n{message_urls}",
            color=disnake.Color.dark_orange(),
        ).set_thumbnail(url=image_url)
        await inter.edit_original_response(embed=embed)
        return

    @commands.slash_command()
    async def search_message(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message: disnake.Message
    ):
        """ Search for an image based on a message. """
        await inter.response.defer()

        if not message.attachments:
            await inter.edit_original_response("No attachments found.")
            return

        for attachment in message.attachments:
            if attachment.content_type is None:
                if not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
            elif not attachment.content_type.startswith("image"):
                continue
            
            image_path = os.path.join(self.bot.cache_dir, attachment.filename)
            await attachment.save(fp=image_path, use_cached=True)
            
            hash = self.bot.imageproc.create_image_hash(image_path)

            query = """
                SELECT *
                FROM media_metadata
                WHERE hash <@ ($1, $2)
                AND guild_id = $3;
            """
            matches = await self.bot.execute_query(query, hash, 0, inter.guild.id)
            self.bot.logger.info(f"Found {len(matches)} similar images.")

            if not matches:
                await inter.edit_original_response("No similar images found.")
                return

            message_urls = []
            for i, match in enumerate(matches, 1):
                user_mention = f"<@{match['author_id']}>"
                time_sent = f"<t:{int(match['timestamp'].timestamp())}:F>"
                jump_url = f"https://discord.com/channels/{match['guild_id']}/{match['channel_id']}/{match['message_id']}"
                message_urls.append(f"{i}. By {user_mention} on {time_sent} in {jump_url}")
            message_urls = "\n".join(message_urls)
            
            embed = disnake.Embed(
                title=f"Search Results",
                description=f"Found `{len(matches)}` similar images.\n{message_urls}",
                color=disnake.Color.dark_orange(),
            ).set_thumbnail(url=attachment.url)
            await inter.edit_original_response(embed=embed)
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
    async def test(
        self,
        inter: disnake.ApplicationCommandInteraction
    ):
        """ Test command. """
        await inter.response.defer(ephemeral=True)
        
        for channel_id in self.bot.monitored_channels:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue

            async for message in channel.history(limit=None, oldest_first=True):
                if message.attachments:
                    attachment = message.attachments[0]
                    if attachment.content_type == 'image/gif':
                        query = """
                            DELETE FROM media_metadata
                            WHERE message_id = $1
                            AND channel_id = $2
                            AND guild_id = $3;
                        """
                        await self.bot.execute_query(query, message.id, channel.id, message.guild.id)
                    else:
                        query = """
                            UPDATE media_metadata
                            SET content_type = $1, filename = $2
                            WHERE message_id = $3
                            AND channel_id = $4
                            AND guild_id = $5;
                        """
                        await self.bot.execute_query(query, attachment.content_type, attachment.filename, message.id, channel.id, message.guild.id)

                    if attachment.content_type.startswith('video/'):
                        # Save the attachment to the cache directory
                        try:
                            file_path = os.path.join(self.bot.cache_dir, attachment.filename)
                            await attachment.save(fp=file_path, use_cached=True)
                        except:
                            self.bot.logger.exception(f"Failed to save attachment {attachment.filename} from message {message.id}")
                            continue
                        
                        # Process the video
                        videoproc = VideoProcessor(file_path)
                        text_tsb = videoproc.transcribe(cache_dir=self.bot.cache_dir)
                        text_ocr = None
                        hash = videoproc.hash
                        
                        query = """
                            INSERT INTO media_metadata (hash, text_ocr, text_tsb, content_type, filename, guild_id, channel_id, message_id, author_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
                        """
                        await self.bot.execute_query(query, hash, text_ocr, text_tsb, attachment.content_type, attachment.filename, message.guild.id, message.channel.id, message.id, message.author.id)

        await inter.edit_original_response("Test command successful.")

def setup(bot: commands.Bot):
    bot.add_cog(Commands(bot))