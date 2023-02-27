"""Contains a Cog for all functionality regarding server roles."""
import re

from sqlite3 import IntegrityError
from typing import List

import discord
from discord.ext import commands
from discord import app_commands

from bot import constants
from bot.logger import command_log, log
from bot.persistence import DatabaseConnector
from bot.university import ufind_requests
from bot.ui import DestructiveView, CourseSelect


class RoleManagementCog(commands.Cog):
    """Cog for functions regarding server roles."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

        # Channel instances
        self.ch_role = bot.get_guild(int(constants.SERVER_ID)).get_channel(int(constants.CHANNEL_ID_ROLES))

    @commands.hybrid_command(name='course', description="Unlock/Hide a specific course channel")
    @app_commands.describe(name='The actual name of the course or a search term')
    @command_log
    async def toggle_course(self, ctx: commands.Context, name: str):
        """Command Handler for the `course` command.

        Allows members to assign/remove so-called course roles to/from themselves. This way users can toggle the
        visibility of text channels for specific courses.
        Keep in mind that this only works if the desired role has been whitelisted as a course role by the bot owner.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            name (str): The name of the university course.
        """
        async with ctx.channel.typing():
            course_options = await ufind_requests.get_course_options(name)

            if course_options:
                course_selector = CourseSelect(course_options, self._db_connector)
                view = DestructiveView(timeout=constants.TIMEOUT_USER_INTERACTION).add_item(course_selector)
                view.message = await ctx.send(f"Ich habe anhand deines Suchbegriffs **__{len(course_options)}__** "
                                              f"Lehrveranstaltungen finden können.", view=view, ephemeral=True)
            else:
                await ctx.send("Ich habe anhand deines Suchbegriffs leider keine Lehrveranstaltungen finden können. "
                               ":pensive:", ephemeral=True, delete_after=constants.TIMEOUT_INFORMATION)

    @commands.group(name="whitelist", invoke_without_command=True, hidden=True)
    @commands.is_owner()
    @command_log
    async def whitelist_role(self, ctx: commands.Context) -> None:
        """Command Handler for the `whitelist` command.

        Prints a help message which lists all the available subcommands that can be used.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        await ctx.send_help(ctx.command)

    @whitelist_role.command(name="add")
    @commands.is_owner()
    @command_log
    async def add_course_role(self, ctx: commands.Context, course_role: discord.Role, course_id: str):
        """Command Handler for the `whitelist` subcommand `add`.

        Allows the bot owner to add a specific role to the list of course roles which users can assign to themselves.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            course_role (discord.Role): The role which should be whitelisted as a course role.
            course_id (str): The course ID assigned by the university.
        """
        try:
            self._db_connector.add_course_role(course_role.id, course_id)
            log.info("Role \"%s\" has been whitelisted as a course role.", course_role)
            await ctx.send(f':white_check_mark: The role **__{course_role}__** has been whitelisted as a course role.')

        except IntegrityError:
            await ctx.send(f'The role **__{course_role}__** has already been whitelisted as a course role.')

    @whitelist_role.command(name="remove")
    @commands.is_owner()
    @command_log
    async def remove_course_role(self, ctx: commands.Context, course_role: discord.Role):
        """Command Handler for the `whitelist` subcommand `remove`.

        Allows the bot owner to remove a specific role from the list of available course roles.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            course_role (discord.Role): The role which should be removed.
        """
        self._db_connector.remove_course_role(course_role.id)
        log.info("Role \"%s\" has been removed as a course role.", course_role)
        await ctx.send(f":white_check_mark: Die Rolle \"**__{course_role}__**\" wurde aus den verfügbaren Kurs-Rollen "
                       f"entfernt.")

    @commands.group(name='module', invoke_without_command=True)
    @command_log
    async def toggle_module(self, ctx: commands.Context, *, str_modules: str):
        """Command Handler for the `module` command.

        Allows members to assign/remove so called mod roles to/from themselves. This way users can toggle text channels
        about specific courses to be visible or not to them. When the operation is finished, SAM will send an overview
        about the changes he did per direct message to the user who invoked the command.
        Keep in mind that this only works if the desired role has been whitelisted as a module role by the bot owner.

        If the command is invoked outside of the configured role channel, the bot will post a short info that this
        command should only be invoked there and delete this message shortly after.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            str_modules (str): A string containing abbreviations of all the modules a user would like to toggle.
        """
        if ctx.channel.id != self.ch_role.id:
            if not self._db_connector.is_botonly(ctx.channel.id):
                await ctx.message.delete()

            await ctx.channel.send(content=f"Dieser Befehl wird nur in {self.ch_role.mention} unterstützt. Bitte "
                                   f"versuche es dort noch einmal.", delete_after=constants.TIMEOUT_INFORMATION)
            return

        converter = commands.RoleConverter()
        modules = list(set(str_modules.split()))  # Removes duplicates

        modules_error = []
        modules_added = []
        modules_removed = []

        for module in modules:
            module_upper = module.upper()
            try:
                role = await converter.convert(ctx, module_upper)

                if not self._db_connector.check_module_role(role.id):
                    raise commands.BadArgument("The specified role hasn't been whitelisted as a module role.")

                if role in ctx.author.roles:
                    await ctx.author.remove_roles(role, atomic=True, reason="Selbstständig entfernt via SAM.")
                    modules_removed.append(module_upper)
                else:
                    await ctx.author.add_roles(role, atomic=True, reason="Selbstständig zugewiesen via SAM.")
                    modules_added.append(module_upper)
            except commands.BadArgument:
                modules_error.append(module_upper)

        if len(modules_error) < len(modules):
            log.info("Module roles of the member %s have been changed.", ctx.author)

        embed = _create_embed_module_roles(modules_added, modules_removed, modules_error)
        await ctx.author.send(embed=embed)

    @toggle_module.command(name="add", hidden=True)
    @commands.is_owner()
    @command_log
    async def add_module_role(self, ctx: commands.Context, module_name: str):
        """Command Handler for the `module` subcommand `add`.

        Allows the bot owner to add a specific role to the module roles.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            module_name (str): The name of the role which should be added.
        """
        module_role = await commands.RoleConverter().convert(ctx, module_name.upper())

        try:
            self._db_connector.add_module_role(module_role.id)
            log.info("Role \"%s\" has been whitelisted as a module role.", module_role)

            await ctx.send(f"Die Rolle \"**__{module_role}__**\" wurde erfolgreich zu den verfügbaren Modul-Rollen "
                           f"hinzugefügt.")
        except IntegrityError:
            await ctx.send(f"Die Rolle \"**__{module_role}__**\" gehört bereits zu den verfügbaren Modul-Rollen.")

    @toggle_module.command(name="remove", hidden=True)
    @commands.is_owner()
    @command_log
    async def remove_module_role(self, ctx: commands.Context, module_name: str):
        """Command Handler for the `module` subcommand `remove`.

        Allows the bot owner to remove a specific role from the module roles.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            module_name (str): The name of the role which should be removed.
        """
        module_role = await commands.RoleConverter().convert(ctx, module_name.upper())

        self._db_connector.remove_module_role(module_role.id)
        log.info("Role \"%s\" has been disabled as a module role.", module_role)

        await ctx.send(f"Die Rolle \"**__{module_role}__**\" wurde aus den verfügbaren Modul-Rollen entfernt.")

    @add_module_role.error
    @remove_module_role.error
    async def module_role_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `module` subcommand `remove`.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            role = re.search(r"\"(.*)\"", error.args[0])  # Regex for getting text between two quotes.
            role = role.group(1) if role is not None else None

            await ctx.author.send(f"Die von dir angegebene Rolle \"**__{role}__**\" existiert leider nicht.")

    @commands.group(name="reactionrole", aliases=["rr"], hidden=True, invoke_without_command=True)
    @commands.is_owner()
    @command_log
    async def reaction_role(self, ctx: commands.Context):
        """Command Handler for the `reactionrole` command.

        Allows the bot owner to manage so called "reaction roles" for messages in the configured role channel. This can
        be done via multiple subcommands like `add`, `remove` or `clear`.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        await ctx.send_help(ctx.command)

    @reaction_role.command(name="add")
    @commands.is_owner()
    @command_log
    async def add_reaction_role(self, ctx: commands.Context, message: discord.Message, emoji: str, role: discord.Role):
        """Command Handler for the subcommand `add` of the `reactionrole` command.

        Adds a reaction to a specified message and creates a corresponding database entry for it to work as a so called
        reaction role.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message to which the reaction role should be added.
            emoji (str): The emoji of the reaction which will be added.
            role (discord.Role): The specific role a member should get when adding the reaction.
        """
        if message.channel.id != self.ch_role.id:
            await ctx.send(f":information_source: Reaction-Roles können nur für Nachrichten im Kanal "
                           f"{self.ch_role.mention} erstellt werden.")
            return
        if emoji in [reaction.emoji for reaction in message.reactions]:
            await ctx.send(":x: Für den angegebenen Emoji existiert bereits eine Reaction-Role.")
            return

        self._db_connector.add_reaction_role(message.id, emoji, role.id)
        await message.add_reaction(emoji)
        log.info("A reaction role has been added to the message with id %s.", message.id)

        await ctx.send(":white_check_mark: Die Reaction-Role wurde erfolgreich erstellt.")

    @reaction_role.command(name="remove")
    @commands.is_owner()
    @command_log
    async def remove_reaction_role(self, ctx: commands.Context, message: discord.Message, emoji: str):
        """Command Handler for the subcommand `remove` of the `reactionrole` command.

        Removes the reaction from a specified message and deletes the corresponding database entry of the reaction role.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message from which the reaction role should be removed.
            emoji (str): The emoji of the reaction.
        """
        if message.channel.id != self.ch_role.id:
            await ctx.send(f":information_source: Nachrichten außerhalb des Kanals {self.ch_role.mention} können keine "
                           f"Reaction-Roles besitzen.")
            return
        if emoji not in [reaction.emoji for reaction in message.reactions]:
            await ctx.send(":x: Für den angegebenen Emoji existiert leider keine Reaction-Role.")
            return

        self._db_connector.remove_reaction_role(message.id, emoji)
        await message.clear_reaction(emoji)
        log.info("A reaction role has been removed from the message with id %s.", message.id)

        if len(message.reactions) == 1:
            self._db_connector.remove_reaction_role_uniqueness_group(message.id)

        await ctx.send(":white_check_mark: Die Reaction-Role wurde erfolgreich entfernt.")

    @reaction_role.command(name="clear")
    @commands.is_owner()
    @command_log
    async def clear_reaction_roles(self, ctx: commands.Context, message: discord.Message):
        """Command Handler for the subcommand `clear` of the `reactionrole` command.

        Removes all the reaction from a specified message and deletes all the corresponding database entry of the
        reaction roles.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message from which the reaction roles should be removed.
        """
        if message.channel.id != self.ch_role.id:
            await ctx.send(f":information_source: Nachrichten außerhalb des Kanals {self.ch_role.mention} können keine "
                           f"Reaction-Roles besitzen.")
            return
        had_reaction_roles = self._db_connector.clear_reaction_roles(message.id)
        self._db_connector.remove_reaction_role_uniqueness_group(message.id)

        if not had_reaction_roles:
            await ctx.send("Die von dir angegebene Nachricht hat keine Reaction-Roles. :face_with_monocle:")
            return

        await message.clear_reactions()
        log.info("All reaction roles of the message with id %s have been removed.", message.id)

        await ctx.send(":white_check_mark: Die Reaction-Roles wurden erfolgreich entfernt.")

    @reaction_role.command(name="unique")
    @commands.is_owner()
    @command_log
    async def toggle_reaction_roles_exclusiveness(self, ctx: commands.Context, message: discord.Message):
        """Command Handler for the subcommand `unique` of the `reactionrole` command.

        Marks all the reaction roles of a message as "unique" by adding the message id to a specific table in the db.
        This means that users can only have one of the configured reaction roles of this message at a time.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (discord.Message): The message from which the reaction roles should be removed.
        """
        if len(message.reactions) == 0:
            await ctx.send(":x: Die angegebene Nachricht besitzt keine Reaction-Roles.")
            return

        if self._db_connector.is_reaction_role_uniqueness_group(message.id):
            self._db_connector.remove_reaction_role_uniqueness_group(message.id)
            log.info("A reaction role has been added to the message with id %s.", message.id)

            await ctx.send(":white_check_mark: Die Reaction-Roles der angegebenen Nachricht sind nicht mehr "
                           "\"exklusiv\".")
        else:
            self._db_connector.add_reaction_role_uniqueness_group(message.id)
            await ctx.send(":white_check_mark: Die Reaction-Roles der angegebenen Nachricht sind nun \"exklusiv\".")

    @add_reaction_role.error
    @remove_reaction_role.error
    @clear_reaction_roles.error
    @toggle_reaction_roles_exclusiveness.error
    async def reaction_role_error(self, _ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `reactionrole` command group.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            _ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            print("**__Error:__** Die von dir angegebene Nachricht/Rolle existiert nicht.")

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def reaction_role_add(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the specified role channel and the added reaction represents one of the configured
        reaction roles, the corresponding role specified in the db will be added to the user.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_role.id and not payload.member.bot:
            if self._db_connector.is_reaction_role_uniqueness_group(payload.message_id):
                message = await self.ch_role.fetch_message(payload.message_id)

                for reaction in message.reactions:
                    if reaction.emoji != payload.emoji.name:
                        users = await reaction.users().flatten()

                        if payload.member in users:
                            await reaction.remove(payload.member)
                            break

                        role_id = self._db_connector.get_reaction_role(payload.message_id, reaction.emoji)
                        role = self.bot.get_guild(payload.guild_id).get_role(role_id)

                        if role in payload.member.roles:
                            await payload.member.remove_roles(role, reason="Automatische/Manuelle Entfernung via "
                                                                           "Reaction.")
                            break

            role_id = self._db_connector.get_reaction_role(payload.message_id, payload.emoji.name)
            role = self.bot.get_guild(payload.guild_id).get_role(role_id)
            await payload.member.add_roles(role, reason="Selbstzuweisung via Reaction.")

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def reaction_role_remove(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been removed.

        If the affected message is in the specified role channel and the removed reaction represents one of the
        configured reaction roles, the corresponding role specified in the db will removed from the user.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_role.id:
            role_id = self._db_connector.get_reaction_role(payload.message_id, payload.emoji.name)
            role = self.bot.get_guild(payload.guild_id).get_role(role_id)

            member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
            await member.remove_roles(role, reason="Automatische/Manuelle Entfernung via Reaction.")

    @commands.Cog.listener(name='on_raw_message_delete')
    async def delete_reaction_role_group(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a message has been deleted.

        If the affected message was in the specified role channel and was listed as a special Reaction Role Group in
         the db, the corresponding entry will be removed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_role.id:
            self._db_connector.remove_reaction_role_uniqueness_group(payload.message_id)


def _create_embed_module_roles(modules_added: List[str], modules_removed: List[str], modules_error: List[str]) \
        -> discord.Embed:
    """Method which creates the overview embed when updating your module roles.

    Args:
        modules_added (List[str]): A list containing the names of the module roles which have been added.
        modules_removed (List[str]): A list containing the names of the module roles which have been removed.
        modules_error (List[str]): A list containing the names of the module roles which couldn't be found.

    Returns:
        discord.Embed: Embedded message representing an overview about the changes regarding a users module roles.
    """
    icon = ":x: " if modules_error else ":white_check_mark: "

    if not modules_error:
        description = "Deine Modul-Rollen wurden erfolgreich angepasst."
    else:
        description = "Beim Anpassen deiner Modul-Rollen, gab es leider Probleme.\n__Folgende Module existieren " \
                      "nicht:__ " + ", ".join(modules_error)

    dict_embed = discord.Embed(title=f"{icon} Modul-Rollen Überblick", description=description,
                               color=constants.EMBED_COLOR_INFO) \
        .add_field(name=":green_circle: **Hinzugefügte Module:**", value="- Keine", inline=True) \
        .add_field(name=":red_circle: **Entfernte Module:**", value="- Keine", inline=True) \
        .to_dict()

    if modules_added:
        str_module = ""
        for module in modules_added:
            str_module += f"- {module}\n"
        dict_embed["fields"][0]["value"] = str_module
    if modules_removed:
        str_module = ""
        for module in modules_removed:
            str_module += f"- {module}\n"
        dict_embed["fields"][1]["value"] = str_module

    return discord.Embed.from_dict(dict_embed)


async def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    await bot.add_cog(RoleManagementCog(bot))
