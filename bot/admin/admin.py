"""Contains a Cog for all administrative funcionality."""

import json
from datetime import datetime
from typing import Optional, Mapping

import discord
import requests
from discord.ext import commands

from bot import constants
from bot.logger import command_log, log
from bot.persistence import DatabaseConnector


# disables too many public methods for now TODO: fix this (maybe with mixins)
# pylint: disable=R0904
class AdminCog(commands.Cog):
    """Cog for administrative Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

        self.guild = bot.get_guild(int(constants.SERVER_ID))

        # Channel instances
        self.ch_bot = self.guild.get_channel(int(constants.CHANNEL_ID_BOT))

    # A special method that registers as a commands.check() for every command and subcommand in this cog.
    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)  # Only owners of the bot can use the commands defined in this Cog.

    @commands.command(name="echo", hidden=True)
    @command_log
    async def echo(self, ctx: commands.Context, channel: Optional[discord.TextChannel], *, text: str):
        """Lets the bot post a simple message to the mentioned channel (or the current channel if none is mentioned).

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            channel (Optional[str]): The channel where the message will be posted in.
            text (str): The text to be echoed.
        """
        await (channel or ctx).send(text)

    @commands.group(name='embed', hidden=True, invoke_without_command=True)
    @command_log
    async def embed(self, _ctx: commands.Context, channel: discord.TextChannel, color: discord.Colour, *, text: str):
        """Command Handler for the embed command

        Creates and sends an embed in the specified channel with color, title and text. The Title and text are separated
        by a '|' character.

        Args:
            _ctx (Context): The context in which the command was called.
            channel (str): The channel where to post the message. Can be channel name (starting with #) or channel id.
            color (str): Color code for the color of the strip.
            text (str): The text to be posted in the embed. The string contains title and content, which are separated
                        by a '|' character. If this character is not found, no title will be assumed.
        """
        if '|' in text:
            title, description = text.split('|')
        else:
            title = ''
            description = text

        embed = discord.Embed(title=title, description=description, color=color)
        await channel.send(embed=embed)

    @embed.command(name='json', hidden=True)
    @command_log
    async def embed_by_json(self, _ctx: commands.Context, channel: discord.TextChannel, *, json_string: str):
        """Command Handler for the embed command.

        Creates and sends an embed in the specified channel parsed from json.

        Args:
            _ctx (Context): The context in which the command was called.
            channel (str): The channel where to post the message. Can be channel name (starting with #) or channel id.
            json_string (str): The json string representing the embed. Alternatively it could also be a pastebin link.
        """
        if is_pastebin_link(json_string):
            json_string = parse_pastebin_link(json_string)
        embed_dict = json.loads(json_string)
        embed = discord.Embed.from_dict(embed_dict)
        await channel.send(embed=embed)

    @commands.group(name="edit", hidden=True, invoke_without_command=True)
    async def edit(self, ctx: commands.Context):
        """Command Handler for the edit command.

        This command has 2 subcommands,
        `edit content` to edit the content of a message and
        `edit embed` to edit the embed of a message.

        Args:
              ctx (commands.Context): The context in which this command was invoked.
        """
        await ctx.send_help(ctx.command)

    @edit.command(name="content", hidden=True)
    async def edit_msg_content(self, _ctx: commands.Context, message: discord.Message, *, new_content: str):
        """Command handler for editing the content of a message posted by the bot.

        If the original message contained more than one embed only the first one will remain after editing.

        Args:
            _ctx (commands.Context): The context in which this command was invoked.
            message (discord.Message): The message to be edited.
            new_content (str). The new content to replace the original one.
        """
        if message.author != self.bot.user:
            raise commands.BadArgument("Can only edit message from bot user. The message was from: %s" % str(message.author))
        # First entry in embed list is used,
        await message.edit(content=new_content, embed=(message.embeds[0] if message.embeds else None))

    @edit.command(name="embed", hidden=True)
    async def edit_msg_embed(self, _ctx: commands.Context, message: discord.Message, *, new_embed: str):
        """Command handler for editing the content of a message posted by the bot.

        If the original message contained more than one embed only the first one will remain after editing.

        Args:
            _ctx (commands.Context): The context in which this command was invoked.
            message (discord.Message): The message to be edited.
            new_embed (str). The new embed in JSON format.
        """
        if message.author != self.bot.user:
            raise commands.BadArgument("Can only edit message from bot user. The message was from: {0}".format(
                str(message.author)))

        if is_pastebin_link(new_embed):
            new_embed = parse_pastebin_link(new_embed)
        embed_dict = json.loads(new_embed)
        embed = discord.Embed.from_dict(embed_dict)
        # Only first embed will be replaced.
        await message.edit(content=message.content, embed=embed)

    @embed.error
    @edit_msg_embed.error
    @edit_msg_content.error
    @embed_by_json.error
    async def embed_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the 'embed' command and its subcommand 'embed json'

        Handles errors specific for the embed commands. Others will be handled globally

        Args:
            ctx (commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        root_error = error if not isinstance(error, commands.CommandInvokeError) else error.original
        error_type = type(root_error)

        # put custom Error Handlers here
        async def handle_http_exception(ctx: commands.Context, _error: discord.HTTPException):
            await ctx.send(
                'Der übergebene JSON-String war entweder leer oder eines der Felder besaß einen ungültigen Typ.\n' +
                'Du kannst dein JSON auf folgender Seite validieren und gegebenenfalls anpassen: ' +
                'https://leovoel.github.io/embed-visualizer/.')

        async def handle_json_decode_error(ctx: commands.Context, error: json.JSONDecodeError):
            await ctx.send(
                "Der übergebene JSON-String konnte nicht geparsed werden. Hier die erhaltene Fehlermeldung:\n{0}".format(
                    str(error)))

        async def handle_bad_argument_error(ctx: commands.Context, _error: commands.BadArgument):
            await ctx.send(
                "Tut mir leid, aber anscheinend gibt es Probleme mit der von dir angegebenen ID. Bist du dir sicher "
                "dass du die richtige kopiert hast?")

        handler_mapper = {
            discord.errors.HTTPException: handle_http_exception,
            json.JSONDecodeError: handle_json_decode_error,
            commands.BadArgument: handle_bad_argument_error
        }

        if error_type in handler_mapper:
            await handler_mapper[error_type](ctx, root_error)

    @commands.group(name="bot", hidden=True, invoke_without_command=True)
    @command_log
    async def cmd_for_bot_stuff(self, ctx: commands.Context):
        """Command handler for the `bot` command.

        This is a command group regarding everything directly bot related. It provides a variety of subcommands for
        special tasks like rebooting the bot or changing its Discord presence. For every single subcommand administrator
        permissions are needed. If no subcommand has been provided, the corresponding help message will be posted
        instead.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        await ctx.send_help(ctx.command)

    @cmd_for_bot_stuff.command(name="cogs", hidden=True)
    @command_log
    async def embed_available_cogs(self, _ctx: commands.Context):
        """Command handler for the `bot` subcommand `cogs`.

        Creates an Embed containing a list of all available Cogs and their current status (un-/loaded). This embed will
        then be posted in the configured bot channel.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        str_cogs = _create_cogs_embed_string(self.bot.cogs)
        description = "Auflistung sämtlich vorhandener \"Cogs\" des Bots. Die Farbe vor den Namen signalisiert, ob " \
                      "die jeweilige Erweiterung momentan geladen ist oder nicht."

        embed = discord.Embed(title="Verfügbare \"Cogs\"", color=constants.EMBED_COLOR_SYSTEM, description=description,
                              timestamp=datetime.utcnow())
        embed.set_footer(text="Erstellt am")
        embed.add_field(name="Status", value=str_cogs)

        await self.ch_bot.send(embed=embed)

    @cmd_for_bot_stuff.group(name="cog", hidden=True, invoke_without_command=True)
    @command_log
    async def management_cog(self, ctx: commands.Context):
        """Command handler for the `bot` subcommand group `cog`.

        This group contains subcommands for reloading, unloading or simply loading Cogs of the bot.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        await ctx.send_help(ctx.command)

    @management_cog.command(name='load', hidden=True)
    @command_log
    async def load_extension(self, _ctx: commands.Context, extn_name: str):
        """Command handler for the `bot cog` subcommand `load`.

        Loads an extension (Cog) with the specified name into the bot.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            extn_name (str): The name of the extension (Cog).
        """
        extn_name = _get_cog_name(extn_name)

        self.bot.load_extension(constants.INITIAL_EXTNS[extn_name])
        log.warning("%s has been loaded.", extn_name)
        await self.ch_bot.send(f":arrow_heading_down: `{extn_name}` has been successfully loaded.")

    @management_cog.command(name='unload', hidden=True)
    @command_log
    async def unload_extension(self, _ctx: commands.Context, extn_name: str):
        """Command handler for the `bot cog` subcommand `unload`.

        Removes an extension (Cog) with the specified name from the bot.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            extn_name (str): The name of the extension (Cog).
        """
        extn_name = _get_cog_name(extn_name)

        self.bot.unload_extension(constants.INITIAL_EXTNS[extn_name])
        log.warning("%s has been unloaded.", extn_name)
        await self.ch_bot.send(f":arrow_heading_up: `{extn_name}` has been successfully unloaded.")

    @management_cog.group(name='reload', hidden=True, invoke_without_command=True)
    @command_log
    async def reload_extension(self, _ctx: commands.Context, extn_name: str):
        """Command handler for the `bot cog` subcommand `reload`.

        Reloads an extension (Cog) with the specified name from the bot. If changes to the code inside a Cog have been
        made, this is going to apply them without taking the bot offline.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            extn_name (str): The name of the extension (Cog).
        """
        extn_name = _get_cog_name(extn_name)

        self.bot.reload_extension(constants.INITIAL_EXTNS[extn_name])
        log.warning("%s has been reloaded.", extn_name)
        await self.ch_bot.send(f":arrows_counterclockwise: `{extn_name}` has been successfully reloaded.")

    @reload_extension.command(name='all', hidden=True)
    @command_log
    async def reload_all_extension(self, _ctx: commands.Context):
        """Command handler for the `bot cog reload` subcommand `all`.

        Reloads all the extension (Cogs) from the bot. If changes to the code inside a Cog have been
        made, this is going to apply them without taking the bot offline.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        for cog_name, path in constants.INITIAL_EXTNS.items():
            self.bot.reload_extension(path)
            log.warning("%s has been reloaded.", cog_name)

        await self.ch_bot.send(":arrows_counterclockwise: All cogs have been successfully reloaded.")

    @load_extension.error
    @unload_extension.error
    @reload_extension.error
    @reload_all_extension.error
    async def management_cog_error(self, _ctx: commands.Context, error: commands.CommandError):
        """Error handler for the `bot` subcommand group `cog`.

        Special errors occurring during reloading, unloading or loading of a Cog are handled in here.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            error (commands.CommandError): The error raised during the execution of a command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, KeyError):
            await self.ch_bot.send("Es konnte leider kein Cog mit diesem Namen gefunden werden.")

    @cmd_for_bot_stuff.group(name="presence", invoke_without_command=True)
    @command_log
    async def change_discord_presence(self, ctx: commands.Context):
        """Command handler for the `bot` subcommand `presence`.

        This is a command group for changing the bots Discord presence. For every user-settable activity type there is
        a corresponding subcommand.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        await ctx.send_help(ctx.command)

    @change_discord_presence.command(name="watching")
    @command_log
    async def change_discord_presence_watching(self, _ctx: commands.Context,
                                               status: Optional[discord.Status] = discord.Status.online,
                                               *, activity_name: str):
        """Command handler for the `presence` subcommand `watching`.

        This is a command that changes the bots Discord presence to a watching activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of whatever the bot should be watching.
        """
        activity = discord.Activity(type=discord.ActivityType.watching, name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="listening")
    @command_log
    async def change_discord_presence_listening(self, _ctx: commands.Context,
                                                status: Optional[discord.Status] = discord.Status.online,
                                                *, activity_name: str):
        """Command handler for the `presence` subcommand `listening`.

        This is a command that changes the bots Discord presence to a listening activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of what the bot should be listening to.
        """
        activity = discord.Activity(type=discord.ActivityType.listening, name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="playing")
    @command_log
    async def change_discord_presence_playing(self, _ctx: commands.Context,
                                              status: Optional[discord.Status] = discord.Status.online,
                                              *, activity_name: str):
        """Command handler for the `presence` subcommand `playing`.

        This is a command that changes the bots Discord presence to a playing activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of the game which the bot should play.
        """
        activity = discord.Game(name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="streaming")
    @command_log
    async def change_discord_presence_streaming(self, _ctx: commands.Context, stream_url: str,
                                                status: Optional[discord.Status] = discord.Status.online,
                                                *, activity_name: str):
        """Command handler for the `presence` subcommand `streaming`.

        This is a command that changes the bots Discord presence to a streaming activity with the specified name and
        stream URL. The Discord status can also be set via the optional status argument.

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
            stream_url (str): The URL of the stream. (The watch button will redirect to this link if clicked)
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of whatever the bot should be streaming.
        """
        # Everything other than Twitch probably won't work because of a clientside bug in Discord.
        # More info here: https://github.com/Rapptz/discord.py/issues/5118
        activity = discord.Streaming(name=activity_name, url=stream_url)
        if "twitch" in stream_url:
            activity.platform = "Twitch"
        elif "youtube" in stream_url:
            activity.platform = "YouTube"
        else:
            activity.platform = None

        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="clear")
    @command_log
    async def change_discord_presence_clear(self, _ctx: commands.Context):
        """Command handler for the `presence` subcommand `clear`.

        This is a command that clears the currently set activity and sets the Discord status to "Online".

        Args:
            _ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        await self.bot.change_presence(activity=None)

    @commands.command(name="botonly")
    @command_log
    async def botonly(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Command handler for the `botonly` command.

        This command marks a channel in the database as bot-only, so every message posted by someone else than the bot
        will be deleted immediately.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            channel (discord.Textchannel): The channel that is to be made bot-only
        """
        target_channel = channel if channel is not None else ctx.channel
        is_channel_botonly = self._db_connector.is_botonly(target_channel)
        if is_channel_botonly:
            log.info("Deactivated bot-only mode for channel [#%s]", target_channel)
            self._db_connector.deactivate_botonly(target_channel)
        else:
            log.info("Activated bot-only mode for channel [#%s]", target_channel)
            self._db_connector.activate_botonly(target_channel)

        is_enabled_string = 'aktiviert' if not is_channel_botonly else 'deaktiviert'
        embed = _build_botonly_embed(is_enabled_string)
        await target_channel.send(embed=embed)

    @commands.Cog.listener(name='on_message')
    async def on_message(self, ctx: discord.Message):
        """Event Handler for new messages.

        Deletes a message if the channel it was posted in is in bot-only mode and the author isn't SAM.

        Args:
            ctx (discord.Message): The context this method was called in. Must always be a message.
        """
        if ctx.author == self.bot.user:
            return
        if self._db_connector.is_botonly(ctx.channel):
            await ctx.delete()


def is_pastebin_link(json_string: str) -> bool:
    """Verifies if the string is a link to pastebin.com by checking if it contains 'pastebin.com' and does not contain
    json specific symbols.

    Args:
        json_string (str): The string to be checked.

    Returns:
          bool: True if it is a link to pastebin.com, False if not.
    """
    return "pastebin.com" in json_string and not any(x in json_string for x in ("{", "}"))


def parse_pastebin_link(url: str) -> str:
    """Resolves a link to pastebin.com and returns the raw data behind it.
        This works with links to the original pastebin (pastebin.com/abc) and to raw links (pastebin.com/raw/abc)

        Args:
            url (str): The pastebin url to resolve.

        Returns:
            str: The raw data as string behind the link.

        Raises:
             Error: If the link could not be resolved for any reasons.
    """
    # add raw to url if not contained
    if "raw" not in url:
        split_index = url.find(".com/")
        url = url[:(split_index + 5)] + "raw/" + url[(split_index + 5):]
    return requests.get(url).text


def _get_cog_name(extn_name: str) -> str:
    """Method for converting user input into a valid Cog name if possible.

    Fixes capitalization and extends the Extension/Cog name if needed.

    Args:
        extn_name (str): The name (or part of it) of an Extension/Cog.

    Returns:
        str: String containing the desired Cog name.
    """
    cog_name = extn_name.capitalize()

    if not cog_name.endswith(("Cog", "cog")):
        cog_name += "Cog"
    elif cog_name.endswith("cog"):
        cog_name = cog_name[:-3] + "Cog"

    return cog_name


def _create_cogs_embed_string(loaded_cogs: Mapping[str, commands.Cog]) -> str:
    """Method for creating the string used in the cogs embed.

    Builds a string containing a list of all available Cogs. Each entry has an emoji representing if a Cog is currently
    loaded or not.

    Args:
        loaded_cogs (Mapping[str, commands.Cog]): A Mapping containing all currently loaded Cogs.

    Returns:
        str: String containing the list of all Cogs and their current status.
    """
    string = ""

    for cog in constants.INITIAL_EXTNS:
        if cog in loaded_cogs.keys():
            string += constants.EMOJI_AVAILABLE
        else:
            string += constants.EMOJI_UNAVAILABLE
        string += " --> {0}\n".format(cog[:-3])

    return string


def _build_botonly_embed(is_enabled_string: str):
    """Creates an embed for the botonly command.

    Args:
        is_enabled_string (str): A string which will be interpolated into the title. Should contain the word 'aktiviert'
        or 'deaktiviert'.

    Returns:
        (discord.Embed): An embed containing information, if the bot-only mode was en- or disabled for a channel.
    """
    title = 'Der Bot-only Mode wurde für diesen Channel {0}'.format(is_enabled_string)
    description = 'Der Bot-only Mode sorgt dafür, dass nur noch SAM Nachrichten in einem Channel posten darf. Jede ' \
                  'Nachricht von anderen Usern wird sofort gelöscht.'
    return discord.Embed(title=title, description=description, color=constants.EMBED_COLOR_BOTONLY)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(AdminCog(bot))
