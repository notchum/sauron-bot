import asyncio

import disnake
from disnake.ext import commands

from bot import SauronBot


class Events(commands.Cog):
    def __init__(self, bot: SauronBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        """Called when a Message is created and sent."""
        if message.channel.id not in self.bot.config.MONITORED_CHANNELS:
            return
        if not message.attachments:
            return

        add_reaction = False

        # Process each attachment
        for attachment_index in range(len(message.attachments)):
            matches = await self.bot.insert_media_record(message, attachment_index)
            if len(matches) > 0:
                add_reaction = True

        # Add a reaction to the message if a repost was detected
        if add_reaction:
            await asyncio.sleep(1)
            await message.add_reaction("<:REPOST:1212160642002194472>")

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
        """Called when a Message receives an update event.
        This then calls on_message() to process the new edit.
        """
        if after.attachments and before.attachments != after.attachments:
            return await self.on_message(after)

    # @commands.Cog.listener()
    # async def on_message_delete(self, message: disnake.Message):
    #     """ Called when a Message is deleted. """
    #     if message.channel.id not in self.bot.config.MONITORED_CHANNELS:
    #         return
    #     if not message.attachments:
    #         return

    #     # Delete the record from the database
    #     query = """
    #         DELETE FROM media_fingerprints
    #         WHERE message_id = $1
    #         AND channel_id = $2
    #         AND guild_id = $3
    #         RETURNING *;
    #     """
    #     deleted_records = await self.bot.execute_query(query, message.id, message.channel.id, message.guild.id)
    #     if len(deleted_records) > 0:
    #         for record in deleted_records:
    #             logger.info(f"Deleted Record {record['id']} from message {message.id}")


def setup(bot: commands.Bot):
    bot.add_cog(Events(bot))
