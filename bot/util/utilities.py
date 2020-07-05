"""Contains a cog for all utility funcionality"""
from discord.ext import commands


class UtilitiesCog(commands.Cog):
    """Cog for utility functions"""

    def __init__(self, bot):
        """Initializes the Cog"""
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        """
        Command Handler for the Ping Command
        Responds with a message containing 'Pong!'
        """
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send("\U0001F3D3 **Pong!** - {0} ms".format(latency))


def setup(bot):
    """Activates the cog to the bot."""
    bot.add_cog(UtilitiesCog(bot))
