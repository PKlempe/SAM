"""File which contains constants used for this bot."""

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Bot Settings
BOT_PREFIX = '!'
INITIAL_EXTNS = {"AdminCog": 'bot.admin.admin',
                 "CommunityCog": 'bot.community.community',
                 "RoleManagementCog": 'bot.role_management.role_management',
                 "ModerationCog": 'bot.moderation.moderation',
                 "UniversityCog": 'bot.university.university',
                 "UtilityCog": 'bot.utility.utility',
                 "MusicCog": 'bot.music.music'}

# Job Times
JOB_START_WINTER_SEMESTER = {"job_id": "ersti_ws", "day": "1", "month": "10", "hour": "4", "minute": "0"}
JOB_START_SUMMER_SEMESTER = {"job_id": "ersti_ss", "day": "1", "month": "3", "hour": "4", "minute": "0"}

JOB_OPEN_GROUP_EXCHANGE_WINTER_SEMESTER = {"job_id": "op_ex_ws", "day": "21", "month": "9", "hour": "4", "minute": "0"}
JOB_CLOSE_GROUP_EXCHANGE_WINTER_SEMESTER = {"job_id": "cl_ex_ws", "day": "1", "month": "11", "hour": "4", "minute": "0"}
JOB_OPEN_GROUP_EXCHANGE_SUMMER_SEMESTER = {"job_id": "op_ex_ss", "day": "20", "month": "2", "hour": "4", "minute": "0"}
JOB_CLOSE_GROUP_EXCHANGE_SUMMER_SEMESTER = {"job_id": "cl_ex_ss", "day": "1", "month": "4", "hour": "4", "minute": "0"}

# Important URLs
URL_DISCORD = "https://discordapp.com"
URL_UFIND = "https://ufind.univie.ac.at/de"
URL_UFIND_API = "https://m-ufind.univie.ac.at"
URL_UFIND_LOGO = "https://blog.univie.ac.at/relaunch/wp-content/uploads/2016/07/ufind-1-300x130.png"
URL_KOFI = "https://ko-fi.com/pklempe"
URL_KOFI_LOGO = "https://i.imgur.com/q0M4x4g.png"
URL_KOFI_DONATION = "https://ko-fi.com/home/coffeeshop?txid={0}&mode=public"
URL_HTTP_CAT = "https://http.cat"

# Limits
LIMIT_PINS = 10
LIMIT_HIGHLIGHT = 15
LIMIT_HIGHLIGHT_LOOKUP = 30
LIMIT_PURGE_MESSAGES = 200
LIMIT_NEW_MEMBERS = 24
LIMIT_NICKNAMES = 12

LIMIT_WARNINGS_LVL_1 = 3
LIMIT_WARNINGS_LVL_2 = 5
LIMIT_WARNINGS_LVL_3 = 6

LIMIT_COMMUNITY_CHANNELS = 20
LIMIT_SONG_QUEUE = 300

# Timeouts
TIMEOUT_USER_INTERACTION = 180
TIMEOUT_USER_SELECTION = 30
TIMEOUT_INFORMATION = 15

# Discord Server Boosts
DISCORD_BOOST_LVL1_CAP = 2
DISCORD_BOOST_LVL2_CAP = 7
DISCORD_BOOST_LVL3_CAP = 14

# Embed Colors
EMBED_COLOR_INFO = 0xFFDF00
EMBED_COLOR_SYSTEM = 0xD1E231
EMBED_COLOR_UNIVERSITY = 0x1E90FF
EMBED_COLOR_SELECTION = 0xFF6700
EMBED_COLOR_REPORT = 0xF01414
EMBED_COLOR_MODERATION = 0x5C2BE2
EMBED_COLOR_HOWTO = 0x6F2DA8

EMBED_COLOR_MODMAIL_OPEN = 0xE60000
EMBED_COLOR_MODMAIL_ASSIGNED = 0xFF7800
EMBED_COLOR_MODMAIL_CLOSED = 0x4CBB17

