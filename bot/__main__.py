"""This is the main module of the SAM project."""

from discord.ext import commands
from bot import constants

bot = commands.Bot(command_prefix=constants.BOT_PREFIX)
initial_extensions = ['bot.util.utilities']

@bot.event
async def on_ready():
    """Event handler for the Bot entering the ready state."""
    print('- {0.user} successfully logged in to Discord!'.format(bot))


if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    print("- Contacting Discord servers...")
    bot.run(constants.DISCORD_BOT_TOKEN)
