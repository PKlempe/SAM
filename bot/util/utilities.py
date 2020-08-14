"""Contains a Cog for all utility funcionality."""

from datetime import datetime
from typing import List

import discord
from discord.ext import commands

from bot import constants
from bot.logger import command_log


class UtilitiesCog(commands.Cog):
    """Cog for Utility Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot

    @commands.command(name='ping')
    @command_log
    async def ping(self, ctx: commands.Context):
        """Command Handler for the `ping` command.

        Posts a message containing 'Pong!', as well as the measured latency to the Discord server in milliseconds, in
        the channel where this command has been invoked.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send(":ping_pong: **Pong!** - {0} ms".format(latency))

    @commands.command(name='serverinfo')
    @command_log
    async def server_info(self, ctx: commands.Context):
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
    @command_log
    async def about(self, ctx: commands.Context):
        """Command Handler for the `about` command.

        Posts an embedded message (Embed) containing some information about this bot and useful links regarding the
        GitHub repository and donations in the channel where this command has been invoked.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        contributor = await commands.MemberConverter().convert(ctx, str(constants.USER_ID_CONTRIBUTOR))

        description = "**__SAM__** ist ein multi-funktionaler Discord-Bot, welcher speziell für den Server der " \
                      "Informatik-Fakultät der Universität Wien entwickelt wurde. Sein Ziel ist es unterschiedlichste" \
                      " hilfreiche Aufgaben zu erledigen und den Moderatoren das Leben ein wenig zu erleichtern."
        str_special_thanks = "Großen Dank an **{0}**, der mich bei der Entwicklung dieses Bots tatkräftig " \
                             "unterstützt hat.".format(contributor)
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
        "COMMERCE": "Kommerziell",
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


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UtilitiesCog(bot))
