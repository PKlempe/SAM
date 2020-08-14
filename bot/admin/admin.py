"""Contains a Cog for all administrative funcionality."""

import json
from typing import Optional, Mapping
from datetime import datetime

import discord
import requests
from discord.ext import commands

from bot import constants
from bot.logger import command_log


class AdminCog(commands.Cog):
    """Cog for administrative Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot

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

    @commands.command(name='embed', hidden=True)
    @command_log
    async def embed(self, ctx: commands.Context, channel: discord.TextChannel, color: discord.Colour, *, text: str):
        """Command Handler for the embed command

        Creates and sends an embed in the specified channel with color, title and text. The Title and text are separated
        by a '|' character.

        Args:
            ctx (Context): The context in which the command was called.
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

    @commands.command(name='cembed', hidden=True)
    @command_log
    async def cembed(self, ctx: commands.Context, channel: discord.TextChannel, *, json_string: str):
        """Command Handler for the embed command.

        Creates and sends an embed in the specified channel parsed from json.

        Args:
            ctx (Context): The context in which the command was called.
            channel (str): The channel where to post the message. Can be channel name (starting with #) or channel id.
            json_string (str): The json string representing the embed. Alternatively it could also be a pastebin link.
        """
        try:
            if is_pastebin_link(json_string):
                json_string = parse_pastebin_link(json_string)
            embed_dict = json.loads(json_string)
            embed = discord.Embed.from_dict(embed_dict)
            await channel.send(embed=embed)
        except commands.errors.CommandInvokeError:
            await ctx.send("**__Error:__** Could not parse json. Make sure your last argument is valid JSON.")
        except discord.errors.HTTPException:
            await ctx.send("**__Error:__** Could not parse json. Make sure your last argument is valid JSON.")
        except discord.DiscordException:
            await ctx.send("**__Error:__** Invalid embed. Make sure you have at least title or description set (also "
                           "for each additional field). You can validate your json at "
                           "https://leovoel.github.io/embed-visualizer/.")
        except ValueError as error:
            await ctx.send(error)
        except TypeError:
            await ctx.send("**__Error:__** Error creating embed. Please check your parameters.")

    @commands.group(name="bot", hidden=True)
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
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @cmd_for_bot_stuff.group(name="cogs")
    @command_log
    async def embed_available_cogs(self, ctx: commands.Context):
        """Command handler for the `bot` subcommand `cogs`.

        Creates an Embed containing a list of all available Cogs and their current status (un-/loaded). This embed will
        then be posted in the configured bot channel.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        ch_bot = ctx.guild.get_channel(constants.CHANNEL_ID_BOT)
        str_cogs = _create_cogs_embed_string(self.bot.cogs)
        description = "Auflistung sämtlich vorhandener \"Cogs\" des Bots. Die Farbe vor den Namen signalisiert, ob " \
                      "die jeweilige Erweiterung momentan geladen oder ungeladen ist."

        embed = discord.Embed(title="Verfügbare \"Cogs\"", color=constants.EMBED_COLOR_SYSTEM, description=description,
                              timestamp=datetime.utcnow())
        embed.set_footer(text="Erstellt am")
        embed.add_field(name="Status", value=str_cogs)

        await ch_bot.send(embed=embed)

    @cmd_for_bot_stuff.group(name="presence")
    @command_log
    async def change_discord_presence(self, ctx: commands.Context):
        """Command handler for the `bot` subcommand `presence`.

        This is a command group for changing the bots Discord presence. For every user-settable activity type there is
        a corresponding subcommand.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @change_discord_presence.command(name="watching")
    @command_log
    async def change_discord_presence_watching(self, ctx: commands.Context,
                                               status: Optional[discord.Status] = discord.Status.online,
                                               *, activity_name: str):
        """Command handler for the `presence` subcommand `watching`.

        This is a command that changes the bots Discord presence to a watching activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of whatever the bot should be watching.
        """
        activity = discord.Activity(type=discord.ActivityType.watching, name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="listening")
    @command_log
    async def change_discord_presence_listening(self, ctx: commands.Context,
                                                status: Optional[discord.Status] = discord.Status.online,
                                                *, activity_name: str):
        """Command handler for the `presence` subcommand `listening`.

        This is a command that changes the bots Discord presence to a listening activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of what the bot should be listening to.
        """
        activity = discord.Activity(type=discord.ActivityType.listening, name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="playing")
    @command_log
    async def change_discord_presence_playing(self, ctx: commands.Context,
                                              status: Optional[discord.Status] = discord.Status.online,
                                              *, activity_name: str):
        """Command handler for the `presence` subcommand `playing`.

        This is a command that changes the bots Discord presence to a playing activity with the specified name. The
        Discord status can also be set via the optional status argument.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            status (Optional[discord.Status]): The status which should be displayed.
            activity_name (str): The name of the game which the bot should play.
        """
        activity = discord.Game(name=activity_name)
        await self.bot.change_presence(activity=activity, status=status)

    @change_discord_presence.command(name="streaming")
    @command_log
    async def change_discord_presence_streaming(self, ctx: commands.Context, stream_url: str,
                                                status: Optional[discord.Status] = discord.Status.online,
                                                *, activity_name: str):
        """Command handler for the `presence` subcommand `streaming`.

        This is a command that changes the bots Discord presence to a streaming activity with the specified name and
        stream URL. The Discord status can also be set via the optional status argument.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
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
    async def change_discord_presence_clear(self, ctx: commands.Context):
        """Command handler for the `presence` subcommand `clear`.

        This is a command that clears the currently set activity and sets the Discord status to "Online".

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        await self.bot.change_presence(activity=None)


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

    for cog in constants.INITIAL_EXTNS.keys():
        if cog in loaded_cogs.keys():
            string += constants.EMOJI_AVAILABLE
        else:
            string += constants.EMOJI_UNAVAILABLE
        string += " --> {0}\n".format(cog[:-3])

    return string


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(AdminCog(bot))
