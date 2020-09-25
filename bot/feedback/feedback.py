"""Contains a Cog for all functionality regarding member feedback."""

from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from bot import constants
from bot.persistence import DatabaseConnector
from bot.logger import command_log, log
from bot.feedback import SuggestionStatus


class FeedbackCog(commands.Cog):
    """Cog for Feedback Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

        # Channel instances
        self.ch_suggestion = bot.get_guild(int(constants.SERVER_ID)).get_channel(int(constants.CHANNEL_ID_SUGGESTIONS))

    @commands.group(name="suggestion", hidden=True, invoke_without_command=True, aliases=["suggest"])
    @command_log
    async def manage_suggestions(self, ctx: commands.Context, *, suggestion: str):
        """Command Handler for the `suggestion` command.

        Allows users to submit suggestions for improving the server. After submitting, an embed containing the provided
        information will be posted in the configured suggestion channel by SAM.
        A suggestion can be marked as "approved", "denied", "considered" or "implemented". For each of these statuses
        exists a corresponding subcommand.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            suggestion (str): The suggestion provided by the user.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        suggestion_id = self._db_connector.add_suggestion(ctx.author.id, ctx.message.created_at)

        embed = _build_suggestion_embed(ctx.author, suggestion, suggestion_id)
        message = await self.ch_suggestion.send(embed=embed)

        self._db_connector.set_suggestion_message_id(suggestion_id, message.id)

        await message.add_reaction(constants.EMOJI_UPVOTE)
        await message.add_reaction(constants.EMOJI_DOWNVOTE)

    @manage_suggestions.command(name="approve")
    @commands.is_owner()
    @command_log
    async def suggestion_approve(self, ctx: commands.Context, suggestion_id: int, *, reason: Optional[str]):
        """Command Handler for the `suggestion` subcommand `approve`.

        Allows the owner to mark a suggestion as approved and add an optional reason to it. If this is the case, the
        corresponding embed will be adapted to represent this change and the user who submitted the idea will be
        notified via DM.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            suggestion_id (int): The id of the suggestion which should be approved.
            reason (Optional[str]): The reason for this decision.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self._change_suggestion_status(suggestion_id, SuggestionStatus.APPROVED, ctx.author, reason)
        log.info("Suggestion #%s has been approved by %s.", suggestion_id, ctx.author)

    @manage_suggestions.command(name="deny")
    @commands.is_owner()
    @command_log
    async def suggestion_deny(self, ctx: commands.Context, suggestion_id: int, *, reason: Optional[str]):
        """Command Handler for the `suggestion` subcommand `deny`.

        Allows the owner to mark a suggestion as denied and add an optional reason to it. If this is the case, the
        corresponding embed will be adapted to represent this change and the user who submitted the idea will be
        notified via DM.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            suggestion_id (int): The id of the suggestion which should be approved.
            reason (Optional[str]): The reason for the decision.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self._change_suggestion_status(suggestion_id, SuggestionStatus.DENIED, ctx.author, reason)
        log.info("Suggestion #%s has been denied by %s.", suggestion_id, ctx.author)

    @manage_suggestions.command(name="consider")
    @commands.is_owner()
    @command_log
    async def suggestion_consider(self, ctx: commands.Context, suggestion_id: int, *, reason: Optional[str]):
        """Command Handler for the `suggestion` subcommand `consider`.

        Allows the owner to mark a suggestion as considered and add an optional reason to it. If this is the case, the
        corresponding embed will be adapted to represent this change and the user who submitted the idea will be
        notified via DM.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            suggestion_id (int): The id of the suggestion which should be approved.
            reason (Optional[str]): The reason for the decision.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self._change_suggestion_status(suggestion_id, SuggestionStatus.CONSIDERED, ctx.author, reason)
        log.info("Suggestion #%s is being considered by %s.", suggestion_id, ctx.author)

    @manage_suggestions.command(name="implemented")
    @commands.is_owner()
    @command_log
    async def suggestion_implemented(self, ctx: commands.Context, suggestion_id: int, *, reason: Optional[str]):
        """Command Handler for the `suggestion` subcommand `implemented`.

        Allows the owner to mark a suggestion as implemented  and add an optional reason to it. If this is the case, the
        corresponding embed will be adapted to represent this change and the user who submitted the idea will be
        notified via DM.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            suggestion_id (int): The id of the suggestion which should be approved.
            reason (Optional[str]): The reason for the decision.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        await self._change_suggestion_status(suggestion_id, SuggestionStatus.IMPLEMENTED, ctx.author, reason)
        log.info("Suggestion #%s marked as implemented by %s.", suggestion_id, ctx.author)

    @suggestion_approve.error
    @suggestion_deny.error
    @suggestion_consider.error
    @suggestion_implemented.error
    async def suggestion_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `suggestion` subcommands `approve`, `deny`, `consider` and `implemented`.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send("Ich konnte leider keinen Vorschlag mit der von dir angegebenen Nummer finden. :frowning2:",
                           delete_after=constants.TIMEOUT_INFORMATION)

    async def _change_suggestion_status(self, suggestion_id: int, status: SuggestionStatus, author: discord.Member,
                                        reason: Optional[str]):
        """Method which changes the status of a suggestion.

        Changes the status of the suggestion in the db, adapts the corresponding embed in the suggestion channel to
        represent the newly made changes and finally notifies the user who submitted it via DM.

        Args:
            status (SuggestionStatus): The new status of the suggestion.
            author (discord.Member): The user who invoked the command to change it.
            suggestion_id (int): The id of the suggestion.
            reason (Optional[str]): The reason for the decision.
        """
        id_exists = self._db_connector.set_suggestion_status(suggestion_id, status)
        if not id_exists:
            raise commands.BadArgument("The suggestion with the specified ID doesn't exist.")

        suggestion_data = self._db_connector.get_suggestion(suggestion_id)
        message = await self.ch_suggestion.fetch_message(suggestion_data[0])

        await _refresh_suggestion_embed(message, author, reason, SuggestionStatus(suggestion_data[1]))
        await self._notify_user_suggestion_change(int(suggestion_data[2]))

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def suggestion_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the configured suggestion channel and the added reaction is one of the two vote
        emojis specified in constants.py, the color of the suggestion embed will be changed if enough up- or downvotes
        have been submitted.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_suggestion.id and not payload.member.bot and \
                self._db_connector.get_suggestion_status(payload.message_id) == SuggestionStatus.UNDECIDED:
            message = await self.ch_suggestion.fetch_message(payload.message_id)
            reactions = message.reactions

            if payload.emoji.name in (constants.EMOJI_UPVOTE, constants.EMOJI_DOWNVOTE):
                required_difference = (reactions[0].count + reactions[1].count) / 2
                actual_difference = abs(reactions[0].count - reactions[1].count)

                # Changes the color of the embed depending if one side received at least 10 votes and the difference
                # between them is bigger than 50% of total votes.
                if reactions[0].count > int(constants.LIMIT_SUGGESTION_VOTES) and \
                        reactions[0].count > reactions[1].count and actual_difference > required_difference:
                    new_embed = _recolor_embed(message.embeds[0], constants.EMBED_COLOR_SUGGESTION_MEMBERS_LIKE)
                    await message.edit(embed=new_embed)
                elif reactions[1].count > int(constants.LIMIT_SUGGESTION_VOTES) and \
                        actual_difference > required_difference:
                    new_embed = _recolor_embed(message.embeds[0], constants.EMBED_COLOR_SUGGESTION_MEMBERS_DISLIKE)
                    await message.edit(embed=new_embed)

    async def _notify_user_suggestion_change(self, user_id: int):
        """Method which notifies a user about changes regarding his suggestion.

        Gets the corresponding Discord member and sends a personalized DM to him informing him about changes regarding
        his suggestion.

        Args:
            user_id (int): The id of the user who submitted the suggestion.
        """
        member = self.bot.get_guild(int(constants.SERVER_ID)).get_member(user_id)
        text = "Hey, {0}!\nEs gibt Neuigkeiten bezüglich deines Vorschlags.Sieh am besten gleich in {1} nach, wie " \
               "das Urteil ausgefallen ist. :fingers_crossed:".format(member.display_name, self.ch_suggestion.mention)

        await member.send(text)


