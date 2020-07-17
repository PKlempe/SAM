"""File which contains constants used for this bot."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# API Keys
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Bot Settings
BOT_PREFIX = '!'

# Embed Colors
EMBED_INFO_COLOR = 0x1E90FF

# Discord Server Boosts
DISCORD_BOOST_LVL1_CAP = 2
DISCORD_BOOST_LVL2_CAP = 15
DISCORD_BOOST_LVL3_CAP = 30

# Special User IDs
DISCORD_USER_ID_CONTRIBUTOR = 310100064687226882

# Database
DB_FILE_PATH = os.getenv("DB_FILE_PATH")
## Absolute path to the init script.
DB_INIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persistence/resources/init_db.sql")
