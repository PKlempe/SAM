"""Context manager for managing database connections."""

import sqlite3
from sqlite3 import Error

from bot.persistence.in_memory_db import get_in_memory_connection
from bot.logger import log


class DatabaseManager:
    """Context Manager class allowing for simple and resilient access to the db.

    Example:
        This class can be used as followed:

            with DatabaseManager("path/to/file.sqllite") as db:
                # Do some db stuff with db object
                ...

        After the last line in the indented block is executed, the connection will be automatically closed via the exit
        method.
    """
    def __init__(self, db_file: str):
        """Initializes the context manager with the filename of the db.

        Args:
            db_file (str): the name (or path) to the db file
        """
        self._db_file = db_file
        self.connection = None
        self.is_in_memory = self._db_file == ':memory:'

    def __enter__(self):
        """Entry method of the context manager.

        Opens the db connection using the `sqlite3` library. If the database is an in-memory database and the connection has not yet been used, it will
        establish one, otherwise reuse an existing one.

        Returns:
            Connection: The database connection object.
        """
        if self.is_in_memory:
            self.connection = get_in_memory_connection()
        else:
            try:
                self.connection = sqlite3.connect(self._db_file)
            except Error as error:
                log.error(error)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit method of the context manager.

        Closes the database connection after the code has been executed, if the database is not an in-memory-database.

        Args:
            exc_type:
            exc_val:
            exc_tb:
        """
        if self.connection and not self.is_in_memory:
            self.connection.close()
