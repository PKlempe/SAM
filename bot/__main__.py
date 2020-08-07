"""This is the main module of the SAM project."""

import asyncio
import traceback

import discord
import requests
from discord.ext import commands

from bot import constants
from .logger import log

bot = commands.Bot(command_prefix=constants.BOT_PREFIX)
initial_extensions = ['bot.util.utilities',
                      'bot.moderation.moderation']


@bot.event
async def on_ready():
    """Event handler for the Bot entering the ready state."""
    print('- {0.user} successfully logged in to Discord!'.format(bot))


@bot.event
async def on_disconnect():
    """Event handler for when the Bot disconnects from Discord."""
    print('- {0.user} has disconnected.'.format(bot))


@bot.event
async def on_command_error(ctx, exception):
    """Event handler for errors in command functions.

        Args:
            ctx (discord.Context): The context of the failing command.
            exception (exception): The exception that was thrown.
    """
    channelname = 'direct message' if isinstance(ctx.channel, discord.DMChannel) else ctx.channel.name
    log.error(
        "Exception while calling command. Message was: %s by %s in channel %s",
        ctx.message.content,
        ctx.message.author,
        channelname)

    ex = traceback.format_exception(type(exception), exception, exception.__traceback__)
    log.error(''.join(ex))

    if isinstance(exception.original, asyncio.TimeoutError):
        await ctx.send("Du konntest dich wohl nicht entscheiden. Kein Problem, du kannst es einfach später nochmal "
                       "versuchen. :smile:")
    elif isinstance(exception.original, requests.HTTPError):
        status_code = exception.original.response.status_code
        reason = exception.original.response.reason

        embed = discord.Embed(title="HTTP Error: {0}".format(status_code), description=reason,
                              image=constants.URL_HTTP_CAT + "/{0}.jpg".format(status_code))
        await ctx.channel.send(content="Oh, oh. Anscheinend gibt es momentan ein Verbindungsproblem:", embed=embed)


if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    print("- Contacting Discord servers...")
    bot.run(constants.DISCORD_BOT_TOKEN)
