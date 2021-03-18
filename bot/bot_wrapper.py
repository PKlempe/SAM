from typing import Dict

from discord import Embed
from discord.ext.commands import Bot

from bot import constants as const


class BotWrapper:

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_donation_notification(self, data: Dict):
        guild = self.bot.get_guild(int(const.SERVER_ID))
        channel = guild.get_channel(int(const.CHANNEL_ID_SUPPORTER))

        name = data["from_name"] if data["is_public"] else "`Anonymer Spender`"
        message = data["message"] if data["is_public"] else "`Geheim.` :shushing_face:"
        url_owner_pic = guild.owner.avatar_url_as(format="png", size=32)

        embed = Embed(title="Neue Spende erhalten!", color=const.EMBED_COLOR_DONATION, url=data["url"],
                      description="Jemand hat dem Betreiber des Servers eine Tasse Kaffee ausgegeben. :coffee:")
        embed.set_author(name="Ko-fi", url=const.URL_KOFI)
        embed.set_footer(text="Danke! \U00002764\U0000FE0F", icon_url=url_owner_pic)
        embed.set_thumbnail(url=const.URL_KOFI_LOGO)
        embed.add_field(name="Name:", value=name)
        # embed.add_field(name="Betrag:", value="{0}€".format(data['amount']))
        embed.add_field(name="Nachricht:", value=message)

        await channel.send(embed=embed)
