"""Contains a Cog for all functionality regarding server roles."""
import re

from sqlite3 import IntegrityError
from typing import List

import discord
from discord.ext import commands

from bot import constants
from bot.logger import command_log
from bot.persistence import DatabaseConnector


class RoleManagementCog(commands.Cog):
    """Cog for functions regarding server roles."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

    @commands.group(name='module', invoke_without_command=True)
    @command_log
    async def toggle_module(self, ctx: commands.Context, *, str_modules: str):
        """Command Handler for the `module` command.

        Allows members to assign/remove so called mod roles to/from themselves. This way users can toggle text channels
        about specific courses to be visible or not to them. When the operation is finished, SAM will send an overview
        about the changes he did per direct message to the user who invoked the command.
        If the command is invoked outside of the configured role channel, the bot will post a short info that this
        command should only be invoked there and delete this message shortly after.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            str_modules (str): A string containing abbreviations of all the modules a user would like to toggle.
        """
        if ctx.channel.id != constants.CHANNEL_ID_ROLES:
            ctx.channel.send(value=f"Dieser Befehl wird nur in <#{constants.CHANNEL_ID_ROLES}> unterstützt. Bitte "
                                   f"versuche es dort noch einmal. ", delete_after=constants.TIMEOUT_INFORMATION)
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

                if role in ctx.author.roles:
                    await ctx.author.remove_roles(role, atomic=True, reason="Selbstständig entfernt via SAM.")
                    modules_removed.append(module_upper)
                else:
                    await ctx.author.add_roles(role, atomic=True, reason="Selbstständig zugewiesen via SAM.")
                    modules_added.append(module_upper)
            except commands.BadArgument:
                modules_error.append(module_upper)

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
            await ctx.send(f"Die Rolle \"**__{module_role}__**\" wurde erfolgreich zu den verfügbaren Modul-Rollen "
                           f"hinzugefügt.",
                           delete_after=constants.TIMEOUT_INFORMATION)
        except IntegrityError:
            await ctx.send(f"Die Rolle \"**__{module_role}__**\" gehört bereits zu den verfügbaren Modul-Rollen.",
                           delete_after=constants.TIMEOUT_INFORMATION)

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
        await ctx.send(f"Die Rolle \"**__{module_role}__**\" wurde aus den verfügbaren Modul-Rollen entfernt.",
                       delete_after=constants.TIMEOUT_INFORMATION)

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
            role = re.search(r"\"(.*)\"", error.args[0])  # Regex to get the text between two quotes.
            role = role.group(1) if role is not None else None

            await ctx.author.send(f"Die von dir angegebene Rolle \"**__{role}__**\" existiert leider nicht.")


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


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(RoleManagementCog(bot))
