"""Contains a Cog for all functionality regarding Moderation."""

from datetime import datetime
from typing import List

import discord
from discord.ext import commands

from bot import constants
from bot.logger import command_log
from bot.moderation import ModmailStatus
from bot.persistence import DatabaseConnector


class ModerationCog(commands.Cog):
    """Cog for Moderation Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

    @commands.group()
    @command_log
    async def modmail(self, ctx: discord.ext.commands.Context):
        """Command Handler for the `modmail` command.

        Allows users to write a message to all the moderators of the server. The message is going to be posted in a
        specified modmail channel which can (hopefully) only be accessed by said moderators. The user who invoked the
        command will get a confirmation via DM and the invocation will be deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        if ctx.invoked_subcommand is None:
            msg_content = ctx.message.content
            msg_attachments = ctx.message.attachments
            msg_author_name = str(ctx.message.author)
            msg_timestamp = ctx.message.created_at
            await ctx.message.delete()

            ch_modmail = ctx.guild.get_channel(constants.CHANNEL_ID_MODMAIL)
            msg_content = msg_content[len(ctx.prefix + ctx.command.name):]

            embed = discord.Embed(title="Status: Offen", color=constants.EMBED_COLOR_MODMAIL_OPEN,
                                  timestamp=datetime.utcnow(), description=msg_content)
            embed.set_author(name=ctx.author.name + "#" + ctx.author.discriminator, icon_url=ctx.author.avatar_url)
            embed.set_footer(text="Erhalten am")

            msg_modmail = await ch_modmail.send(embed=embed, files=msg_attachments)
            self._db_connector.add_modmail(msg_modmail.id, msg_author_name, msg_timestamp)
            await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_DONE)
            await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)

            embed_confirmation = embed.to_dict()
            embed_confirmation["title"] = "Deine Nachricht:"
            embed_confirmation["color"] = constants.EMBED_COLOR_INFO
            embed_confirmation = discord.Embed.from_dict(embed_confirmation)
            await ctx.author.send("Deine Nachricht wurde erfolgreich an die Moderatoren weitergeleitet!\n"
                                  "__Hier deine Bestätigung:__", embed=embed_confirmation)

    @modmail.command(name='get')
    @commands.has_role(constants.ROLE_ID_MODERATOR)
    @command_log
    async def get_modmail_with_status(self, ctx: discord.ext.commands.Context, *, status: str):
        """Command Handler for the modmail subcommand `get`.

        Allows moderators to generate an embeded message (Embed) in the modmail channel which contains a list of all
        modmails with the specified status. Each list element is a hyperlink which, if clicked, brings you to the
        corresponding modmail message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            status (str): The status specified by the moderator.
        """
        if ctx.channel.id == constants.CHANNEL_ID_MODMAIL:
            try:
                enum_status = ModmailStatus[status.upper()]

                ch_modmail = ctx.guild.get_channel(constants.CHANNEL_ID_MODMAIL)
                modmail = self._db_connector.get_all_modmail_with_status(enum_status)

                embed = _modmail_create_list_embed(enum_status, modmail)
                await ch_modmail.send(embed=embed)
            except (KeyError, ValueError):
                await ctx.channel.send("**__Error:__** Ungültiger oder nicht unterstützter Status `{0}`."
                                       .format(status.title()))

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def modmail_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the configured Modmail channel and the added reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot and payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or \
                    payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, True)
                await modmail.edit(embed=new_embed)

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def modmail_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been removed.

        If the affected message is in the configured Modmail channel and the removed reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == constants.CHANNEL_ID_MODMAIL:
            modmail = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or \
                    payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, False)
                await modmail.edit(embed=new_embed)

    async def change_modmail_status(self, modmail: discord.Message, emoji: str, reaction_added: bool) -> discord.Embed:
        """Method which changes the status of a modmail depending on the given emoji.

        This is done by changing the StatusID in the database for the respective message and visualized by changing the
        color of the Embed posted on Discord.

        Args:
            modmail (discord.Message): The Discord message in the specified Modmail channel.
            emoji (str): A String containing the Unicode for a specific emoji.
            reaction_added (Boolean): A boolean indicating if a reaction has been added or removed.

        Returns:
            discord.Embed: An adapted Embed corresponding to the new modmail status.
        """
        curr_status = self._db_connector.get_modmail_status(modmail.id)
        dict_embed = modmail.embeds[0].to_dict()
        dict_embed["title"] = "Status: "

        if reaction_added and emoji == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.CLOSED:
            await modmail.clear_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.CLOSED)

            dict_embed["title"] += "Erledigt"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
        elif reaction_added and emoji == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.ASSIGNED:
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.ASSIGNED)

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


