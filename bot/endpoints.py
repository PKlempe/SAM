from aiohttp import web
from json import loads

from bot import singletons

routes = web.RouteTableDef()


@routes.post("/ko-fi")
async def kofi_notification(request):
    data = loads((await request.post())["data"])

    if data["type"] == "Donation":
        await singletons.bot_wrapper.send_donation_notification(data)
        return web.Response(status=200, reason="OK")

    return web.Response(status=400, reason="Bad Request")
