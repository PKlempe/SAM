"""This is the main module of the SAM project."""

from discord.ext import commands
from bot import constants

bot = commands.Bot(command_prefix=constants.BOT_PREFIX)
initial_extensions = ['bot.moderation.moderation',
                      'bot.university.university',
                      'bot.util.utilities']


@bot.event
async def on_ready():
    """Event handler for the Bot entering the ready state."""
    print('- {0.user} successfully logged in to Discord!'.format(bot))


@bot.event
async def on_disconnect():
    """Event handler for when the Bot disconnects from Discord."""
    print('- {0.user} has disconnected.'.format(bot))


if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    print("- Contacting Discord servers...")
    bot.run(constants.DISCORD_BOT_TOKEN)