def _modmail_create_hyperlinks_list(messages: List[tuple]) -> str:
    """Method which creates a string representing a list of hyperlinks with specific Discord messages as their targets.

    Args:
        messages (List[tuple]): A list containing tuples consisting of a message id and the authors name.

    Returns:
        str: A listing of hyperlinks with the specified Discord messages as their targets.
    """
    string = ""

    for message in messages:
        string += "- [{0[1]}](https://discordapp.com/channels/{1}/{2}/{0[0]})\n" \
            .format(message, constants.SERVER_ID, constants.CHANNEL_ID_MODMAIL)

    return string


def _modmail_create_timestamps_list(messages: List[tuple]) -> str:
    """Method which creates a string representing a list of dates and times for when the individual messages provided
    have been created.

    Args:
        messages (List[tuple]): A list containing tuples consisting of a message id, the authors name and a timestamp.

    Returns:
        str: A listing of dates and times.
    """
    string = ""

    for message in messages:
        timestamp = datetime.strptime(message[2], '%Y-%m-%d %H:%M:%S.%f')
        string += timestamp.strftime('%d.%m.%Y %H:%M') + "\n"

    return string


def _modmail_create_list_embed(status: ModmailStatus, modmail: List[tuple]) -> discord.Embed:
    """Method which creates an Embed containing a list of hyperlinks to all the modmail with the specified status.

    Args:
        status (ModmailStatus): The status specified by a moderator.
        modmail (List[tuple]): A list containing tuples consisting of a message id and the authors name.

    Returns:
        discord.Embed: The embed containing the list of hyperlinks with the authors name as the link text.
    """
    embed = discord.Embed(timestamp=datetime.utcnow())
    embed.set_footer(text="Erstellt am")
    dict_embed = embed.to_dict()

    if modmail is not None:
        embed.add_field(name="Eingereicht von:", value=_modmail_create_hyperlinks_list(modmail), inline=True)
        embed.add_field(name="Eingereicht am:", value=_modmail_create_timestamps_list(modmail), inline=True)
        dict_embed = embed.to_dict()

        if status == ModmailStatus.OPEN:
            dict_embed["title"] = "Offenen Tickets: " + str(len(modmail))
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN
        elif status == ModmailStatus.ASSIGNED:
            dict_embed["title"] = "Zugewiesene Tickets: " + str(len(modmail))
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            raise ValueError("Nicht unterstützter Modmail-Status `{0}`.".format(status.name))
    elif status == ModmailStatus.OPEN:
        dict_embed["title"] = "Keine offenen Tickets! :tada:"
        dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
        dict_embed["description"] = "Lehn dich zurück und entspanne ein wenig. Momentan gibt es für dich keine " \
                                    "Tickets, welche du abarbeiten könntest. :beers:"
    elif status == ModmailStatus.ASSIGNED:
        dict_embed["title"] = "Keine Tickets in Bearbeitung! :eyes:"
        dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        dict_embed["description"] = "**Es ist ruhig, zu ruhig...** Vielleicht gibt es momentan ja ein paar offene " \
                                    "Tickets die bearbeitet werden müssten."
    else:
        raise ValueError("Nicht unterstützter Modmail-Status `{0}`.".format(status.name))

    return discord.Embed.from_dict(dict_embed)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(ModerationCog(bot))
