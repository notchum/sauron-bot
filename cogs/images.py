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
                FROM images
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
            FROM images
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

def setup(bot: commands.Bot):
    bot.add_cog(Images(bot))