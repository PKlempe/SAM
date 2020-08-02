"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO MODMAIL (ID, Author, Timestamp) VALUES (?, ?, ?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
GET_ALL_MODMAIL_WITH_STATUS = "SELECT ID, Author, Timestamp FROM Modmail WHERE StatusID = ?"
