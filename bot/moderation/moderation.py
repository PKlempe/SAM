"""Contains a Cog for all functionality regarding Moderation."""

from datetime import datetime
from typing import List, Optional
import re

import discord
from discord.ext import commands

from bot import constants
from bot.logger import command_log, log
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

        self.guild = bot.get_guild(int(constants.SERVER_ID))

        # Channel instances
        self.ch_report = self.guild.get_channel(int(constants.CHANNEL_ID_REPORT))
        self.ch_modmail = self.guild.get_channel(int(constants.CHANNEL_ID_MODMAIL))

        # Role instances
        self.role_moderator = self.guild.get_role(int(constants.ROLE_ID_MODERATOR))

    @commands.command(name='avatar')
    @command_log
    async def user_avatar(self, ctx: commands.Context, *, user: discord.Member):
        description = "[.jpg]({0}) | [.png]({1}) | [.webp]({2})".format(user.avatar_url_as(format="jpg"),
                                                                        user.avatar_url_as(format="png"),
                                                                        user.avatar_url_as(format="webp"))
        possible_gif_url = str(user.avatar_url_as())

        if ".gif" in possible_gif_url:
            description += " | [.gif]({0})".format(possible_gif_url)

        embed = discord.Embed(title=f"Avatar von {user}", color=constants.EMBED_COLOR_MODERATION,
                              timestamp=datetime.utcnow(),
                              description=description)
        embed.set_footer(text="Erstellt am")
        embed.set_image(url=user.avatar_url)

        await ctx.send(embed=embed)

    @user_avatar.error
    async def convert_user_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for commands which take a username and try to convert them to a user/member object.

        Handles an exception which may occurs during the execution of commands when trying to convert a username to a
        user/member object. The global error handler will still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            regex = re.search(r"\"(.*)\"", error.args[0])  # Regex to get the text between two quotes.
            user = regex.group(1) if regex is not None else None

            await ctx.send(f"Ich konnte leider keinen Nutzer namens **{user}** finden. :confused: Hast du dich "
                           f"möglicherweise vertippt?")

    @commands.command(name='report')
    @command_log
    async def report_user(self, ctx: commands.Context, offender: discord.Member, *, description: str):
        """Command Handler for the `report` command.

        Allows users to report other members to the moderators by using their ID, name + discriminator, name, nickname
        or by simply mentioning them. Everything after that will be used as the description for the report. The
        complete report will then be posted in the configured report channel, which (hopefully) can only be accessed by
        by the moderators.
        If no member could be found, the user who invoked the command will be informed via a direct message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            offender (discord.Member): The person accused of doing something wrong.
            description (str): A description of why this person has been reported.
        """
        await ctx.message.delete()

        embed = _create_report_embed(offender, ctx.author, ctx.channel, ctx.message, description)
        await self.ch_report.send(embed=embed)

    @report_user.error
    async def report_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `report` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            regex = re.search(r"\"(.*)\"", error.args[0])  # Regex to get the text between two quotes.
            user = regex.group(1) if regex is not None else None

            await ctx.author.send(f"Ich konnte leider keinen Nutzer namens **{user}** finden. :confused: Hast du dich "
                                  f"möglicherweise vertippt?")

    @commands.group(name='purge', hidden=True)
    @commands.has_role(constants.ROLE_ID_MODERATOR)
    @command_log
    async def purge_messages(self, ctx: commands.Context, channel: Optional[discord.TextChannel], amount: int):
        """Command Handler for the `purge` command.

        Allows moderators to delete the specified amount of messages in a channel. After invocation, a confirmation
        message with all relevant information will be posted by SAM which the author needs to confirm in order to
        proceed with the operation. If the moderator chooses an invalid amount of messages (negative or higher than the
        configured limit), a temporary error message will be posted by the bot to inform the user.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            channel (Optional[discord.TextChannel]): The channel in which the messages should be deleted.
            amount (int): The amount of messages which need to be purged.
        """
        await ctx.message.delete()
        purge_channel = channel if channel else ctx.channel

        if amount <= 0 or amount > constants.LIMIT_PURGE_MESSAGES:
            raise commands.BadArgument("Invalid amount of messages to be purged was passed. "
                                       "Maximum: {0}, Passed limit: {1}".format(constants.LIMIT_PURGE_MESSAGES, amount))

        confirmation_embed = _build_purge_confirmation_embed(purge_channel, amount)
        is_confirmed = await self._send_confirmation_dialog(ctx, confirmation_embed)

        if is_confirmed:
            deleted_messages = await purge_channel.purge(limit=amount)
            await purge_channel.send('**Ich habe __{0} Nachrichten__ erfolgreich gelöscht.**'
                                     .format(len(deleted_messages)), delete_after=constants.TIMEOUT_INFORMATION)
            log.info("SAM deleted %s messages in [#%s]", len(deleted_messages), purge_channel)

    @purge_messages.error
    async def purge_messages_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `purge` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send(content="**__Error:__** Die Anzahl der Nachrichten welche gelöscht werden sollen, muss im "
                                   "__positiven Bereich__ liegen und darf __{0} nicht überschreiten__!"
                           .format(constants.LIMIT_PURGE_MESSAGES),
                           delete_after=constants.TIMEOUT_INFORMATION)

    @commands.group(name='modmail', invoke_without_command=True)
    @command_log
    async def modmail(self, ctx: commands.Context):
        """Command Handler for the `modmail` command.

        Allows users to write a message to all the moderators of the server. The message is going to be posted in a
        specified modmail channel which can (hopefully) only be accessed by said moderators. The user who invoked the
        command will get a confirmation via DM and the invocation will be deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        await ctx.message.delete()

        msg_content = ctx.message.content[len(ctx.prefix + ctx.command.name):]
        msg_attachments = ctx.message.attachments
        msg_author_name = str(ctx.message.author)
        msg_timestamp = ctx.message.created_at

        embed = discord.Embed(title="Status: Offen", color=constants.EMBED_COLOR_MODMAIL_OPEN,
                              timestamp=datetime.utcnow(), description=msg_content)
        embed.set_author(name=ctx.author.name + "#" + ctx.author.discriminator, icon_url=ctx.author.avatar_url)
        embed.set_footer(text="Erhalten am")

        msg_modmail = await self.ch_modmail.send(embed=embed, files=msg_attachments)
        self._db_connector.add_modmail(msg_modmail.id, msg_author_name, msg_timestamp)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_DONE)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)

        embed_confirmation = embed.to_dict()
        embed_confirmation["title"] = "Deine Nachricht:"
        embed_confirmation["color"] = constants.EMBED_COLOR_INFO
        embed_confirmation = discord.Embed.from_dict(embed_confirmation)
        await ctx.author.send("Deine Nachricht wurde erfolgreich an die Moderatoren weitergeleitet!\n"
                              "__Hier deine Bestätigung:__", embed=embed_confirmation)

    @modmail.command(name='get', hidden=True)
    @commands.has_role(constants.ROLE_ID_MODERATOR)
    @command_log
    async def get_modmail_with_status(self, ctx: commands.Context, *, status: str):
        """Command Handler for the modmail subcommand `get`.

        Allows moderators to generate an embedded message (Embed) in the modmail channel which contains a list of all
        modmail with the specified status. Each list element is a hyperlink which, if clicked, brings you to the
        corresponding modmail message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            status (str): The status specified by the moderator.
        """
        if ctx.channel.id == self.ch_modmail.id:
            try:
                enum_status = ModmailStatus[status.upper()]
                modmail = self._db_connector.get_all_modmail_with_status(enum_status)

                embed = _modmail_create_list_embed(enum_status, modmail)
                await self.ch_modmail.send(embed=embed)
            except (KeyError, ValueError):
                await ctx.channel.send("**__Error:__** Ungültiger oder nicht unterstützter Status `{0}`."
                                       .format(status.title()))

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def modmail_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the configured modmail channel and the added reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot and payload.channel_id == self.ch_modmail.id and \
                self.role_moderator in payload.member.roles:
            modmail = await self.ch_modmail.fetch_message(payload.message_id)

            if payload.emoji.name in (constants.EMOJI_MODMAIL_DONE, constants.EMOJI_MODMAIL_ASSIGN):
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, True)
                await modmail.edit(embed=new_embed)

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def modmail_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been removed.

        If the affected message is in the configured modmail channel and the removed reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_modmail.id:
            modmail = await self.ch_modmail.fetch_message(payload.message_id)

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or \
                    payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, False)
                await modmail.edit(embed=new_embed)

    async def change_modmail_status(self, modmail: discord.Message, emoji: str, reaction_added: bool) -> discord.Embed:
        """Method which changes the status of a modmail depending on the given emoji.

        This is done by changing the StatusID in the database for the respective message and visualized by changing the
        color of the Embed posted on Discord.

        Args:
            modmail (discord.Message): The Discord message in the specified modmail channel.
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

    async def _send_confirmation_dialog(self, ctx: commands.Context, embed: discord.Embed) -> bool:
        """Posts a confirmation dialog and returns the users answer.

        Posts an embed and adds reactions for confirmation and cancellation to it. A bool indicating if the user has
        confirmed or aborted the operation will be returned. Regardless of the return value the embed will be deleted
        shortly after.

        Args:
            ctx (commands.Context): The context of invocation. Used to send the message.
            embed (discord.Embed): The embed that will be posted. It should contain some explanation about what should
            be confirmed.

        Returns:
            (bool):A bool representing the users decision.
        """
        message = await ctx.send(embed=embed, delete_after=constants.TIMEOUT_USER_SELECTION)
        await message.add_reaction(constants.EMOJI_CONFIRM)
        await message.add_reaction(constants.EMOJI_CANCEL)

        def check_reaction(_reaction, user):
            return _reaction.message.id == ctx.message.id and user == ctx.author and \
                   str(_reaction.emoji) in [constants.EMOJI_CANCEL, constants.EMOJI_CONFIRM]

        reaction = await self.bot.wait_for('reaction_add', timeout=constants.TIMEOUT_USER_SELECTION,
                                           check=check_reaction)
        await message.delete()

        return str(reaction[0].emoji) == constants.EMOJI_CONFIRM


