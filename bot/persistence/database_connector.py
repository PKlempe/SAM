"""Contains logic for connecting to and manipulating the database.

Todo:
    * add queries for db tables once, the tables are clear
"""

from sqlite3 import Error
from typing import List, Union
from .queries import INSERT_PROPERTY_QUERY, GET_PROPERTY_QUERY
from .database_manager import DatabaseManager


class DatabaseConnector():
    """Class used to communicate with the database.

    The database is created and initialized with, using the __init__ method
    The other methods support getting or adding properties to the database.
    """

    _db_file: Union[str, None] = None

    def __init__(self, db_file: str, init_script=None):
        """Create a database connection to a SQLite database and create the default tables form the SQL script in
        init_db.sql.

        Args:
            db_file (str): The filename of the SQLite database file.
            init_script (Union[str, None]): Optional SQL script filename that
                will be run when the method is called.
        """
        self._db_file = db_file
        with DatabaseManager(self._db_file) as db_manager:
            if init_script is not None:
                queries = self.parse_sql_file(init_script)
                for query in queries:
                    try:
                        db_manager.execute(query)
                    except Error as error:
                        print("command could not be executed, skipping it: {0}".format(error))

    def add_config_property(self, key: str, val: str):
        """Adds a new configuration property to the database or updates an
        existing if the key already exists.

        Args:
            key (str): The property key (must be unique among properties).
            val (str): The value of the property.

        Raises:
            Error: If the db __init__ method was not called before, as it sets the filename of the database
            file which is needed to operate on the db. This also ensures that the database exists and works, contains
            the table prior to calling this method.
        """
        if self._db_file is None:
            raise Error(
                "Method __init__(filename, init_script=None) has not yet been called. Database filename is not set.")
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(INSERT_PROPERTY_QUERY, (key, val))
            db_manager.commit()

    def get_property(self, key: str):
        """Searches the config table of the db for a specific property.

        Args:
            key (str): The property key to search for.

        Returns:
            Union[str, None]: the property value for the specified key or None
            if it does not exist.
        """
        if self._db_file is None:
            raise Error(
                "Method __init__(filename, init_script=None) has not yet been called. Database filename is not set.")

        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(GET_PROPERTY_QUERY, (key,))
            row = result.fetchone()
            if row is not None:
                return row[0]
            return None

    @staticmethod
    def parse_sql_file(filename: str) -> List[str]:
        """Parses a SQL script to read all queries/commands it contains.

        Args:
            filename (str): the filename of the init file. Can also be a path.

        Returns:
            List[str]: A list of strings with each entry being a SQL-query.
        """
        file = open(filename, 'r')
        sql_file = file.read()
        file.close()
        return sql_file.split(';')
