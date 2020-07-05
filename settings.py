import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BOT_PREFIX = '!'
