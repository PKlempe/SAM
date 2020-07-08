"""Contains a Cog for all utility funcionality."""

from datetime import datetime
from discord.ext import commands
import discord


class UtilitiesCog(commands.Cog):
    """Cog for Utility Functions."""

    def __init__(self, bot):
        """Initializes the Cog."""
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Command Handler for the `ping` command.

        Args:
            ctx (Context): The context in which the command was called.

        Returns:
            str: A message containing 'Pong!', as well as the measured latency to the Discord server in milliseconds.
        """
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send(":ping_pong: **Pong!** - {0} ms".format(latency))

    @commands.command(name='serverinfo')
    async def server_info(self, ctx):
        """Command Handler for the `serverinfo` command.

        Args:
            ctx (Context): The context in which the command was called.

        Returns:
            Embed: An embedded message (Embed) containing a variety of stats and interesting information about the
                    Discord server.
        """
        str_owner = "{0.display_name}#{0.discriminator}" \
            .format(ctx.guild.owner)
        str_boosts = "__Level {0.premium_tier}__\n{0.premium_subscription_count}{1} Boosts" \
            .format(ctx.guild, determine_boost_level_cap(ctx.guild.premium_subscription_count))
        str_members = "__Gesamt: {0[0]}__\nBots: {0[1]}\nMenschen: {0[2]}" \
            .format(get_member_counters(ctx.guild))
        str_channels = "__Gesamt: {0[0]}__\nText: {0[1]}\nSprach: {0[2]}" \
            .format(get_channel_counters(ctx.guild))
        str_roles = "__Gesamt: {0}__" \
            .format(len(ctx.guild.roles))
        str_features = generate_features_string(ctx.guild.features)

        embed = discord.Embed(title=ctx.guild.name, timestamp=datetime.now(), color=0x1E90FF)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text="Erstellungsdatum")
        embed.add_field(name="Besitzer :crown:", value=str_owner, inline=True)
        embed.add_field(name="Server Boost <:server_boost:730390579699122256>", value=str_boosts, inline=True)
        embed.add_field(name="Server Features :tools:", value=str_features, inline=True)
        embed.add_field(name="Mitglieder :man_raising_hand:", value=str_members, inline=True)
        embed.add_field(name="Kanäle :dividers:", value=str_channels, inline=True)
        embed.add_field(name="Rollen :medal:", value=str_roles, inline=True)
        await ctx.send(embed=embed)


def determine_boost_level_cap(amount_boosts):
    """Function for determining the current server level cap.

    Args:
        amount_boosts (int): The number of Boosts a server has received from its members.

    Returns:
        str: A short message indicating how many boosts are needed to level up.
    """
    level_cap = ""

    if amount_boosts < 2:
        level_cap = "/2"
    elif 2 <= amount_boosts < 15:
        level_cap = "/15"
    elif 15 <= amount_boosts < 30:
        level_cap = "/30"

    return level_cap


def get_channel_counters(guild):
    """Function for counting the amount of different channels on a server.

    Args:
        guild (Guild): A Guild object which represents a Discord server.

    Returns:
        list: A list containing the total amount of channels, the amount of text channel and the amount of voice
                channels on a server.
    """
    cntr_vc_channels = len(guild.voice_channels)
    cntr_txt_channels = len(guild.text_channels)
    cntr_channels = cntr_vc_channels + cntr_txt_channels

    return [cntr_channels, cntr_txt_channels, cntr_vc_channels]


def get_member_counters(guild):
    """Function for counting the amount of members and bots on a server.

    Args:
        guild (Guild): A Guild object which represents a Discord server.

    Returns:
        list: A list containing the total amount of members, the amount of bots and the amount of human members.
    """
    cntr_bots = len(list(filter(lambda user: user.bot, guild.members)))

    return [guild.member_count, cntr_bots, guild.member_count - cntr_bots]


def generate_features_string(features):
    """Function for creating a string which contains an enumeration of all available server features.

    Args:
        features (list): A list of available server features for a specific Discord server.

    Returns:
        str: A string containing an enumeration of all available server features.
    """
    ic_bullet_point = ":white_check_mark: "
    str_features = ":no_entry_sign: Keine"

    if len(features) != 0:
        str_features = ""

        for feature in features:
            str_features += {
                "VIP_REGIONS":              ic_bullet_point + "VIP-Regionen\n",
                "VANITY_URL":               ic_bullet_point + "Vanity URL\n",
                "INVITE_SPLASH":            ic_bullet_point + "Invite Splash\n",
                "VERIFIED":                 ic_bullet_point + "Verifiziert\n",
                "PARTNERED":                ic_bullet_point + "Discord-Partner\n",
                "MORE_EMOJI":               ic_bullet_point + "Mehr Emojis\n",
                "DISCOVERABLE":             ic_bullet_point + "In Server-Browser\n",
                "FEATURABLE":               ic_bullet_point + "Featurable\n",
                "COMMERCE":                 ic_bullet_point + "Commerce",
                "PUBLIC":                   ic_bullet_point + "Öffentlich\n",
                "NEWS":                     ic_bullet_point + "News-Kanäle\n",
                "BANNER":                   ic_bullet_point + "Server-Banner\n",
                "ANIMATED_ICON":            ic_bullet_point + "Animiertes Icon\n",
                "PUBLIC_DISABLED":          ic_bullet_point + "Public disabled\n",
                "WELCOME_SCREEN_ENABLED":   ic_bullet_point + "Begrüßungsbildschirm\n"
            }[feature]

    return str_features


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UtilitiesCog(bot))
