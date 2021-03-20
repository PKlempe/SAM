"""File containing the class for the AIOHTTP web server."""
from typing import Dict

from json import loads
from aiohttp import web

from discord import Embed
from discord.ext.commands import Bot

from bot import constants as const
from bot.logger import log


class WebServer:
    """A class representing the AIOHTTP web server."""
    def __init__(self, bot: Bot):
        """Initializes the web server."""
        self.app = web.Application()
        self.app.add_routes([web.post('/ko-fi', self.kofi_notification)])
        self.bot = bot

    async def start(self):
        """Starts the web server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner)
        await site.start()

    async def kofi_notification(self, request):
        """Request handler for receiving and processing Ko-fi notifications."""
        log.info("The Web Server has received a request.")
        data = loads((await request.post())["data"])

        if data["type"] == "Donation":
            await _send_donation_notification(self.bot, data)
            log.info("Donation Embed has been posted.")
            return web.Response(status=200, reason="OK")

        return web.Response(status=400, reason="Bad Request")


async def _send_donation_notification(bot: Bot, donation_data: Dict):
    """Method which is being called by the web server if a notification from Ko-fi has been received.

    Posts an donation embed in the configured supporter channel.

    Args:
        donation_data (Dict): A dictionary containing all the information about the received donation.
    """
    guild = bot.get_guild(int(const.SERVER_ID))
    channel = guild.get_channel(int(const.CHANNEL_ID_SUPPORTER))
    url_owner_pic = guild.owner.avatar_url_as(format="png", size=32)

    if donation_data["is_public"]:
        name = donation_data["from_name"]
        message = donation_data["message"] if donation_data["message"] else "-"
        url_donation = const.URL_KOFI_DONATION.format(donation_data["message_id"])
    else:
        name = "`Anonymer Spender`"
        message = "`Geheim.` :shushing_face:"
        url_donation = ""

    embed = Embed(title="Neue Spende erhalten!", color=const.EMBED_COLOR_DONATION, url=url_donation,
                          description="Jemand hat dem Betreiber des Servers eine Tasse Kaffee ausgegeben. :coffee:")
    embed.set_author(name="Ko-fi", url=const.URL_KOFI)
    embed.set_footer(text="Danke! \U00002764\U0000FE0F", icon_url=url_owner_pic)
    embed.set_thumbnail(url=const.URL_KOFI_LOGO)
    embed.add_field(name="Name:", value=name)
    embed.add_field(name="Nachricht:", value=message)

    await channel.send(embed=embed)