def _build_purge_confirmation_embed(channel: discord.TextChannel, amount: int) -> discord.Embed:
    """Creates an embed for confirmation of the `purge` command.

    Args:
        channel (discord.TextChannel): The channel in which the messages should be deleted.
        amount (int): The amount of messages the user wants to remove.

    Returns:
        (discord.Embed): The embed with the confirmation dialog
    """
    description = "**Bist du sicher dass du im Channel {0} __{1} Nachrichten__ löschen möchtest?**\nDiese Operation " \
                  "kann nicht rückgängig gemacht werden! Überlege dir daher gut, ob du das auch wirklich tun möchtest."\
        .format(channel.mention, amount)

    return discord.Embed(title=":warning: Purge-Bestätigung :warning:", description=description,
                         color=constants.EMBED_COLOR_WARNING)


def _create_report_embed(offender: discord.Member, reporter: discord.Member, channel: discord.TextChannel,
                         message: discord.Message, description: str) -> discord.Embed:
    """Method which creates an embed containing information about a possible incident on the server.

    Each embed consists of information about the person who reported a problem, the possible offender and a description
    about why the person has been reported.

    Args:
        offender (discord.Member): The user who has been reported.
        reporter (discord.Member): The person who submitted the report.
        channel (discord.TextChannel): The channel from where the report has been submitted.
        message (discord.Message): The message which invoked the command.
        description (str): The description why this person has been reported.

    Returns:
        discord.Embed: An embedded message containing information about a possible offender.
    """
    joined_at = offender.joined_at.strftime("%d.%m.%Y - %H:%M")
    created_at = offender.created_at.strftime("%d.%m.%Y - %H:%M")

    embed = discord.Embed(title="Nutzer-Infos", color=constants.EMBED_COLOR_REPORT, timestamp=datetime.utcnow(),
                          description=f"**Name:** {offender}\n**Beitritt am:** {joined_at}\n"
                                      f"**Erstellt am:** {created_at}")
    embed.set_author(name=f"Neue Meldung aus [#{channel}]")
    embed.set_footer(text=f"Gemeldet von {reporter}", icon_url=reporter.avatar_url)
    embed.add_field(name="Beschreibung:", value=f"{description}\n[Gehe zum Channel]({message.jump_url})")
    embed.set_thumbnail(url=offender.avatar_url)

    return embed


def _modmail_create_ticket_list(messages: List[tuple]) -> str:
    """Method which creates a string representing a list of modmail tickets.

    Each entry of the list consists of a timestamp representing the moment this ticket has been submitted and a link to
    the corresponding embedded message in the modmail channel. The text of each hyperlink represents the user who
    submitted the ticket.

    Args:
        messages (List[tuple]): A list containing tuples consisting of a message id and the authors name.

    Returns:
        str: A listing of hyperlinks with the specified Discord messages as their targets.
    """
    string = ""

    for message in messages:
        timestamp = datetime.strptime(message[2], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')

        string += "- {0} | [{1[1]}]({2}/channels/{3}/{4}/{1[0]})\n" \
            .format(timestamp, message, constants.URL_DISCORD, constants.SERVER_ID, constants.CHANNEL_ID_MODMAIL)

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
        dict_embed = embed.to_dict()
        dict_embed["description"] = _modmail_create_ticket_list(modmail)

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
        dict_embed["description"] = "Lehne dich zurück und entspanne ein wenig. Momentan gibt es für dich keine " \
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
