"""Contains a Cog for all community related functionality."""

import re
from typing import Optional

import discord
from discord.ext import commands

from bot import constants as const
from bot.persistence import DatabaseConnector
from bot.logger import command_log, log


class CommunityCog(commands.Cog):
    """Cog for Community Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(const.DB_FILE_PATH, const.DB_INIT_SCRIPT)

        # Channel Category instances
        self.cat_gaming_rooms = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CATEGORY_ID_GAMING_ROOMS))
        self.cat_study_rooms = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CATEGORY_ID_STUDY_ROOMS))

    @commands.command(name='studyroom', aliases=["sr"])
    @command_log
    async def create_study_room(self, ctx: commands.Context, ch_name: Optional[str], user_limit: Optional[int]):
        """Command Handler for the `studyroom` command.

        Allows users to create temporary "Study Rooms" consisting of a voice and text channel in the configured study
        room category on the server. The member who created the room gets special permissions for muting/deafening
        members in the voice channel. If no members are left in the voice channel, it, as well as the corresponding text
        channel, will be automatically deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_name (Optional[str]): The name of the channel provided by the member.
            user_limit (int): The user limit for the voice channel provided by the member.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self.create_community_room(ctx, self.cat_study_rooms, ch_name, user_limit)

    @commands.command(name='gameroom', aliases=["gr"])
    @command_log
    async def create_gaming_room(self, ctx: commands.Context, ch_name: Optional[str], user_limit: Optional[int]):
        """Command Handler for the `gameroom` command.

        Allows users to create temporary "Game Rooms" consisting of a voice and text channel in the configured game room
        category on the server. The member who created the room gets special permissions for muting/deafening members
        in the voice channel. If no members are left in the voice channel, it, as well as the corresponding text
        channel, will be automatically deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_name (Optional[str]): The name of the channel provided by the member.
            user_limit (int): The user limit for the voice channel provided by the member.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self.create_community_room(ctx, self.cat_gaming_rooms, ch_name, user_limit)

    @create_gaming_room.error
    @create_study_room.error
    async def community_room_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the community room commands.

        Handles the exceptions which could occur during the execution of said command.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, NotImplementedError):
            await ctx.send("Bitte lösche zuerst deinen bestehenden Study/Game Room, bevor du einen weiteren erstellst.",
                           delete_after=const.TIMEOUT_INFORMATION)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, RuntimeWarning):
            await ctx.send("Es gibt zurzeit zu viele aktive Räume in dieser Kategorie. Bitte versuche es später noch "
                           "einmal. :hourglass:", delete_after=const.TIMEOUT_INFORMATION)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.InvalidArgument):
            await ctx.send("Das Nutzer-Limit für einen Sprachkanal muss zwischen 1 und 99 liegen. Bitte versuche es "
                           "noch einmal.", delete_after=const.TIMEOUT_INFORMATION)

    async def create_community_room(self, ctx: commands.Context, ch_category: discord.CategoryChannel,
                                    ch_name: Optional[str], user_limit: Optional[int]):
        """Method which creates a temporary community room requested via the study/game room commands.

        Additionally it validates the configured limits (max. amount of community rooms, valid user limit, one room
        per member) and raises an exception if needed.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_name (Optional[str]): The name of the channel provided by the member.
            user_limit (int): The user limit for the voice channel provided by the member.
        """
        if len(ch_category.voice_channels) >= const.LIMIT_COMMUNITY_CHANNELS:
            raise RuntimeWarning("Too many Community Rooms of this kind at the moment.")
        if user_limit and (user_limit < 1 or user_limit > 99):
            raise discord.InvalidArgument("User limit cannot be outside range from 1 to 99.")
        if any(True for ch in self.cat_gaming_rooms.voice_channels if ctx.author in ch.overwrites) or \
           any(True for ch in self.cat_study_rooms.voice_channels if ctx.author in ch.overwrites):
            raise NotImplementedError("Member already has an active Community Room.")

        limit: Optional[int]
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

        # Remove channel number if user has added it himself.
        regex = re.search(r"(\[#\d+])", name)
        if regex:
            name = name.replace(regex.group(1), "")

        ch_number_addition = _determine_channel_number(ch_category, name)
        if ch_number_addition:
            name += ch_number_addition

        if len(name) > 100:
            name = name[:100]

        reason = f"Manuell erstellt von {ctx.author} via SAM."

        # Voice Channel
        bitrate = 96000  # 96 Kbit/s
        overwrites_voice = ch_category.overwrites
        overwrites_voice[ctx.author] = discord.PermissionOverwrite(priority_speaker=True, move_members=True,
                                                                   mute_members=True, deafen_members=True)
        await ch_category.create_voice_channel(name=name, user_limit=limit, bitrate=bitrate,
                                               overwrites=overwrites_voice, reason=reason)

        # Text Channel
        channel_type = "Game" if ch_category == self.cat_gaming_rooms else "Study"
        topic = f"Temporärer {channel_type}-Channel. || Erstellt von: {ctx.author.display_name}"
        await ch_category.create_text_channel(name=name, topic=topic, reason=reason)

        log.info("Temporary %s Room created by %s", channel_type, ctx.author)
        await ctx.send(f":white_check_mark: Der {channel_type}-Room wurde erfolgreich erstellt!",
                       delete_after=const.TIMEOUT_INFORMATION)

    @commands.Cog.listener(name='on_voice_state_update')
    async def delete_community_room(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Event listener which triggers if the VoiceState of a member changes.

        Deletes a Community Room (consisting of a voice and text channel) if no members are left in the corresponding
        voice channel.

        Args:
            member (discord.Member): The member whose VoiceState changed.
            before (discord.VoiceState): The previous VoiceState.
            after (discord.VoiceState): The new VoiceState.
        """
        if before.channel and before.channel.category_id in {self.cat_gaming_rooms.id, self.cat_study_rooms.id} and \
           before.channel != after.channel and len(before.channel.members) == 0:
            reason = "No one was left in Community Room."
            txt_ch_name = re.sub(r"[^\w\s-]", "", before.channel.name.lower())  # Remove non-word chars except WS
            txt_ch_name = re.sub(r"\s", "-", txt_ch_name)                       # Replace whitespaces with "-"
            txt_ch = next(ch for ch in before.channel.category.text_channels if ch.name == txt_ch_name)

            await before.channel.delete(reason=reason)
            await txt_ch.delete(reason=reason)
            log.info("Empty Community Room [%s] has been automatically deleted.", before.channel.name)

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def mark_as_highlight(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added to a message.

        If enough users react to a message with the specified highlight emoji, it will be reposted in the configured
        highlights channel by SAM. This way even users who don't have access to specific channels are able to see
        interesting content from somewhere on the server.
        If recently a highlight message has already been posted for a specific message, the reaction counter inside its
        embed will be modified.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.emoji.name != const.EMOJI_HIGHLIGHT or payload.channel_id == int(const.CHANNEL_ID_HIGHLIGHTS) \
                or self._db_connector.is_botonly(payload.channel_id):
            return

        guild = self.bot.get_guild(payload.guild_id)
        message_channel = guild.get_channel(payload.channel_id)
        message = await message_channel.fetch_message(payload.message_id)
        reaction = next(x for x in message.reactions if x.emoji == const.EMOJI_HIGHLIGHT)

        has_author_reacted = await reaction.users().get(id=message.author.id)
        reaction_counter = reaction.count - 1 if has_author_reacted else reaction.count

        highlight_channel = guild.get_channel(int(const.CHANNEL_ID_HIGHLIGHTS))
        highlight_message = await _check_if_already_highlight(highlight_channel, message.id)

        if highlight_message:
            embed = highlight_message.embeds[0]
            embed.set_field_at(0, name=f"{const.EMOJI_HIGHLIGHT} {reaction_counter}", value=const.ZERO_WIDTH_SPACE)
            await highlight_message.edit(content=f"Sieht so aus als hätte sich {message.author.mention} einen Platz in "
                                                 f"der Ruhmeshalle verdient! :tada:", embed=embed)

        elif reaction_counter >= const.LIMIT_HIGHLIGHT:
            # Check if an image has been attached to the original message. If yes, take the first image and pass it to
            # the method which builds the embed so that it will be displayed inside it. Every other image or type of
            # attachment should be attached to a second message which will be send immediately after the highlight embed
            # because they can't be included in the embed.
            image = next((a for a in message.attachments if not a.is_spoiler() and "image" in a.content_type), None)
            files = [await a.to_file(spoiler=a.is_spoiler()) for a in message.attachments if a != image]

            embed = _build_highlight_embed(message, image, guild.get_channel(int(const.CHANNEL_ID_ROLES)).name)
            await highlight_channel.send(f"Sieht so aus als hätte sich {message.author.mention} einen Platz in der "
                                         f"Ruhmeshalle verdient! :tada:", embed=embed)
            if files:
                async with highlight_channel.typing():
                    await highlight_channel.send(":paperclip: **Dazugehörige Attachments:**", files=files)


async def _check_if_already_highlight(highlight_channel: discord.TextChannel, message_id: int) \
        -> Optional[discord.Message]:
    """Checks whether a message has already been reposted as a highlight recently and returns it if true.

    Args:
        highlight_channel (discord.TextChannel): The configured channel for highlights.
        message_id (int): The ID of the message which has been marked as a highlight.

    Returns:
        (discord.Message): The highlight message if one has already been posted recently.
    """
    async for message in highlight_channel.history(limit=int(const.LIMIT_HIGHLIGHT_LOOKUP)):
        if message.embeds and message.embeds[0].url:
            original_message_id = message.embeds[0].url.split("/")[-1]

            if int(original_message_id) == message_id:
                return message

    return None


def _build_highlight_embed(message: discord.Message, image: discord.Attachment, role_ch_name: str) -> discord.Embed:
    """Creates an embed which contains a message that has been marked as a highlight by the server members.

    The embed contains the original message, the name of its author, the channel where it was posted and an image if one
    has been attached.

    Args:
        message (discord.Message): The message which should be reposted in the highlight channel.
        image (discord.Attachment): A possible image which should can be set for the embed.
        role_ch_name (str): The name of the configured role channel for the info text at the bottom of the embed.

    Returns:
        (discord.Embed): The new highlight embed.
    """
    embed = discord.Embed(title="[ Zur Original-Nachricht ]", url=message.jump_url, color=discord.Colour.gold(),
                          description=message.content) \
        .set_author(name=f"{message.author.display_name} in #{message.channel}:", icon_url=message.author.avatar_url) \
        .set_footer(text=f"Der obige Link funktioniert nur, wenn man zum jeweiligen Kanal auch Zugriff hat. Für mehr "
                         f"Infos siehe #{role_ch_name}.",
                    icon_url="https://i.imgur.com/TUN1NcQ.png") \
        .add_field(name=f"{const.EMOJI_HIGHLIGHT} {const.LIMIT_HIGHLIGHT}", value=const.ZERO_WIDTH_SPACE)

    if image:
        embed.set_image(url=image.url)

    return embed


def _determine_channel_number(ch_category: discord.CategoryChannel, name: str) -> Optional[str]:
    """Method which creates a string representing a channel number if needed.

    If a member tries to create a Community Room with a name that is currently being used in the same channel category,
    this method will determine the next free numeration and returns a corresponding string which will then be added to
    the channel name. If the name chosen is unique, `None` will be returned instead.

    Args:
        name (str): The channel name chosen by the member.

    Returns:
        Optional[str]: A string representing the next free numeration for a channel with the specified name.
    """
    channels = ch_category.voice_channels
    try:
        existing_name = next(ch.name for ch in reversed(channels) if name in ch.name)
        regex = re.search(r"\[#(\d+)]", existing_name)  # Regex for getting channel number.
        ch_number = int(regex.group(1)) + 1 if regex else "2"

    except StopIteration:
        return None

    return f" [#{ch_number}]"


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(CommunityCog(bot))