async def _refresh_suggestion_embed(message: discord.Message, author: discord.Member, reason: Optional[str],
                                    status: SuggestionStatus):
    """Method which adapts an embed regarding a suggestion.

    Changes title, color and fields of the embed accordingly to the new status of the suggestion.

    Args:
        message (discord.Message): The message containing the suggestion embed.
        author (discord.Member): The user who invoked the command to change it.
        reason (Optional[str]): The reason for the decision.
        status (SuggestionStatus): The new status of the suggestion.
    """
    dict_embed = message.embeds[0].to_dict()

    dict_embed["fields"] = [{"name": f"Begründung von {author}:", "value": reason}] if reason else list()

    dict_embed["title"] = dict_embed["title"].split(" -")[0]
    if status == SuggestionStatus.APPROVED:
        dict_embed["color"] = constants.EMBED_COLOR_SUGGESTION_APPROVED
        dict_embed["title"] = dict_embed["title"] + " - Genehmigt :white_check_mark:"
    elif status == SuggestionStatus.DENIED:
        dict_embed["color"] = constants.EMBED_COLOR_SUGGESTION_DENIED
        dict_embed["title"] = dict_embed["title"] + " - Abgelehnt :no_entry_sign:"
    elif status == SuggestionStatus.CONSIDERED:
        dict_embed["color"] = constants.EMBED_COLOR_SUGGESTION_CONSIDERED
        dict_embed["title"] = dict_embed["title"] + " - Möglicherweise :thinking:"
    else:
        dict_embed["color"] = constants.EMBED_COLOR_SUGGESTION_IMPLEMENTED
        dict_embed["title"] = dict_embed["title"] + " - Umgesetzt :tada:"

    await message.edit(embed=discord.Embed.from_dict(dict_embed))


def _build_suggestion_embed(author: discord.Member, suggestion: str, suggestion_id: int) -> discord.Embed:
    """Method which builds the embed for a suggestion.

    Args:
        author (discord.Member): The user who invoked the command to change it.
        suggestion (str): The suggestion provided by the user.
        suggestion_id (int): The id of the suggestion provided by the db.

    Returns:
        discord.Embed: The embed representing a user suggestion.
    """
    embed = discord.Embed(title=f"Vorschlag #{suggestion_id}", description=suggestion,
                          color=constants.EMBED_COLOR_SUGGESTION, timestamp=datetime.utcnow()) \
        .set_author(name=str(author), icon_url=author.avatar_url) \
        .set_footer(text="Eingereicht am")

    return embed


def _recolor_embed(embed: discord.Embed, color: discord.Colour) -> discord.Embed:
    """Method which changes the color of a provided embed.

    Args:
        embed (discord.Embed): The embed of which the color should be changed.
        color (discord.Colour): The new color of the embed.

    Returns:
        discord.Embed: The embed provided but with a new color.
    """
    dict_embed = embed.to_dict()
    dict_embed["color"] = color
    return discord.Embed.from_dict(dict_embed)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(FeedbackCog(bot))
