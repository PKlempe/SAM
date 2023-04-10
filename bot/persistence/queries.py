"""This module contains template string constants which will be used for database queries and commands."""

# Modmail
INSERT_MODMAIL = "INSERT INTO Modmail (ID, Author, Timestamp) VALUES (?, ?, ?)"
CHANGE_MODMAIL_STATUS = "UPDATE Modmail SET StatusID = ? WHERE ID = ?"
GET_MODMAIL_STATUS = "SELECT StatusID FROM Modmail WHERE ID = ? LIMIT 1"
GET_ALL_MODMAIL_WITH_STATUS = "SELECT ID, Author, Timestamp FROM Modmail WHERE StatusID = ?"


# Module/Course Roles
INSERT_MODULE_ROLE = "INSERT INTO ModuleRole (RoleID) VALUES (?)"
REMOVE_MODULE_ROLE = "DELETE FROM ModuleRole WHERE RoleID = ?"
CHECK_IF_MODULE_ROLE = "SELECT EXISTS(SELECT 1 FROM ModuleRole WHERE RoleID = ?)"

INSERT_COURSE_ROLE = "INSERT INTO CourseRole (RoleID, CourseID) VALUES (?, ?)"
REMOVE_COURSE_ROLE = "DELETE FROM CourseRole WHERE RoleID = ?"
GET_COURSE_ROLE = "SELECT RoleID FROM CourseRole WHERE CourseID = ?"


# Reaction Roles
GET_REACTION_ROLE = "SELECT RoleID FROM ReactionRole WHERE MessageID = ? AND Emoji = ? LIMIT 1"
INSERT_REACTION_ROLE = "INSERT INTO ReactionRole (MessageID, Emoji, RoleID) VALUES (?,?,?)"
REMOVE_REACTION_ROLE = "DELETE FROM ReactionRole WHERE MessageID = ? AND Emoji = ?"
CLEAR_REACTION_ROLES = "DELETE FROM ReactionRole WHERE MessageID = ?"
INSERT_REACTION_ROLE_UNIQUENESS_GROUP = "INSERT INTO ReactionRoleUniquenessGroup (MessageID) VALUES (?)"
REMOVE_REACTION_ROLE_UNIQUENESS_GROUP = "DELETE FROM ReactionRoleUniquenessGroup WHERE MessageID = ?"
IS_REACTION_ROLE_UNIQUE = "SELECT EXISTS(SELECT 1 FROM ReactionRoleUniquenessGroup WHERE MessageID = ?)"


# Member Warnings
INSERT_MEMBER_WARNING = "INSERT INTO MemberWarning (UserID, Timestamp, Reason) VALUES (?, ?, ?)"
DELETE_MEMBER_WARNING = "DELETE FROM MemberWarning WHERE ID = ?"
DELETE_MEMBER_WARNINGS = "DELETE FROM MemberWarning WHERE UserID = ?"
GET_WARNING_USERID = "SELECT UserID FROM MemberWarning WHERE ID = ? LIMIT 1"
GET_MEMBER_WARNINGS = "SELECT ID, Timestamp, Reason FROM MemberWarning WHERE UserID = ?"


# Group Exchange
INSERT_GROUP_OFFER = "INSERT INTO GroupOffer (UserId, Course, GroupNr) VALUES (?, ?, ?)"
INSERT_GROUP_REQUEST = "INSERT INTO GroupRequest (UserId, Course, GroupNr) VALUES (?, ?, ?)"
UPDATE_GROUP_MESSAGE_ID = "UPDATE GroupOffer SET MessageId = ? WHERE UserId = ? AND Course = ?"

## needs to be formatted to have as many ? as there are group numbers for requested groups
FIND_GROUP_EXCHANGE_CANDIDATES = "SELECT DISTINCT offer.UserId, offer.MessageId, offer.GroupNr " \
                                 "FROM GroupOffer offer INNER JOIN GroupRequest request " \
                                 "ON offer.Course = request.Course " \
                                 "AND offer.UserId = request.UserId " \
                                 "WHERE offer.UserId != ? " \
                                 "AND offer.Course = ? " \
                                 "AND request.GroupNr = ? " \
                                 "AND offer.GroupNr IN ({0})"

GET_GROUP_EXCHANGE_MESSAGE = "SELECT MessageId FROM GroupOffer WHERE UserId = ? AND Course = ? LIMIT 1"
REMOVE_GROUP_EXCHANGE_OFFER = "DELETE FROM GroupOffer WHERE UserId = ? AND Course = ?"
REMOVE_GROUP_EXCHANGE_REQUESTS = "DELETE FROM GroupRequest WHERE UserId = ? AND Course = ?"
GET_GROUP_EXCHANGE_FOR_USER = "SELECT DISTINCT offer.Course, offer.MessageId, offer.GroupNr, group_concat(request.GroupNr, ',') " \
                              "FROM GroupOffer offer INNER JOIN GroupRequest request " \
                              "ON offer.Course = request.Course " \
                              "AND offer.UserId = request.UserId " \
                              "WHERE offer.UserId = ? " \
                              "GROUP BY offer.Course"

## These queries are ridiculously dangerous. Use with caution.
CLEAR_GROUP_EXCHANGE_OFFERS = "DELETE FROM GroupOffer"
CLEAR_GROUP_EXCHANGE_REQUESTS = "DELETE FROM GroupRequest"


# Bot-only Mode
IS_CHANNEL_BOTONLY = "SELECT EXISTS(SELECT 1 FROM BotOnlyChannel WHERE ChannelID = ?)"
ACTIVATE_BOTONLY_FOR_CHANNEL = "INSERT INTO BotOnlyChannel (ChannelID) VALUES (?)"
DEACTIVATE_BOTONLY_FOR_CHANNEL = "DELETE FROM BotOnlyChannel WHERE ChannelID = ?"


# Moderation
INSERT_MEMBER_NAME = "INSERT INTO MemberNameHistory (UserID, Name, Timestamp) VALUES (?, ?, ?)"
GET_MEMBER_NAMES = "SELECT Name, Timestamp FROM MemberNameHistory WHERE UserID = ? ORDER BY ROWID DESC"
