"""This module contains template string constants to be used for database queries and commands
"""

INSERT_PROPERTY_QUERY = "INSERT OR REPLACE INTO configs VALUES(?, ?);"
GET_PROPERTY_QUERY = "SELECT val FROM configs WHERE config_key =?"
