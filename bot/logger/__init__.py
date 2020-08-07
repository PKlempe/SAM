"""Module for Logging functionality.
It exposes log and command_log.

'command_log' is a decorator to be used on command functions. It works on any function whose first argument is a
context object. It logs when a command is called by a user. Additional information include the calling user and channel.

log is a logger object used to log information on various levels in the code. The logs will be written to the stderr and
to a logfile. The path must be specified in the env file.

"""
from .logger import command_log, log
