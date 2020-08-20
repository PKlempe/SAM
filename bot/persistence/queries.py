"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO MODMAIL (ID, Author, Timestamp) VALUES (?, ?, ?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ?"
GET_ALL_MODMAIL_WITH_STATUS = "SELECT ID, Author, Timestamp FROM Modmail WHERE StatusID = ?"

# GroupExchange
INSERT_GROUP_OFFER = "INSERT INTO GroupOffer (UserId, Course, GroupNr, MessageId) VALUES (?, ?, ?, ?)"
INSERT_GROUP_REQUEST = "INSERT INTO GroupRequest (UserId, Course, GroupNr) VALUES (?, ?, ?)"
UPDATE_GROUP_MESSAGE_ID = "UPDATE GroupOffer SET MessageId = ? WHERE UserId = ? AND Course = ?"
#needs to be formatted to have as many ? as there are group numbers for requested groups
FIND_GROUP_EXCHANGE_CANDIDATES = "SELECT DISTINCT offer.UserId, offer.MessageId " \
                                 "FROM GroupOffer offer INNER JOIN GroupRequest request " \
                                 "ON offer.Course = request.Course " \
                                 "AND offer.UserId = request.UserId " \
                                 "WHERE offer.UserId != ? " \
                                 "AND offer.Course = ? " \
                                 "AND request.GroupNr = ? " \
                                 "AND offer.GroupNr IN ({0})"
