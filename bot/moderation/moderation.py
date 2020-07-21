"""Contains a Cog for all functionality regarding Moderation."""

from datetime import datetime
from discord.ext import commands
import discord
from bot.persistence import DatabaseConnector
from bot.moderation import ModmailStatus
from bot import constants


class ModerationCog(commands.Cog):
    """Cog for Moderation Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

    @commands.command(name='modmail')
    async def modmail(self, ctx):
        """Command Handler for the `modmail` command.

        Allows users to write a message to all the moderators of the server. The message is going to be posted in a
        specified modmail channel which can (hopefully) only be accessed by said moderators. The user who invoked the
        command will get a confirmation via DM and the invocation will be deleted.

        Args:
            ctx (Context): The context in which the command was called.
        """
        msg_content = ctx.message.content
        msg_attachments = ctx.message.attachments
        await ctx.message.delete()

        ch_modmail = ctx.guild.get_channel(constants.CHANNEL_ID_MODMAIL)
        msg_content = msg_content[len(ctx.prefix + ctx.command.name):]

        embed = discord.Embed(title="Status: Offen",
                              color=constants.EMBED_COLOR_MODMAIL_OPEN, timestamp=datetime.utcnow(),
                              description=msg_content)
        embed.set_author(name=ctx.author.name + "#" + ctx.author.discriminator, icon_url=ctx.author.avatar_url)
        embed.set_footer(text="Erhalten am")

        msg_modmail = await ch_modmail.send(embed=embed, files=msg_attachments)
        self._db_connector.add_modmail(msg_modmail.id)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_DONE)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)

        embed_confirmation = embed.to_dict()
        embed_confirmation["title"] = "Deine Nachricht:"
        embed_confirmation["color"] = constants.EMBED_COLOR_INFO
        embed_confirmation = discord.Embed.from_dict(embed_confirmation)
        await ctx.author.send("Deine Nachricht wurde erfolgreich an die Moderatoren weitergeleitet!\n"
                              "__Hier deine Bestätigung:__", embed=embed_confirmation)

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def change_modmail_status_add(self, payload):
        """Event listener which changes the status and the embed of a modmail message if a specific reaction has been
        added by a user.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot and payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            curr_status = self._db_connector.get_modmail_status(modmail.id)
            dict_embed = modmail.embeds[0].to_dict()

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.CLOSED:
                await modmail.clear_reaction(constants.EMOJI_MODMAIL_ASSIGN)
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.CLOSED)
                dict_embed["title"] = "Status: Erledigt"
                dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
            elif payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.IN_PROGRESS:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.IN_PROGRESS)
                dict_embed["title"] = "Status: In Bearbeitung"
                dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED

            await modmail.edit(embed=discord.Embed.from_dict(dict_embed))

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def change_modmail_status_remove(self, payload):
        """Event listener which changes the status and the embed of a modmail message if a specific reaction has been
        removed by a user.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            curr_status = self._db_connector.get_modmail_status(modmail.id)
            dict_embed = modmail.embeds[0].to_dict()
            dict_embed["title"] = "Status: Offen"

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)
                dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN
                await modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            elif payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)
                dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN

            await modmail.edit(embed=discord.Embed.from_dict(dict_embed))


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(ModerationCog(bot))
