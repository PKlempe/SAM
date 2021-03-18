"""Contains instance variables and functions which can be accessed by the whole application."""
import atexit
from asyncio import get_event_loop
from aiohttp import ClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from discord.ext.commands import Bot

from bot.constants import DB_FILE_PATH
from bot.webserver import WebServer


WEBSERVER = None
HTTP_SESSION = ClientSession()
SCHEDULER = AsyncIOScheduler(job_defaults={'misfire_grace_time': 24 * 60 * 60},
                             jobstores={'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_FILE_PATH}')})


async def start_webserver(bot: Bot):
    """Function for initializing and starting the web server."""
    global WEBSERVER
    WEBSERVER = WebServer(bot)
    await WEBSERVER.start()


@atexit.register
def cleanup():
    """Function for various cleanup tasks automatically executed upon normal interpreter termination."""
    get_event_loop().run_until_complete(HTTP_SESSION.close())
