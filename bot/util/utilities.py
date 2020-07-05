from discord.ext import commands
from datetime import datetime, timedelta


class UtilitiesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send("\U0001F3D3 **Pong!** - {0} ms".format(latency))


def setup(bot):
    bot.add_cog(UtilitiesCog(bot))
