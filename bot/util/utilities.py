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


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UtilitiesCog(bot))
