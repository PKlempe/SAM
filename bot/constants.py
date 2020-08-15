"""File which contains constants used for this bot."""

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
SERVER_ID = 356078768953098240


# API Keys
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


# Bot Settings
BOT_PREFIX = '!'
INITIAL_EXTNS = {"AdminCog":        'bot.admin.admin',
                 "ModerationCog":   'bot.moderation.moderation',
                 "UniversityCog":   'bot.university.university',
                 "UtilitiesCog":    'bot.util.utilities'}


# Filepaths
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH") or '/logfile.log'

## SQLite Database
DB_FILE_PATH = os.getenv("DB_FILE_PATH")
DB_INIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persistence/resources/init_db.sql")


# Important URLs
URL_DISCORD = "https://discordapp.com"
URL_UFIND = "https://ufind.univie.ac.at/de"
URL_UFIND_API = "https://m-ufind.univie.ac.at"
URL_UFIND_LOGO = "https://blog.univie.ac.at/relaunch/wp-content/uploads/2016/07/ufind-1-300x130.png"
URL_HTTP_CAT = "https://http.cat"


# Embed Colors
EMBED_COLOR_INFO = 0xFFDF00
EMBED_COLOR_SYSTEM = 0xD1E231
EMBED_COLOR_UNIVERSITY = 0x1E90FF
EMBED_COLOR_SELECTION = 0xFF6700

EMBED_COLOR_MODMAIL_OPEN = 0xE60000
EMBED_COLOR_MODMAIL_ASSIGNED = 0xFF7800
EMBED_COLOR_MODMAIL_CLOSED = 0x4CBB17


# Discord Server Boosts
DISCORD_BOOST_LVL1_CAP = 2
DISCORD_BOOST_LVL2_CAP = 15
DISCORD_BOOST_LVL3_CAP = 30


# Special Role IDs
ROLE_ID_MODERATOR = 356080544670285825


# Special Channel IDs
CHANNEL_ID_BOT = 729066220627951757
CHANNEL_ID_MODMAIL = 729066220627951757


# Special User IDs
USER_ID_CONTRIBUTOR = 310100064687226882


# Special Emojis
EMOJI_AVAILABLE = "\U0001F7E2"
EMOJI_UNAVAILABLE = "\U0001F534"

EMOJI_MODMAIL_DONE = "\U00002705"
EMOJI_MODMAIL_ASSIGN = "\U0001F4DD"

ZERO_WIDTH_SPACE = "\U0000200B"
