"""Contains instance variables and functions which can be accessed by the whole application."""
import atexit
from asyncio import get_event_loop
from aiohttp import ClientSession


http_session = ClientSession()


@atexit.register
def cleanup():
    """Function for various cleanup tasks automatically executed upon normal interpreter termination."""
    get_event_loop().run_until_complete(http_session.close())
