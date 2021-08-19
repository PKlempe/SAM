"""Contains a Cog for all utility functionality."""

from datetime import datetime
from typing import List, Optional

import discord
from discord.ext import commands

from bot import constants
from bot.logger import command_log, log


class UtilityCog(commands.Cog):
    """Cog for Utility Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot

        # Role instances
        self.role_moderator = bot.get_guild(int(constants.SERVER_ID)).get_role(int(constants.ROLE_ID_MODERATOR))

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
        embed.add_field(name="Server Boost <:server_boost:722778309309759559>", value=embed_strings[1], inline=True)
        embed.add_field(name="Mitglieder :man_raising_hand:", value=embed_strings[3], inline=True)
        embed.add_field(name="Kanäle :dividers:", value=embed_strings[4], inline=True)
        embed.add_field(name="Rollen :medal:", value=embed_strings[5], inline=True)
        embed.add_field(name="Server Features :tools:", value=embed_strings[2], inline=True)
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
        contributor = await commands.UserConverter().convert(ctx, str(constants.USER_ID_CONTRIBUTOR))

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

    @commands.group(name='howto', invoke_without_command=True)
    @command_log
    async def howto(self, ctx: commands.Context, subcommand: Optional[str]):
        """Handler for the `howto` command.

        The available subcommands of this Command Group post individual help messages explaining how to do various
        things regarding the Discord server itself or other often needed tasks.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            subcommand (Optional[str]): The subcommand the user wants to invoke.
        """
        message = "Ich kenne diesen Befehl leider nicht. Hast du vielleicht einen der folgenden gemeint?\n" \
            if subcommand else None

        await ctx.send(message, embed=discord.Embed(
            title="Verfügbare HowTos:",
            description="\n".join(["**- " + c.name + "**: " + c.description for c in self.howto.commands])
        ))

    @howto.command(name='code', description="Code richtig formatieren")
    @command_log
    async def howto_code(self, ctx: commands.context):
        """Handler for the `howto code` subcommand.

        Explains how to properly format code using Discords code blocks:
        https://support.discord.com/hc/articles/210298617

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        embed = discord.Embed(
            title="Code-Formatierung 📝",
            color=constants.EMBED_COLOR_HOWTO,
            description="Wenn du deinen Code mit anderen teilen willst, dann kannst du hierfür sogenannte Codeblöcke "
                        "verwenden. Sie sorgen dafür, dass dein Code vom Rest deiner Nachricht visuell abgegrenzt wird "
                        "und macht ihn lesbarer für alle.\n\nFür einen __Inline-Codeblock__, schreibe deinen Code "
                        "zwischen zwei Backticks (**`**).\nFür einen __Multi-Line-Codeblock__, verwende stattdessen "
                        "jeweils drei (**```**).\n\nIm letzteren Fall kannst du außerdem mit einem Kürzel nach den "
                        "ersten Backticks die jeweilige Programmiersprache angeben, um so sogar passendes "
                        "Syntax-Highlighting zu erhalten.",
        )
        embed.set_image(url="https://i.imgur.com/A0BGhtz.png")
        embed.add_field(name="Hinweis:",
                        value="Für zusätzliche Infos bzgl. der Formatierung von Nachrichten siehe "
                              "[Markdown Text 101](https://support.discord.com/hc/de/articles/210298617).")
        await ctx.send(embed=embed)

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def pin_message(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added to a message.

        If enough users have reacted with the specified pin emoji to a specific message, it will be pinned in the
        corresponding channel by SAM. If the maximum of pinned messages in a channel has been reached, a message will
        be posted to inform the members.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot and payload.emoji.name == constants.EMOJI_PIN:
            channel = self.bot.get_guild(int(constants.SERVER_ID)).get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            reaction = next(x for x in message.reactions if x.emoji == constants.EMOJI_PIN)

            if not message.pinned and reaction.count >= constants.LIMIT_PINS:
                try:
                    await message.pin(reason="Ausreichend Nutzer haben mit dem Pin-Emoji reagiert.")
                    log.info("A message has been pinned in channel %s via user reactions.", channel)
                except discord.HTTPException:
                    channel.send("Es sieht so aus, als wurden bereits zu viele Nachrichten in diesem Channel "
                                 "angepinnt. :pushpin:\nEin {0} könnte in diesem Fall die Pins ein wenig aufräumen. "
                                 ":broom:".format(self.role_moderator.mention))

    @commands.Cog.listener(name='on_member_join')
    async def welcome_message(self, user: discord.Member):
        """Event listener which triggers if a user joins the server.

        If the server gets a new member, the bot automatically welcomes him by sending a private message with some
        usefull tips.

        Args:
            user (discord.Member): The new member on the server.
        """
        log.info("%s has joined the server!", user)

        content = "Hallo! :wave: :grinning:\nIch bin **SAM**, der Management-Bot für den Discord-Server der " \
                  "**__Uni Wien INF/WINF__**. Es freut mich sehr, dass du zu uns gefunden hast!\n\nHier ein paar " \
                  "Tipps damit du sofort durchstarten kannst:"

        description = "**- Hol dir als __allererstes__ ein paar Rollen im Channel <#{0}>.**\n" \
                      "Was das genau bedeutet und wie es funktioniert, wird dir dort in einer kurzen Anleitung " \
                      "erklärt.\n\n" \
                      "**- Lies dir unsere <#{1}> durch.**\n" \
                      "Wir legen großen Wert darauf, dass sich auch wirklich jeder auf unserem Server wohlfühlt. Um " \
                      "dies zu gewährleisten, gibt es eine Gruppe an Moderatoren, die für die Einhaltung der Regeln " \
                      "sorgen und bei Problemen auch jederzeit kontaktiert werden können.\n\n" \
                      "**- Sieh dir die <#{2}> an.**\n" \
                      "Dort findest du Antworten zu den am häufigsten gestellten Fragen. Sollte das nicht " \
                      "ausreichen, dann stelle einfach eine neue Frage in <#{3}> oder schreibe einen " \
                      "Moderator direkt an.\n\n" \
                      "**- Hab Spaß und sei Teil der Community! :heart:**\n" \
                      "Unser Ziel ist es eine zentrale Anlaufstelle für Studierende zu schaffen, was nur mithilfe " \
                      "unserer Mitglieder funktionieren kann. Stelle/Beantworte Fragen, teile Unterlagen/Lösungen " \
                      "mit anderen und starte bzw. nimm an Diskussionen teil. Getrau dich ruhig aktiv zu sein, wir " \
                      "sind hier auf Discord sowieso alle anonym. :spy:\n" \
            .format(constants.CHANNEL_ID_ROLES, constants.CHANNEL_ID_RULES, constants.CHANNEL_ID_FAQ,
                    constants.CHANNEL_ID_QUESTIONS)

        embed = discord.Embed(description=description, color=constants.EMBED_COLOR_INFO) \
            .add_field(name=constants.ZERO_WIDTH_SPACE, value="> **Ein Studium ist nicht immer leicht, aber "
                                                              "__gemeinsam__ schaffen wir das!** :muscle:")
        await user.send(content=content, embed=embed)


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

    ic_bullet_point = ":white_check_mark:"
    dict_server_features = {
        "COMMUNITY": "Community-Server",
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
        "PUBLIC_DISABLED": "Nicht öffentlich",
        "WELCOME_SCREEN_ENABLED": "Begrüßungsbildschirm",
        "MEMBER_VERIFICATION_GATE_ENABLED": "Member Screening",
        "PREVIEW_ENABLED": "Servervorschau",
        "THREADS_ENABLED": "Threads",
        "PRIVATE_THREADS": "Private Threads",
        "THREE_DAY_THREAD_ARCHIVE": "3-Tage-Archiv für Threads",
        "SEVEN_DAY_THREAD_ARCHIVE": "7-Tage-Archiv für Threads"
    }
    str_features = ""

    for feature in features:
        name = dict_server_features[feature] if feature in dict_server_features else feature
        str_features += f"{ic_bullet_point} {name}\n"

    return str_features


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UtilityCog(bot))
