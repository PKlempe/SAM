"""Contains a Cog for all utility funcionality."""

import json
import typing
from datetime import datetime
from typing import List

import discord
import requests
from discord.ext import commands

from bot import constants


class UtilitiesCog(commands.Cog):
    """Cog for Utility Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx: discord.ext.commands.Context):
        """Command Handler for the `ping` command.

        Posts a message containing 'Pong!', as well as the measured latency to the Discord server in milliseconds, in
        the channel where this command has been invoked.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send(":ping_pong: **Pong!** - {0} ms".format(latency))

    @commands.command(name='serverinfo')
    async def server_info(self, ctx: discord.ext.commands.Context):
        """Command Handler for the `serverinfo` command.

        Posts an embedded message (Embed) containing a variety of stats and information regarding the server owner,
        server boosts, server features, members, channels and roles in the channel where this command has been invoked.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        embed_strings = build_serverinfo_strings(ctx.guild)

        embed = discord.Embed(title=ctx.guild.name, timestamp=datetime.utcnow(), color=constants.EMBED_COLOR_INFO)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text="Erstellungsdatum")

        embed.add_field(name="Besitzer :crown:", value=embed_strings[0], inline=True)
        embed.add_field(name="Server Boost <:server_boost:730390579699122256>", value=embed_strings[1], inline=True)
        embed.add_field(name="Server Features :tools:", value=embed_strings[2], inline=True)
        embed.add_field(name="Mitglieder :man_raising_hand:", value=embed_strings[3], inline=True)
        embed.add_field(name="Kanäle :dividers:", value=embed_strings[4], inline=True)
        embed.add_field(name="Rollen :medal:", value=embed_strings[5], inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='about')
    async def about(self, ctx: discord.ext.commands.Context):
        """Command Handler for the `about` command.

        Posts an embedded message (Embed) containing some information about this bot and useful links regarding the
        GitHub repository and donations in the channel where this command has been invoked.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        description = "**__SAM__** ist ein multi-funktionaler Discord-Bot, welcher speziell für den Server der " \
                      "Informatik-Fakultät der Universität Wien entwickelt wurde. Sein Ziel ist es unterschiedlichste" \
                      " hilfreiche Aufgaben zu erledigen und den Moderatoren das Leben ein wenig zu erleichtern."
        str_special_thanks = "Großen Dank an **{0}**, der mich bei der Entwicklung dieses Bots tatkräftig " \
                             "unterstützt hat.".format(self.bot.get_user(constants.USER_ID_CONTRIBUTOR))
        str_links = "- [Bot-Wiki](https://github.com/PKlempe/SAM/wiki)\n" \
                    "- [GitHub-Repo](https://github.com/PKlempe/SAM)\n" \
                    "- [Entwickler](https://github.com/PKlempe)\n" \
                    "- [Donate via Ko-fi](https://ko-fi.com/pklempe)"

        embed = discord.Embed(title="About", color=constants.EMBED_COLOR_INFO, description=description)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        embed.set_footer(text="Made with \U00002764\U0000FE0F and discord.py",
                         icon_url="https://i.imgur.com/JLl8ocp.png")

        embed.add_field(name="Special Thanks:", value=str_special_thanks)
        embed.add_field(name="Links:", value=str_links)
        await ctx.send(embed=embed)

    @commands.command(name='embed')
    @commands.has_guild_permissions(administrator=True)
    async def embed(self, ctx, channel: str, color: str, *, text: str):
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
        try:
            channel_to_post = get_text_channel(channel, ctx.guild)
        except ValueError as error:
            await ctx.send(error)
            return

        if '|' in text:
            title, description = text.split('|')
        else:
            title = ''
            description = text

        try:
            col = int('0x' + color, 16)
            embed = discord.Embed(title=title, description=description, color=col)
            await channel_to_post.send(embed=embed)
        except ValueError:
            await ctx.send("**__Error:__** Hex value could not be parsed. Please use a valid color code.")
            return

    @commands.command(name='cembed')
    @commands.has_guild_permissions(administrator=True)
    async def cembed(self, ctx, channel: str, *, json_string: str):
        """Command Handler for the embed command.

        Creates and sends an embed in the specified channel parsed from json.

        Args:
            ctx (Context): The context in which the command was called.
            channel (str): The channel where to post the message. Can be channel name (starting with #) or channel id.
            json (str): The json string representing the embed. Alternatively it could also be a pastebin link.
        """
        try:
            channel_to_post = get_text_channel(channel, ctx.guild)
            if is_pastebin_link(json_string):
                json_string = parse_pastebin_link(json_string)
            embed_dict = json.loads(json_string)
            embed = discord.Embed.from_dict(embed_dict)
            await channel_to_post.send(embed=embed)
        except discord.ext.commands.errors.CommandInvokeError:
            await ctx.send("**__Error:__** Could not parse json. Make sure your last argument is valid JSON.")
        except discord.errors.HTTPException:
            await ctx.send("**__Error:__** Could not parse json. Make sure your last argument is valid JSON.")
        except discord.DiscordException:
            await ctx.send(
                "**__Error:__** Invalid embed. Make sure you have at least title or description set (also for each additional field). You can validate your json at https://leovoel.github.io/embed-visualizer/.")
        except ValueError as error:
            await ctx.send(error)
        except TypeError:
            await ctx.send("**__Error:__** Error creating embed. Please check your parameters.")

    @commands.command(name="echo")
    async def echo(self, ctx, channel: typing.Optional[discord.TextChannel], *, text: str):
        """Lets the bot post a simple message to the mentioned channel (or the current channel if none is mentioned).

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            channel (Optional[str]): The channel where the message will be posted in.
            text (str): The text to be echoed
        """
        await (channel or ctx).send(text)



