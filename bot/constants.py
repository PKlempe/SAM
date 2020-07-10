"""File which contains constants used for this bot."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")

BOT_PREFIX = '!'

DISCORD_BOOST_LVL1_CAP = 2
DISCORD_BOOST_LVL2_CAP = 15
DISCORD_BOOST_LVL3_CAP = 30

EMBED_INFO_COLOR = 0x1E90FF

# Database
DB_FILE_PATH = os.getenv("DB_FILE_PATH")
#absolute path to the init script
DB_INIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persistence/resources/init_db.sql")

# Database Queries
INSERT_PROPERTY_QUERY = "INSERT OR REPLACE INTO configs VALUES(?, ?);"
GET_PROPERTY_QUERY = "SELECT val FROM configs WHERE config_key =?"
