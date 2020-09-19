"""Contains logic for connecting to and manipulating the database."""

import datetime
from sqlite3 import Error
from typing import List, Optional, Iterator, Iterable

from bot.moderation import ModmailStatus
from bot.feedback import SuggestionStatus
from bot.persistence import queries
from .database_manager import DatabaseManager


class DatabaseConnector:
    """Class used to communicate with the database.

    The database is created and initialized using the __init__ method. The other methods support getting or adding
    properties to the database.
    """

    def __init__(self, db_file: str, init_script: Optional[str]):
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
            if init_script:
                queries_ = self.parse_sql_file(init_script)
                for query in queries_:
                    try:
                        db_manager.execute(query)
                    except Error as error:
                        print("Command could not be executed, skipping it: {0}".format(error))

    def add_member_warning(self, user_id: int, timestamp: datetime.datetime, reason: Optional[str]):
        """Adds a warning to the table "MemberWarning".

        Args:
            user_id (int): The id of the member who has been warned.
            timestamp (datetime.datetime): Timestamp representing the moment when the member was warned.
            reason (Optional[str]): The reason provided by the moderator why the member was warned.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MEMBER_WARNING, (user_id, timestamp, reason))
            db_manager.commit()

    def remove_member_warning(self, warning_id: int):
        """Removes the warning with the specified id from the table "MemberWarning".

        Args:
            warning_id (int): The id of the warning which should be removed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.DELETE_MEMBER_WARNING, (warning_id,))
            db_manager.commit()

    def remove_member_warnings(self, user_id: int):
        """Removes all warnings of a member from the table "MemberWarning".

        Args:
            user_id (int): The id of the member whose warnings should be removed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.DELETE_MEMBER_WARNINGS, (user_id,))
            db_manager.commit()

    def get_warning_userid(self, warning_id: int) -> Optional[int]:
        """Gets the id of the member which received the warning with the specified id.

        Args:
            warning_id (int): The id of warning whose receiver needs to be identified.

        Returns:
            Optional[int]: The id of the member who has been warned.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_WARNING_USERID, (warning_id,))

            row = result.fetchone()
            if row:
                return int(row[0])
            return None

    def get_member_warnings(self, user_id: int) -> Optional[List[tuple]]:
        """Gets all the warnings of a specific member.

        Args:
            user_id (int): The id of the member whose warnings have been requested.

        Returns:
            Optional[List[tuple]]: A list containing the id of the warning, the timestamp when it happened and the
                                   reason provided by the moderator.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_MEMBER_WARNINGS, (user_id,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

    def add_member_name(self, user_id: int, name: str, timestamp: datetime.datetime):
        """Adds a members old nickname to the table "MemberNameHistory".

        Args:
            user_id (int): The id of the member whose nickname has changed.
            name (str): The old nickname used before the change.
            timestamp (datetime.datetime): A timestamp representing when the nickname has been changed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MEMBER_NAME, (user_id, name, timestamp))
            db_manager.commit()

    def get_member_names(self, user_id: int) -> Optional[List[tuple]]:
        """Gets all the nicknames used by a member from the table "MemberNameHistory".

        Args:
            user_id (int): The id of the member whose nicknames have been requested.

        Returns:
            Optional[List[tuple]]: A list containing tuples consisting of the nickname and the timestamp representing
                                   when the name has been replaced.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_MEMBER_NAMES, (user_id,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

    def add_module_role(self, role_id: int):
        """Adds a role to the table "ModuleRole".

        Args:
            role_id (int): The id of the role which should be added.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MODULE_ROLE, (role_id,))
            db_manager.commit()

    def remove_module_role(self, role_id: int):
        """Removes a role from the table "ModuleRole".

        Args:
            role_id (int): The role id of the role which should be removed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_MODULE_ROLE, (role_id,))
            db_manager.commit()
            
    def check_module_role(self, role_id: int) -> bool:
        """Check if there's an entry for the specified role in the table "ModuleRole".

        Args:
            role_id (int): The id of the role which needs to be checked.

        Returns:
            bool: A boolean indicating if the role has been whitelisted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.CHECK_IF_MODULE_ROLE, (role_id,))
            
            row = result.fetchone()
            return bool(row[0])

    def get_reaction_role(self, msg_id: int, emoji: str) -> Optional[int]:
        """Gets the role id for the specified reaction on a specific message.

        Args:
            msg_id (int): The id of the message which has been reacted to.
            emoji (str): The emoji of the reaction.

        Returns:
            Optional[int]: The id of the role associated with the given message + reaction.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_REACTION_ROLE, (msg_id, emoji))

            row = result.fetchone()
            if row:
                return int(row[0])
            return None

    def add_reaction_role(self, msg_id: int, emoji: str, role_id: int):
        """Adds information needed for a reaction role to the table "ReactionRole".

        Args:
            msg_id (int): The id of the message which users should react to.
            emoji (str): The emoji for the reaction role.
            role_id (int): The id of the role for the reaction role.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_REACTION_ROLE, (msg_id, emoji, role_id))
            db_manager.commit()

    def remove_reaction_role(self, msg_id: int, emoji: str):
        """Removes information needed for a reaction role from the table "ReactionRole".

        Args:
            msg_id (int): The id of the message which users should react to.
            emoji (str): The emoji for the specific reaction role.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_REACTION_ROLE, (msg_id, emoji))
            db_manager.commit()

    def clear_reaction_roles(self, msg_id: int) -> bool:
        """Removes all information needed for the reaction roles of a specific message from the table "ReactionRole".

        Args:
            msg_id (int): The id of the message which reaction roles should be removed.

        Returns:
            bool: A boolean indicating if any reaction roles have been deleted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            affected_rows = db_manager.execute(queries.CLEAR_REACTION_ROLES, (msg_id,)).rowcount
            db_manager.commit()

            return affected_rows != 0

    def add_reaction_role_uniqueness_group(self, msg_id: int):
        """Adds the id of a message to the table "ReactionRoleGroup".

        The existence of a message id in this table indicates, that a user should only be able to have one of the
        specified reaction roles of a message at any time given.

        Args:
            msg_id (int): The id of the message which users can react to.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_REACTION_ROLE_UNIQUENESS_GROUP, (msg_id,))
            db_manager.commit()

    def remove_reaction_role_uniqueness_group(self, msg_id: int):
        """Removes the id of a message from the table "ReactionRoleGroup".

        The absence of a message id in this table indicates, that a user can have multiple reaction roles of this
        message at once.

        Args:
            msg_id (int): The id of the message which users can react to.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_REACTION_ROLE_UNIQUENESS_GROUP, (msg_id,))
            db_manager.commit()

    def is_reaction_role_uniqueness_group(self, msg_id: int) -> bool:
        """Checks if the reaction roles of a message have been declared as unique.

        If yes, this means that a user can only have one of these roles at any time given.

        Args:
            msg_id (int): The id of the message which users can react to.

        Returns:
            bool: A boolean indicating if the reaction roles of a message have been declared as unique.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.IS_REACTION_ROLE_UNIQUE, (msg_id,))

    def add_suggestion(self, author_id: int, timestamp: datetime.datetime) -> int:
        """Adds a suggestion to the table "Suggestion".

        Args:
            author_id (int): The id of the user who submitted the suggestion.
            timestamp (datetime.datetime): A timestamp when this suggestion has been submitted.

        Returns:
            int: The row id of the new entry.
        """
        with DatabaseManager(self._db_file) as db_manager:
            row_id = db_manager.execute(queries.INSERT_SUGGESTION, (author_id, timestamp)).lastrowid
            db_manager.commit()

            return row_id

    def set_suggestion_message_id(self, suggestion_id: int, message_id: int):
        """Sets the message id of a specific suggestion.

        Args:
            suggestion_id (int): The id of the suggestion.
            message_id (int): The message id of the embed posted in the suggestion channel.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.SET_SUGGESTION_MESSAGE_ID, (message_id, suggestion_id))
            db_manager.commit()

    def get_suggestion(self, suggestion_id: int) -> Optional[tuple]:
        """Gets data regarding a suggestion with the specified id.

        Args:
            suggestion_id (int): The id of the suggestion.

        Returns:
            tuple: A tuple containing MessageID, StatusID and AuthorID of a suggestion in the table "Suggestion".
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_SUGGESTION_BY_ID, (suggestion_id,))

            row = result.fetchone()
            if row:
                return row
            return None

    def get_suggestion_status(self, message_id: int) -> Optional[SuggestionStatus]:
        """Gets the status of a suggestion with the specified message id.

        Args:
            message_id (int): The id of the message containing the suggestion embed.

        Returns:
            SuggestionStatus: The status of the suggestion.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_SUGGESTION_STATUS, (message_id,))

            row = result.fetchone()
            if row:
                return SuggestionStatus(row[0])
            return None

    def set_suggestion_status(self, suggestion_id: int, status: SuggestionStatus) -> bool:
        """Sets the status of a suggestion with the specified id.

        Args:
            suggestion_id (int): The id of the suggestion.
            status (SuggestionStatus): The new status of the suggestion.

        Returns:
            bool: A boolean representing if any rows have been changed
        """
        with DatabaseManager(self._db_file) as db_manager:
            affected_rows = db_manager.execute(queries.SET_SUGGESTION_STATUS, (status.value, suggestion_id)) \
                .rowcount
            db_manager.commit()
            return affected_rows != 0

    def get_all_suggestions_with_status(self, status: SuggestionStatus) -> Optional[List[tuple]]:
        """Gets data about all suggestions with the specified status.

        Args:
            status (SuggestionStatus): The status which the suggestions should have.

        Returns:
            Optional[List[tuple]]: A list containing data of all suggestions with the specified status.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_ALL_SUGGESTIONS_WITH_STATUS, (status.value,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

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
            if row:
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

    def add_group_offer_and_requests(self, user_id: str,
                                     course: str,
                                     offered_group: int,
                                     requested_groups: Iterator[int]):
        """Adds new offer and requests for a course and a group.

        Args:
            user_id (str): The user id of the offering user.
            course (str): The course for which the offer is.
            offered_group (str): The group that the user offers.
            requested_groups (List[str]): List of all groups the user would accept.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_GROUP_OFFER, (user_id, course, offered_group))
            for group_nr in requested_groups:
                db_manager.execute(queries.INSERT_GROUP_REQUEST, (user_id, course, group_nr))
            db_manager.commit()

    def update_group_exchange_message_id(self, user_id: str,
                                         course: str,
                                         message_id: str):
        """Updates the message id in the GroupOffer table from 'undefined' to a valid value

        This function is necessary because the message_id can only be retrieved after the embed is sent, which happens
        after inserting in the db, to ensure constraints are fulfilled.

        Args:
            user_id (str): The user_id of the requesting user.
            course (str): The course that should be exchanged.
            message_id (str): The id of the message that contains the group exchange embed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.UPDATE_GROUP_MESSAGE_ID, (message_id, user_id, course))
            db_manager.commit()

    def get_candidates_for_group_exchange(self, author_id,
                                          course: str,
                                          offered_group: int,
                                          requested_groups: Iterable[int]):
        """Gets all possible candidates for a group exchange offer.

        Args:
            author_id (str): The id of the author of the request.
            course (str): The course for which the candidates are searched.
            offered_group (int): The group that the user offers.
            requested_groups (Iterable[int]): The groups that the user requests.

        Returns:
            (Tuple[str, str]): UserId and MessageId of potential group exchange candidates.
        """
        with DatabaseManager(self._db_file) as db_manager:
            parameter_list = [author_id, course, offered_group] + list(requested_groups)
            result = db_manager.execute(
                queries.FIND_GROUP_EXCHANGE_CANDIDATES.format(', '.join('?' for _ in requested_groups)),
                tuple(parameter_list)
            )
            rows = result.fetchall()
            if rows:
                return rows
            return None

    def get_group_exchange_message(self, user_id: str, course: str):
        """Gets message id for a the request of a user for a specific course.

        Args:
            user_id (str): The id of the author of the request.
            course (str): The id of the channel referring to the course.

        Returns:
            (str): The id of the message containing the request.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_GROUP_EXCHANGE_MESSAGE, (user_id, course))

            rows = result.fetchone()
            if rows:
                return rows[0]
            return None

    def remove_group_exchange_offer(self, user_id: str, course: str):
        """Removes all entries of a group exchange offer and request for a user.

        Args:
            user_id (str): The user for which the request and offer should be deleted.
            course (str): The channel_id refering to the course for which the entries should be deleted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_GROUP_EXCHANGE_OFFER, (user_id, course))
            db_manager.execute(queries.REMOVE_GROUP_EXCHANGE_REQUESTS, (user_id, course))
            db_manager.commit()

    def is_botonly(self, channel):
        """Runs a query checking if a channel is marked as botonly in the db.

        Args:
            channel (discord.TextChannel): The channel to be queried.

        Returns:
            bool: true if the channel is botonly, false if not or no entry is found
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.IS_CHANNEL_BOTONLY, (channel.id,))

            rows = result.fetchone()
            if rows:
                return rows[0]
            return 0

    def activate_botonly(self, channel):
        """Executes a query that enables bot-only mode for a channel.

        Args:
            channel (discord.TextChannel): The channel to be made bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.ACTIVATE_BOTONLY_FOR_CHANNEL, (channel.id,))
            db_manager.commit()

    def deactivate_botonly(self, channel):
        """Executes a query that disables bot-only for a channel.

        Args:
            channel (discord.TextChannel): The channel to be made not bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.DEACTIVATE_BOTONLY_FOR_CHANNEL, (channel.id,))
            db_manager.commit()

    def get_group_exchange_for_user(self, user_id: int):
        """Executes a query to get all group exchange requests for a user.

        Args:
            user_id (int): The user id of the user.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_GROUP_EXCHANGE_FOR_USER, (user_id,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

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
