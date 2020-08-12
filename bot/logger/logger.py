"""Module providing logging functionality.

Configures the logger for the discord library and the logger for custom project code.
It also provides the decorator for logging command calls.
"""
import functools
import logging
from logging.handlers import RotatingFileHandler

import discord
from discord.ext.commands import Command, Group

from bot import constants

# configure logger for bot
log = logging.getLogger("bot")
log.setLevel(logging.INFO)
file_handler = RotatingFileHandler(filename=constants.LOG_FILE_PATH, encoding='utf-8', mode='a',
                                   maxBytes=10 * 1024 * 1024)
file_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(message)s'))
log.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(message)s'))
log.addHandler(stream_handler)

# add discord to logging (file and console)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)
discord_logging_file_handler = RotatingFileHandler(filename=constants.LOG_FILE_PATH, encoding='utf-8', mode='a',
                                                   maxBytes=10 * 1024 * 1024)
discord_logging_file_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(name)s: %(message)s'))
discord_logger.addHandler(discord_logging_file_handler)
discord_logging_stream_handler = logging.StreamHandler()
discord_logging_stream_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s: %(name)s:  %(message)s'))
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
        msg = ctx.message.content
        command = ctx.command
        if is_deepest_subcommand(command, msg):
            user = ctx.author
            # full_command_name = f"{' '.join([c.name for c in command.parents][::-1])} {command.name}"
            full_command_name = str(ctx.command)
            channelname = 'direct message' if isinstance(ctx.channel, discord.DMChannel) else ctx.channel.name
            log.info("Command %s called by %s in channel %s ", full_command_name, user, channelname)

        await func(*args, **kwargs)

    return wrapper


def is_deepest_subcommand(command: Command, msg: str) -> bool:
    """Checks whether the passed command is the deepest subcommand called in the message.

        Args:
            command (Command): The command containing to be reviewed.
            msg (str): The message where the command was sent in.

        Returns:
            bool: true if it is the deepest command, false if there is yet uncalled deeper subcommand.
    """
    # remove prefix and make all lowercase
    msg = msg[1::].lower()
    # can only not be deepest if it is a group
    if isinstance(command, Group):
        sub_commands = command.commands
        # msg does not start with any of the subcommands of the evaluated command
        return not any(msg.startswith(str(sub_command).lower()) for sub_command in sub_commands)
    return True
