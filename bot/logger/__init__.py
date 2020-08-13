"""Package for Logging functionality.
It exposes log and command_log.

It exposes log and command_log. The 'command_log' decorator should be used on methods regarding bot commands.
It therefore works on any method whose first argument is a context object. It creates a log entry every time a command
is called by a user. Additional information include the user who invoked the command and the corresponding channel.

The object log is is a logger object used to log information on various levels in the code. The logs will be written
to the stderr and to a logfile which path must be specified in the .env file.
"""
from .logger import command_log, log