"""Context manager for managing database connections"""

import sqlite3
from sqlite3 import Error


class DatabaseManager():
    """Context Manager class allowing for simple and resilient accessing of the db.
    This class can be used as followed:

    with DatabaseManager("path/to/file.sqllite") as db:
        #do some db stuff with db object
        ...

    After the last line in the indented block is executed, the connection will be automatically
    close via the exit method
    """
    connection = None

    def __init__(self, db_file: str):
        """Initializes the context manager with the db file name

        Args:
            db_file: the name (or path) to the db file
        """
        self.db_file = db_file
        self.connection = None

    def __enter__(self):
        """Entry method of the context manager.
        Opens the db connection

        Returns: The database connection object
        """
        try:
            self.connection = sqlite3.connect(self.db_file)
        except Error as error:
            print(error)
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit method of the context manager
        Closes the database connection after the code has executed
        """
        if self.connection:
            self.connection.close()
