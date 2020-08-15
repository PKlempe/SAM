"""Contains logic for connecting to and manipulating the database."""

import datetime
from sqlite3 import Error
from typing import List, Optional

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

    def add_modmail(self, msg_id: int, author: str, timestamp: datetime.datetime):
        """Inserts the username of the author and the message id of a submitted modmail into the database and
        sets its status to `Open`.

        Args:
            msg_id (int): The message id of the modmail which has been submitted.
            author (str): The username with the discriminator of the author.
            timestamp (datetime.datetime): A timestamp representing the moment when the message has been submitted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MODMAIL, (msg_id, author, timestamp))
            db_manager.commit()

    def get_modmail_status(self, msg_id: int) -> Optional[ModmailStatus]:
        """Returns the current status of a modmail associated with the message id given.

        Args:
            msg_id (int): The message id of the modmail.

        Returns:
            Optional[ModmailStatus]: The current status of the modmail.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_MODMAIL_STATUS, (msg_id,))

            row = result.fetchone()
            if row is not None:
                return ModmailStatus(row[0])
            return None

    def change_modmail_status(self, msg_id: int, status: ModmailStatus):
        """Changes the status of a specific modmail with the given id.

        Args:
            msg_id (int): The message id of the modmail.
            status (ModmailStatus): The new status which should be set.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.CHANGE_MODMAIL_STATUS, (status.value, msg_id))
            db_manager.commit()

    def get_all_modmail_with_status(self, status: ModmailStatus) -> Optional[List[tuple]]:
        """Returns the message id of every modmail with the specified status.

        Args:
            status (ModmailStatus): The status to look out for.

        Returns:
            Optional[List[tuple]]: A list of all modmails with the the status specified.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_ALL_MODMAIL_WITH_STATUS, (status.value,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

    def is_botonly(self, channel):
        """Runs a query checking if a channel is marked as botonly in the db.

        Args:
            channel (discord.TextChannel): The channel to be queried.

        Returns:
            bool: true if the channel is botonly, false if not or no entry is found
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.IS_BOTONLY, (channel.name,))
            rows = result.fetchone()
            if rows:
                return rows[0]
            return 0


    def enable_botonly(self, channel):
        """Executes a query that adds the channel as bot-only.

        Args:
            channel (discord.TextChannel): The channel to be made bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.ENABLE_BOTONLY, (channel.name,))
            db_manager.commit()

    def disable_botonly(self, channel):
        """Executes a query that adds the channel as not bot-only.

        Args:
            channel (discord.TextChannel): The channel to be made not bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.DISABLE_BOTONLY, (channel.name,))
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
