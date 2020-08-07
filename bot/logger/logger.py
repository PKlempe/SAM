"""Logger Module. Configures the logger for the discord library and the logger for custom code.
It also provides the decorator for logging command calls.
"""
import functools
import logging

import discord

from bot import constants

# configure logger for bot
log = logging.getLogger("bot")
log.setLevel(logging.INFO)
file_handler = logging.FileHandler(filename=constants.LOG_FILE_PATH, encoding='utf-8', mode='w')
file_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(message)s'))
log.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(message)s'))
log.addHandler(stream_handler)

# add discord to logging (file and console)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)
discord_logging_file_handler = logging.FileHandler(filename=constants.LOG_FILE_PATH, encoding='utf-8', mode='w')
discord_logging_file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_logging_file_handler)
discord_logging_stream_handler = logging.StreamHandler()
discord_logging_stream_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_logging_stream_handler)


def command_log(func):
    """Decorator to log when a command is triggered.
    If a command function is annotated with '@command_log' it will automatically log if it is called, by whom and in
    which channel. Ensure that command_log is the last annotation on the function as it needs to be evaluated before
    the discord annotations and the evaluation order is from bottom up.

    Example:
        @command(name='ping')
        @command_log
        def ping(ctx):
            ...

    Args:
        func (function): The function that was called.

    Returns:
        (function): a wrapper function that will be called before the acutal function is invoked.
    """

    @functools.wraps(func)  # Important to preserve name because `command` uses it
    async def wrapper(*args, **kwargs):
        ctx = args[1]
        user = ctx.author
        channelname = 'direct message' if isinstance(ctx.channel, discord.DMChannel) else ctx.channel.name
        log.info("Command %s called by %s in channel %s ", func.__name__, user, channelname)
        await func(*args, **kwargs)

    return wrapper
