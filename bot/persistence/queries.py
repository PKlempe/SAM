"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO MODMAIL (ID, Author, Timestamp) VALUES (?, ?, ?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
GET_ALL_MODMAIL_WITH_STATUS = "SELECT ID, Author, Timestamp FROM Modmail WHERE StatusID = ?"

#botonly
IS_CHANNEL_BOTONLY = "SELECT EXISTS(SELECT 1 FROM BotOnlyChannels WHERE Channel = ?)"
ACTIVATE_BOTONLY_FOR_CHANNEL = "INSERT INTO BotOnlyChannels (Channel) VALUES (?)"
DEACTIVATE_BOTONLY_FOR_CHANNEL = "DELETE FROM BotOnlyChannels WHERE Channel =  ?"
