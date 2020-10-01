"""Contains a Cog for all gaming related functionality."""

from typing import Optional

import discord
from discord.ext import commands
import re

from bot import constants as const
from bot.persistence import DatabaseConnector
from bot.logger import command_log, log


class GamingCog(commands.Cog):
    """Cog for Gaming Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(const.DB_FILE_PATH, const.DB_INIT_SCRIPT)

        # Channel Category instances
        self.cat_gaming_channels = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CATEGORY_ID_GAMING_ROOMS))

    @commands.command(name='gameroom', aliases=["gr"])
    @command_log
    async def create_gaming_room(self, ctx: commands.Context, ch_name: Optional[str], user_limit: Optional[int]):
        """Command Handler for the `gameroom` command.

        Allows users to create temporary "Game Rooms" consisting of a voice and text channel in the configured game room
        category on the server. The member who created the room gets permissions for pinning/deleting messages in the
        text channel and for muting/deafening members in the voice channel.
        If no members are left in the voice channel, it will be deleted as well as the corresponding text channel.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_name (Optional[str]): The name of the channel provided by the member.
            user_limit (int): The user limit for the voice channel provided by the member.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        if len(self.cat_gaming_channels.channels) >= const.LIMIT_GAMING_CHANNELS:
            raise RuntimeWarning("Too many game rooms at the moment.")
        if user_limit and user_limit > 99:
            raise discord.InvalidArgument("User limit cannot be bigger than 99.")
        if any(True for ch in self.cat_gaming_channels.voice_channels if ctx.author in ch.overwrites):
            raise NotImplementedError("Member already has an active Game Room.")

        if ch_name and not user_limit:
            try:
                limit = int(ch_name)
                name = f"{ctx.author.display_name}'s Room"
            except ValueError:
                limit = None
                name = ch_name
        else:
            name = f"{ctx.author.display_name}'s Room" if ch_name is None else ch_name
            limit = user_limit

        ch_number_addition = self._determine_channel_number(name)
        if ch_number_addition:
            name += ch_number_addition

        if len(name) > 100:
            name = name[:100]

        reason = f"Manuell erstellt von {ctx.author} via SAM."

        # Voice Channel
        bitrate = 96000  # 96 Kbit/s
        overwrites_voice = self.cat_gaming_channels.overwrites
        overwrites_voice[ctx.author] = discord.PermissionOverwrite(priority_speaker=True, move_members=True,
                                                                   mute_members=True, deafen_members=True)
        await self.cat_gaming_channels.create_voice_channel(name=name, user_limit=limit, bitrate=bitrate,
                                                            overwrites=overwrites_voice, reason=reason)

        # Text Channel
        topic = f"Temporärer Gaming-Kanal. || Erstellt von: {ctx.author.display_name}"
        overwrites_text = self.cat_gaming_channels.overwrites
        overwrites_text[ctx.author] = discord.PermissionOverwrite(manage_messages=True)
        await self.cat_gaming_channels.create_text_channel(name=name, topic=topic, overwrites=overwrites_text,
                                                           reason=reason)

        log.info("Temporary Game Room created by %s", ctx.author)
        await ctx.send(":white_check_mark: Der Game-Room wurde erfolgreich erstellt!",
                       delete_after=const.TIMEOUT_INFORMATION)

    @create_gaming_room.error
    async def gaming_room_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the command `gameroom`.

        Handles the exceptions which could occur during the execution of this command.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, NotImplementedError):
            await ctx.send("Bitte lösche zuerst deinen bestehenden Game Room, bevor du einen neuen erstellst.",
                           delete_after=const.TIMEOUT_INFORMATION)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, RuntimeWarning):
            await ctx.send("Es gibt zurzeit zu viele aktive Game Rooms. Bitte versuche es später noch einmal. "
                           ":hourglass:", delete_after=const.TIMEOUT_INFORMATION)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.InvalidArgument):
            await ctx.send("Das Nutzer-Limit für einen Sprachkanal darf 99 nicht überschreiten. Bitte versuche es noch "
                           "einmal.", delete_after=const.TIMEOUT_INFORMATION)

    def _determine_channel_number(self, name: str) -> Optional[str]:
        """Method which creates a string representing a channel number if needed.

        If a member tries to create a Game Room with a name that is currently being used, this method will determine
        the next free numeration and returns a corresponding string which will then be added to the channel name.
        If the name chosen is unique, `None` will be returned instead.

        Args:
            name (str): The channel name chosen by the member.

        Returns:
            Optional[str]: A string representing the next free numeration for a channel with the specified name.
        """
        channels = self.cat_gaming_channels.voice_channels

        try:
            existing_name = next(ch.name for ch in reversed(channels) if name in ch.name)
            regex = re.search(r"\[#(\d+)]", existing_name)  # Regex for getting channel number.
            ch_number = int(regex.group(1)) + 1 if regex else "2"

        except StopIteration:
            return None

        return f" [#{ch_number}]"

    @commands.Cog.listener(name='on_voice_state_update')
    async def delete_gaming_room(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Event listener which triggers if the VoiceState of a member changes.

        Deletes a Game Rome (consisting of a voice and text channel) if no members are left in the corresponding voice
        channel.

        Args:
            member (discord.Member): The member whose VoiceState changed.
            before (discord.VoiceState): The previous VoiceState.
            after (discord.VoiceState): The new VoiceState.
        """
        if before.channel and before.channel.category_id == self.cat_gaming_channels.id \
          and before.channel != after.channel and len(before.channel.members) == 0:
            reason = "No one was left in Game Room."
            txt_ch_name = before.channel.name.lower().replace(" ", "-").replace("[#", "").replace("]", "")
            txt_ch = next(ch for ch in self.cat_gaming_channels.text_channels if ch.name == txt_ch_name)

            await before.channel.delete(reason=reason)
            await txt_ch.delete(reason=reason)
            log.info("Empty Game Room [%s] has been automatically deleted.", before.channel.name)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(GamingCog(bot))
