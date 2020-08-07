"""File which contains constants used for this bot."""

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
SERVER_ID = 356078768953098240

# API Keys
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Bot Settings
BOT_PREFIX = '!'

# Embed Colors
EMBED_COLOR_INFO = 0xFFDF00
EMBED_COLOR_UNIVERSITY = 0x1E90FF

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
CHANNEL_ID_MODMAIL = 729066220627951757

# Special User IDs
USER_ID_CONTRIBUTOR = 310100064687226882

# Special Emojis
EMOJI_MODMAIL_DONE = "\U00002705"
EMOJI_MODMAIL_ASSIGN = "\U0001F4DD"

# SQLite Database
DB_FILE_PATH = os.getenv("DB_FILE_PATH")
## Absolute path to the init script.
DB_INIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persistence/resources/init_db.sql")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH") or '/logfile.log'
URL_HTTP_CAT = "https://http.cat"
