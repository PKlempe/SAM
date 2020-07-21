"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO MODMAIL (ID) VALUES (?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
GET_OPEN_MODMAILS = "SELECT ID FROM Modmail WHERE StatusID = ?"
