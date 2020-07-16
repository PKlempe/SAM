"""Context manager for managing database connections."""

import sqlite3
from sqlite3 import Error


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
    connection = None

    def __init__(self, db_file: str):
        """Initializes the context manager with the filename of the db.

        Args:
            db_file (str): the name (or path) to the db file
        """
        self.db_file = db_file
        self.connection = None

    def __enter__(self):
        """Entry method of the context manager.

        Opens the db connection using the `sqlite3` library.

        Returns:
            Connection: The database connection object.
        """
        try:
            self.connection = sqlite3.connect(self.db_file)
        except Error as error:
            print(error)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit method of the context manager.

        Closes the database connection after the code has been executed.

        Args:
            exc_type:
            exc_val:
            exc_tb:
        """
        if self.connection:
            self.connection.close()
