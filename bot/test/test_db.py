"""Tests for the database and other persistence classes."""

import os
from bot import constants
from bot.moderation import ModmailStatus
from bot.persistence import DatabaseConnector


def test_db():
    """Tests if inserts and reads from the database work.

    Initializes the database, adds a single value, queries the same value by key and finally deletes the db file.
    Passes if the returned value is found (ie. not None) and equal to the original one.
    """
    conn = DatabaseConnector("./test.sqlite", init_script=constants.DB_INIT_SCRIPT)
    conn.add_modmail(47348382920304934)
    res = conn.get_modmail_status(47348382920304934)

    os.remove("./test.sqlite")

    assert res == ModmailStatus.OPEN.value
