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
    async def modmail_reaction_add(self, payload):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the configured Modmail channel and the added reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot and payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, True)
                await modmail.edit(embed=new_embed)

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def modmail_reaction_remove(self, payload):
        """Event listener which triggers if a reaction has been removed.

        If the affected message is in the configured Modmail channel and the removed reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, False)
                await modmail.edit(embed=new_embed)

    async def change_modmail_status(self, modmail, emoji, reacion_added):
        """Method which changes the status of a modmail depending on the given emoji.

        This is done by changing the StatusID in the database for the respective message and visualized by changing the
        color of the Embed posted on Discord.

        Args:
            modmail (discord.Message): The Discord message in the specified Modmail channel.
            emoji (str): A String containing the Unicode for a specific emoji.
            reacion_added (Boolean): A boolean indicating if a reaction has been added or removed.

        Returns:
            discord.Embed: An adapted Embed corresponding to the new modmail status.
        """
        curr_status = self._db_connector.get_modmail_status(modmail.id)
        dict_embed = modmail.embeds[0].to_dict()
        dict_embed["title"] = "Status: "

        if reacion_added and emoji == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.CLOSED:
            await modmail.clear_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.CLOSED)

            dict_embed["title"] += "Erledigt"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
        elif reacion_added and emoji == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.IN_PROGRESS:
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.IN_PROGRESS)

            dict_embed["title"] += "In Bearbeitung"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            dict_embed["title"] += "Offen"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN

            if emoji == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)
                await modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            elif emoji == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)

        return discord.Embed.from_dict(dict_embed)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(ModerationCog(bot))