def build_serverinfo_strings(guild: discord.Guild) -> List[str]:
    """Function for building the strings needed for the serverinfo Embed.

    Args:
        guild (discord.Guild): A Guild object which represents a Discord server.

    Returns:
        List[str]: A list containing strings for each individual embed field.
    """
    str_owner = str(guild.owner)
    str_boosts = "__Level {0.premium_tier}__\n{0.premium_subscription_count}{1} Boosts" \
        .format(guild, determine_boost_level_cap(guild.premium_subscription_count))
    str_members = "__Gesamt: {0[0]}__\nBots: {0[1]}\nMenschen: {0[2]}" \
        .format(get_member_counters(guild))
    str_channels = "__Gesamt: {0[0]}__\nText: {0[1]}\nSprach: {0[2]}" \
        .format(get_channel_counters(guild))
    str_roles = "__Gesamt: {0}__" \
        .format(len(guild.roles))
    str_features = generate_features_list(guild.features)

    return [str_owner, str_boosts, str_features, str_members, str_channels, str_roles]


def determine_boost_level_cap(amount_boosts: int) -> str:
    """Function for determining the current server level cap.

    Args:
        amount_boosts (int): The number of Boosts a server has received from its members.

    Returns:
        str: A short message indicating how many boosts are needed to level up.
    """
    if amount_boosts < constants.DISCORD_BOOST_LVL1_CAP:
        return "/{0}".format(constants.DISCORD_BOOST_LVL1_CAP)
    if constants.DISCORD_BOOST_LVL1_CAP <= amount_boosts < constants.DISCORD_BOOST_LVL2_CAP:
        return "/{0}".format(constants.DISCORD_BOOST_LVL2_CAP)
    if constants.DISCORD_BOOST_LVL2_CAP <= amount_boosts < constants.DISCORD_BOOST_LVL3_CAP:
        return "/{0}".format(constants.DISCORD_BOOST_LVL3_CAP)
    return ""


def get_channel_counters(guild: discord.Guild) -> List[int]:
    """Function for counting the amount of different channels on a server.

    Args:
        guild (discord.Guild): A Guild object which represents a Discord server.

    Returns:
        List[int]: A list containing the total amount of channels, the amount of text channel and the amount of voice
            channels on a server.
    """
    cntr_vc_channels = len(guild.voice_channels)
    cntr_txt_channels = len(guild.text_channels)
    cntr_channels = cntr_vc_channels + cntr_txt_channels

    return [cntr_channels, cntr_txt_channels, cntr_vc_channels]


def get_member_counters(guild: discord.Guild) -> List[int]:
    """Function for counting the amount of members and bots on a server.

    Args:
        guild (discord.Guild): A Guild object which represents a Discord server.

    Returns:
        List[int]: A list containing the total amount of members, the amount of bots and the amount of human members.
    """
    cntr_bots = len(list(filter(lambda user: user.bot, guild.members)))

    return [guild.member_count, cntr_bots, guild.member_count - cntr_bots]


def generate_features_list(features: List[str]) -> str:
    """Function for creating a string which contains an enumeration of all available server features.

    Args:
        features (List[str]): A list of available server features for a specific Discord server.

    Returns:
        str: A string containing an enumeration of all available server features.
    """
    if len(features) == 0:
        return ":no_entry_sign: Keine"

    ic_bullet_point = ":white_check_mark: "
    dict_server_features = {
        "VIP_REGIONS": "VIP-Regionen",
        "VANITY_URL": "Vanity URL",
        "INVITE_SPLASH": "Invite Splash",
        "VERIFIED": "Verifiziert",
        "PARTNERED": "Discord-Partner",
        "MORE_EMOJI": "Mehr Emojis",
        "DISCOVERABLE": "In Server-Browser",
        "FEATURABLE": "Featurable",
        "COMMERCE": "Commerce",
        "PUBLIC": "Öffentlich",
        "NEWS": "News-Kanäle",
        "BANNER": "Server-Banner",
        "ANIMATED_ICON": "Animiertes Icon",
        "PUBLIC_DISABLED": "Public disabled",
        "WELCOME_SCREEN_ENABLED": "Begrüßungsbildschirm"
    }
    str_features = ""

    for feature in features:
        str_features += ic_bullet_point + dict_server_features[feature] + "\n"

    return str_features


def get_text_channel(channel_id: str, guild: discord.Guild) -> discord.TextChannel:
    """Parses a message id string and searches the text channel in the passed guild

    Args:
        channel_id (str): The id of the channel (might also be surrounded by '<#' and '>'
        guild (discord.Guild): The guild in which the channel is searched.

    Returns:
        discord.Channel: The found channel.

    Raises:
        ValueError: If the channel could not be found.
    """
    try:
        if channel_id.startswith('<#'):
            channel_id = channel_id[2:-1]
        channel = guild.get_channel(int(channel_id))
    except ValueError:
        raise ValueError(
            'Channel to post embed to could not be found. Use valid channel ID or mention (linked with #).')

    if channel is None:
        raise ValueError(
            'Channel to post embed to could not be found. Use valid channel ID or mention (linked with #).')

    return channel


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


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UtilitiesCog(bot))