EMBED_COLOR_MODLOG_PURGE = 0x000000
EMBED_COLOR_MODLOG_REPEAL = 0xF5F50C
EMBED_COLOR_MODLOG_WARN = 0xFF9D00
EMBED_COLOR_MODLOG_KICK = 0xDC143C
EMBED_COLOR_MODLOG_MUTE = 0x34EBEB
EMBED_COLOR_MODLOG_BAN = 0xDC143C
EMBED_COLOR_MODLOG_LOCKDOWN = 0xFFFFFF

EMBED_COLOR_GROUP_EXCHANGE = 0xECFF00
EMBED_COLOR_BOTONLY = 0xFF7900
EMBED_COLOR_WARNING = 0xFF0000
EMBED_COLOR_DONATION = 0xFF5E5B
EMBED_COLOR_SUBSCRIPTION = 0xFBAA19

# Special Emojis
EMOJI_PIN = "\U0001F4CC"
EMOJI_HIGHLIGHT = "\U00002B50"

EMOJI_AVAILABLE = "\U0001F7E2"
EMOJI_UNAVAILABLE = "\U0001F534"

EMOJI_MODMAIL_DONE = "\U00002705"
EMOJI_MODMAIL_ASSIGN = "\U0001F4DD"

EMOJI_CONFIRM = "\U00002705"
EMOJI_CANCEL = "\U0000274C"

EMOJI_UPVOTE = "\U00002B06\U0000FE0F"
EMOJI_DOWNVOTE = "\U00002B07\U0000FE0F"

ZERO_WIDTH_SPACE = "\U0000200B"
EMOJI_CHANNEL_NAME_SEPARATOR = "\U0001F539"

# API Keys
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN") or "Undefined"

# File Paths
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH") or './logfile.log'
DB_FILE_PATH = os.getenv("DB_FILE_PATH") or "./database.sqlite3"
DB_INIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persistence/resources/init_db.sql")

# Special Discord IDs
SERVER_ID = os.getenv("SERVER_ID") or "Undefined"

## Category IDs
CATEGORY_ID_GAMING_ROOMS = os.getenv("CATEGORY_ID_GAMING_ROOMS") or "Undefined"
CATEGORY_ID_STUDY_ROOMS = os.getenv("CATEGORY_ID_STUDY_ROOMS") or "Undefined"

## Channel IDs
CHANNEL_ID_BOT = os.getenv("CHANNEL_ID_BOT") or "Undefined"
CHANNEL_ID_MODLOG = os.getenv("CHANNEL_ID_MODLOG") or "Undefined"
CHANNEL_ID_NEWS = os.getenv("CHANNEL_ID_NEWS") or "Undefined"
CHANNEL_ID_RULES = os.getenv("CHANNEL_ID_RULES") or "Undefined"
CHANNEL_ID_FAQ = os.getenv("CHANNEL_ID_FAQ") or "Undefined"
CHANNEL_ID_SUPPORTER = os.getenv("CHANNEL_ID_SUPPORTER") or "Undefined"
CHANNEL_ID_REPORT = os.getenv("CHANNEL_ID_REPORT") or "Undefined"
CHANNEL_ID_MODMAIL = os.getenv("CHANNEL_ID_MODMAIL") or "Undefined"
CHANNEL_ID_ROLES = os.getenv("CHANNEL_ID_ROLES") or "Undefined"
CHANNEL_ID_SUGGESTIONS = os.getenv("CHANNEL_ID_SUGGESTIONS") or "Undefined"
CHANNEL_ID_QUESTIONS = os.getenv("CHANNEL_ID_QUESTIONS") or "Undefined"
CHANNEL_ID_GROUP_EXCHANGE = os.getenv("CHANNEL_ID_GROUP_EXCHANGE") or "Undefined"
CHANNEL_ID_HIGHLIGHTS = os.getenv("CHANNEL_ID_HIGHLIGHTS") or "Undefined"

## Role IDs
ROLE_ID_MODERATOR = os.getenv("ROLE_ID_MODERATOR") or "Undefined"
ROLE_ID_MUTED = os.getenv("ROLE_ID_MUTED") or "Undefined"
ROLE_ID_ERSTI = os.getenv("ROLE_ID_ERSTI") or "Undefined"

## User IDs
USER_ID_CONTRIBUTOR = 310100064687226882
