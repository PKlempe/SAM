"""This is the main module of the SAM project."""

from discord.ext import commands
import settings

bot = commands.Bot(command_prefix=settings.BOT_PREFIX)
initial_extensions = ['bot.util.utilities']

@bot.event
async def on_ready():
    print('- {0.user} successfully logged in to Discord!'.format(bot))


if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

    print("- Contacting Discord servers...")
    bot.run(settings.DISCORD_BOT_TOKEN)
