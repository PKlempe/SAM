"""Contains logic for connecting to and manipulating the database.

Todo:
    * Add queries for db tables once the db design is clear.
"""

from sqlite3 import Error
from typing import List
from bot.moderation import ModmailStatus
from bot.persistence import queries
from .database_manager import DatabaseManager


class DatabaseConnector:
    """Class used to communicate with the database.

    The database is created and initialized using the __init__ method. The other methods support getting or adding
    properties to the database.
    """
    def __init__(self, db_file: str, init_script=None):
        """Create a database connection to a SQLite database and create the default tables form the SQL script in
        init_db.sql.

        Args:
            db_file (str): The filename of the SQLite database file.
            init_script (Optional[str]): Optional SQL script filename that will be run when the method is called.
        """
        if db_file is None:
            raise Error("Database filepath and/or filename hasn't been set.")

        self._db_file = db_file
        with DatabaseManager(self._db_file) as db_manager:
            if init_script is not None:
                queries_ = self.parse_sql_file(init_script)
                for query in queries_:
                    try:
                        db_manager.execute(query)
                    except Error as error:
                        print("Command could not be executed, skipping it: {0}".format(error))

    def add_config_property(self, key: str, val: str):
        """Adds a new configuration property to the database or updates an existing one if the key already exists.

        Args:
            key (str): The property key (must be unique among properties).
            val (str): The value of the property.

        Raises:
            Error: If the db __init__ method was not called before, as it sets the filename of the database file which
                is needed to operate on the db. This also ensures that the database exists and works, contains the table
                prior to calling this method.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.QUERY_INSERT_PROPERTY, (key, val))
            db_manager.commit()

    def get_property(self, key: str):
        """Searches the config table of the db for a specific property.

        Args:
            key (str): The property key to search for.

        Returns:
            Optional[str]: The property value for the specified key or `None` if it doesn't exist.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.QUERY_GET_PROPERTY, (key,))
            row = result.fetchone()
            if row is not None:
                return row[0]
            return None

    def add_modmail(self, msg_id: int):
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.QUERY_INSERT_MODMAIL, (msg_id,))
            db_manager.commit()

    def get_modmail_status(self, msg_id: int):
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.QUERY_GET_MODMAIL_STATUS, (msg_id,))
            db_manager.commit()

            row = result.fetchone()
            if row is not None:
                return ModmailStatus(row[0])
            return None

    def change_modmail_status(self, msg_id: int, status: ModmailStatus):
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.QUERY_CHANGE_MODMAIL_STATUS, (status.value, msg_id))
            db_manager.commit()

    @staticmethod
    def parse_sql_file(filename: str) -> List[str]:
        """Parses a SQL script to read all queries/commands it contains.

        Args:
            filename (str): The filename of the init file. Can also be a path.

        Returns:
            List[str]: A list of strings with each entry being a SQL query.
        """
        file = open(filename, 'r')
        sql_file = file.read()
        file.close()
        return sql_file.split(';')
