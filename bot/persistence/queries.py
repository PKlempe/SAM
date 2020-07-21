"""This module contains template string constants which will be used for database queries and commands."""

QUERY_INSERT_PROPERTY = "INSERT OR REPLACE INTO configs VALUES(?, ?);"
QUERY_GET_PROPERTY = "SELECT val FROM configs WHERE config_key = ?"

# Modmail
QUERY_INSERT_MODMAIL = "INSERT INTO MODMAIL (ID) VALUES (?)"
QUERY_CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
QUERY_GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
QUERY_GET_MODMAIL_OPEN = "SELECT ID FROM Modmail WHERE StatusID = ?"
