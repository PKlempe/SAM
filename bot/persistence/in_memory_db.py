"""Script containing global database connection which will only be instantiated in case of using an in-memory database."""


#global database connection, only used in case of in-memory database.
import sqlite3

_in_memory_connection = None


def get_in_memory_connection():
    global _in_memory_connection
    if _in_memory_connection is not None:
        return _in_memory_connection
    else:
        _in_memory_connection = sqlite3.connect(':memory:')
    return _in_memory_connection

