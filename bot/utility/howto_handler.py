"""Contains the handlers for the howto command"""

from typing import Optional

import discord
from discord.ext import commands

from bot import constants


def code():
    """Handler for the `howto code` command.

    Explains how to properly format code using discords code blocks (https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline-)

    """
    embed = discord.Embed(
        title="Code richtig formatieren",
        color=constants.EMBED_COLOR_INFO)
    embed.set_image(url="https://cdn.discordapp.com/attachments/858040409312591873/860573151724175400/howto_code.png")
    embed.add_field(
        name="Weitere Information:",
        value="Unter https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline- gibt es mehr Infos zu Discords Markdownsyntax"
    )
    return embed
