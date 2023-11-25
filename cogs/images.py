import os

import disnake
from disnake.ext import commands

from bot import SauronBot

class Images(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: SauronBot = bot

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
            FROM images
            WHERE text % $1
            AND guild_id = $2
            ORDER BY text <-> $1;
        """
        trigram_matches = await self.bot.execute_query(query, f"%{text}%", inter.guild.id)
        
        # Find text matches in the database using full text search
        # query = """
        #     SELECT *
        #     FROM images
        #     WHERE text_vector @@ to_tsquery('english', $1)
        #     AND guild_id = $2
        #     ORDER BY ts_rank_cd(text_vector, to_tsquery('english', $1)) DESC;
        # """
        query = """
            SELECT *
            FROM images
            WHERE text_vector @@ plainto_tsquery('english', $1)
            AND guild_id = $2
            ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', $1)) DESC;
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
            FROM images
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
        
        image_path = await self.bot.imageproc.download_image(image_url)

        hash = self.bot.imageproc.create_image_hash(image_path)

        query = """
            SELECT *
            FROM images
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
    
    @commands.slash_command(default_member_permissions=disnake.Permissions(administrator=True))
    async def test(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        
        for channel in inter.guild.text_channels:
            if channel.id not in self.bot.monitored_channels:
                continue
            self.bot.logger.info(f"Searching channel {channel.name}[{channel.id}] for images...")
            async for message in channel.history(limit=None, oldest_first=True):
                if message.author.bot:
                    continue

                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM images
                        WHERE message_id = $1
                        AND channel_id = $2
                        AND guild_id = $3
                    );
                """
                exists = await self.bot.execute_query(query, message.id, message.channel.id, message.guild.id)
                if exists[0][0]:
                    query = """
                        UPDATE images
                        SET timestamp = $1
                        WHERE message_id = $2
                        AND channel_id = $3
                        AND guild_id = $4;
                    """
                    await self.bot.execute_query(query, message.created_at, message.id, message.channel.id, message.guild.id)
                    continue                
                
                jump_url = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                self.bot.logger.info(f"Searching message {jump_url}")
                if not message.attachments:
                    continue
                
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
                    
                    text = self.bot.imageproc.ocr_core(image_path)
                    hash = self.bot.imageproc.create_image_hash(image_path)

                    query = """
                        INSERT INTO images (hash, text, guild_id, channel_id, message_id, author_id)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING *;
                    """
                    await self.bot.execute_query(query, hash, text, message.guild.id, message.channel.id, message.id, message.author.id)
                    self.bot.logger.info(f"Inserted image from message {message.id} into database.")

def setup(bot: commands.Bot):
    bot.add_cog(Images(bot))