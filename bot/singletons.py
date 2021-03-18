"""Contains instance variables and functions which can be accessed by the whole application."""
import atexit
from asyncio import get_event_loop
from aiohttp import ClientSession, web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from discord.ext.commands import Bot

from bot.constants import DB_FILE_PATH
from bot.endpoints import routes
from bot.bot_wrapper import BotWrapper


bot_wrapper = None
webserver = None
http_session = ClientSession()
scheduler = AsyncIOScheduler(job_defaults={'misfire_grace_time': 24*60*60},
                             jobstores={'default': SQLAlchemyJobStore(
                                 url=f'sqlite:///{DB_FILE_PATH}')})


async def start_webserver():
    global webserver
    webserver = web.Application()
    webserver.add_routes(routes)

    runner = web.AppRunner(webserver)
    await runner.setup()
    site = web.TCPSite(runner)
    await site.start()


def initialise_bot_wrapper(bot: Bot):
    global bot_wrapper
    bot_wrapper = BotWrapper(bot)


@atexit.register
def cleanup():
    """Function for various cleanup tasks automatically executed upon normal interpreter termination."""
    get_event_loop().run_until_complete(http_session.close())
