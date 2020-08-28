"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO MODMAIL (ID, Author, Timestamp) VALUES (?, ?, ?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
GET_ALL_MODMAIL_WITH_STATUS = "SELECT ID, Author, Timestamp FROM Modmail WHERE StatusID = ?"


# Module Roles
INSERT_MODULE_ROLE = "INSERT INTO ModuleRole (RoleID) VALUES (?)"
REMOVE_MODULE_ROLE = "DELETE FROM ModuleRole WHERE RoleID =  ?"


# GroupExchange
INSERT_GROUP_OFFER = "INSERT INTO GroupOffer (UserId, Course, GroupNr) VALUES (?, ?, ?)"
INSERT_GROUP_REQUEST = "INSERT INTO GroupRequest (UserId, Course, GroupNr) VALUES (?, ?, ?)"
UPDATE_GROUP_MESSAGE_ID = "UPDATE GroupOffer SET MessageId = ? WHERE UserId = ? AND Course = ?"

# needs to be formatted to have as many ? as there are group numbers for requested groups
FIND_GROUP_EXCHANGE_CANDIDATES = "SELECT DISTINCT offer.UserId, offer.MessageId, offer.GroupNr " \
                                 "FROM GroupOffer offer INNER JOIN GroupRequest request " \
                                 "ON offer.Course = request.Course " \
                                 "AND offer.UserId = request.UserId " \
                                 "WHERE offer.UserId != ? " \
                                 "AND offer.Course = ? " \
                                 "AND request.GroupNr = ? " \
                                 "AND offer.GroupNr IN ({0})"

GET_GROUP_EXCHANGE_MESSAGE = "SELECT MessageId FROM GroupOffer WHERE UserId = ? AND Course = ?"
REMOVE_GROUP_EXCHANGE_OFFER = "DELETE FROM GroupOffer WHERE UserId = ? AND Course = ?"
REMOVE_GROUP_EXCHANGE_REQUESTS = "DELETE FROM GroupRequest WHERE UserId = ? AND Course = ?"
GET_GROUP_EXCHANGE_FOR_USER = "SELECT DISTINCT offer.Course, offer.MessageId, offer.GroupNr, group_concat(request.GroupNr, ',') " \
                              "FROM GroupOffer offer INNER JOIN GroupRequest request " \
                              "ON offer.Course = request.Course " \
                              "AND offer.UserId = request.UserId " \
                              "WHERE offer.UserId = ? " \
                              "GROUP BY offer.Course"

# These queries are ridiculously dangerous. Use with caution.
CLEAR_GROUP_EXCHANGE_OFFERS = "DELETE FROM GroupOffer"
CLEAR_GROUP_EXCHANGE_REQUESTS = "DELETE FROM GroupRequest"


# Bot-only Mode
IS_CHANNEL_BOTONLY = "SELECT EXISTS(SELECT 1 FROM BotOnlyChannels WHERE ChannelID = ?)"
ACTIVATE_BOTONLY_FOR_CHANNEL = "INSERT INTO BotOnlyChannels (ChannelID) VALUES (?)"
DEACTIVATE_BOTONLY_FOR_CHANNEL = "DELETE FROM BotOnlyChannels WHERE ChannelID =  ?"
