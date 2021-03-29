"""Contains a Cog for all funcionality regarding translations."""

import discord
from discord.ext import commands

from bot import constants as const
from bot.logger import command_log, log
from bot.persistence import DatabaseConnector


class TranslationCog(commands.Cog):
    """Cog for translation functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(const.DB_FILE_PATH, const.DB_INIT_SCRIPT)

        # Role instances
        self.role_moderator = bot.get_guild(int(const.SERVER_ID)).get_role(int(const.ROLE_ID_MODERATOR))

    # A special method that registers as a commands.check() for every command and subcommand in this cog.
    async def cog_check(self, ctx):
        return self.role_moderator in ctx.author.roles

    @commands.group(name='translation', hidden=True, invoke_without_command=True)
    @command_log
    async def translation(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @translation.command(name='add')
    @command_log
    async def add_translation(self, ctx: commands.Context, message: discord.Message, flag_emoji: str,
                              *, translation: str):
        """Command Handler for the subcommand `add` of the `translation` command.

        Adds a translation for the specified message by creating a database entry and adding a reaction representing a
        country flag to said message. If a user clicks on the reaction, a DM with the translation will be send to him
        via DM.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message for which a translation should be added.
            flag_emoji (str): The emoji representing a country flag and therefore a specific language.
            translation (str): The translation of the message.
        """
        if flag_emoji in [reaction.emoji for reaction in message.reactions]:
            await ctx.send(":x: Für die angegebene Landesflagge existiert bereits eine Übersetzung.")
            return

        self._db_connector.add_translation(message.id, flag_emoji, translation)
        await message.add_reaction(flag_emoji)
        log.info("A translation has been added to the message with id %s.", message.id)

        await ctx.send(":white_check_mark: Die Übersetzung wurde erfolgreich hinzugefügt.")

    @translation.command(name='remove')
    @command_log
    async def remove_translation(self, ctx: commands.Context, message: discord.Message, flag_emoji: str):
        """Command Handler for the subcommand `remove` of the `translation` command.

        Removes a translation of the specified message by deleting the corresponding database entry and reaction.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message for which a translation should be added.
            flag_emoji (str): The emoji representing a country flag and therefore a specific language.
        """
        if flag_emoji not in [reaction.emoji for reaction in message.reactions]:
            await ctx.send(":x: Für die angegebene Landesflagge existiert keine Übersetzung.")
            return

        self._db_connector.remove_translation(message.id, flag_emoji)
        await message.clear_reaction(flag_emoji)
        log.info("A translation has been removed from the message with id %s.", message.id)

        await ctx.send(":white_check_mark: Die Übersetzung wurde erfolgreich entfernt.")

    @translation.command(name='update')
    @command_log
    async def update_translation(self, ctx: commands.Context, message: discord.Message, flag_emoji: str,
                                 *, translation: str):
        """Command Handler for the subcommand `update` of the `translation` command.

        Updates a translation for the specified message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message for which a translation should be added.
            flag_emoji (str): The emoji representing a country flag and therefore a specific language.
            translation (str): The new translation of the message.
        """
        if flag_emoji not in [reaction.emoji for reaction in message.reactions]:
            await ctx.send(":x: Für die angegebene Landesflagge existiert keine Übersetzung.")
            return

        self._db_connector.update_translation(message.id, flag_emoji, translation)
        log.info("A translation of the message with id %s has been updated.", message.id)

        await ctx.send(":white_check_mark: Die Übersetzung wurde erfolgreich aktualisiert.")

    @translation.command(name='clear')
    @command_log
    async def clear_translations(self, ctx: commands.Context, message: discord.Message):
        """Command Handler for the subcommand `clear` of the `translation` command.

        Removes all translations of the specified message by deleting all the corresponding database entries and
        reactions.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message for which a translation should be added.
        """
        had_translations = self._db_connector.clear_translations(message.id)

        if not had_translations:
            await ctx.send("Die von dir angegebene Nachricht hat keine Übersetzungen. :face_with_monocle:")
            return

        await message.clear_reactions()
        log.info("All translations of the message with id %s have been removed.", message.id)

        await ctx.send(":white_check_mark: Die Übersetzungen wurden erfolgreich entfernt.")

    @add_translation.error
    @remove_translation.error
    @update_translation.error
    @clear_translations.error
    async def translation_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the subcommands of the `translation` command.

        Handles an exception which occurs if the specified message is invalid.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send("Ich konnte leider die von dir angegebene Nachricht nicht finden. :cold_sweat: Hast du dich "
                           "möglicherweise vertippt?")

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def get_translation(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the added reaction represents a country flag, the DB will be checked for a translation of this message. If
        one exists, the translation will be send to the user via DM.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if not payload.member.bot:
            translation = self._db_connector.get_translation(payload.message_id, payload.emoji.name)

            if translation:
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

                embed = _create_translation_embed(message.jump_url, payload.emoji.name, translation)
                await payload.member.send(embed=embed)

                # Remove reaction so that the user can request the translation again in the future
                await message.remove_reaction(payload.emoji, payload.member)


def _create_translation_embed(msg_url: str, flag_emoji: str, translation: str):
    embed = discord.Embed(title=f"Translation {flag_emoji}", color=const.EMBED_COLOR_TRANSLATION,
                          description=translation, url=msg_url)
    embed.set_footer(text="Found a translation error? Please contact the moderators!")

    return embed


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(TranslationCog(bot))
