"""Contains a Cog for all functionality regarding Moderation."""

import operator
import re
from datetime import datetime, timedelta
from typing import List, Optional, Union

import discord
from discord.ext import commands

from bot import singletons, constants as const
from bot.logger import command_log, log
from bot.moderation import ModmailStatus
from bot.persistence import DatabaseConnector
from bot.utility.time_parsing import get_future_timestamp, get_pretty_string_duration


class ModerationCog(commands.Cog):
    """Cog for Moderation Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(const.DB_FILE_PATH, const.DB_INIT_SCRIPT)

        # Static variables which are needed for running jobs created by the scheduler. A lot of data structures provided
        # by discord.py can't be pickled (serialized) which is why IDs are being used instead. For converting them into
        # usable objects, a bot/client object is needed, which should be the same for the whole application anyway. The
        # same goes for the db connector.
        ModerationCog.bot = self.bot
        ModerationCog.db_connector = self._db_connector

        # Channel instances
        self.ch_modlog = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CHANNEL_ID_MODLOG))
        self.ch_report = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CHANNEL_ID_REPORT))
        self.ch_modmail = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CHANNEL_ID_MODMAIL))
        self.ch_rules = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CHANNEL_ID_RULES))
        self.ch_server_news = bot.get_guild(int(const.SERVER_ID)).get_channel(int(const.CHANNEL_ID_NEWS))

        # Role instances
        self.role_moderator = bot.get_guild(int(const.SERVER_ID)).get_role(int(const.ROLE_ID_MODERATOR))
        self.role_muted = bot.get_guild(int(const.SERVER_ID)).get_role(int(const.ROLE_ID_MUTED))

    # A special method that registers as a commands.check() for every command and subcommand in this cog.
    # Only moderators can use the commands defined in this Cog except for `report` and `modmail`.
    def cog_check(self, ctx):
        if ctx.command.name in ["report", "modmail"]:
            return True
        return self.role_moderator in ctx.author.roles

    @commands.group(name='lockdown', hidden=True, invoke_without_command=True)
    @command_log
    async def lockdown(self, ctx: commands.Context,
                       ch_input: Optional[Union[discord.TextChannel, discord.VoiceChannel]]):
        """Command Handler for the `lockdown` command.

        Puts the current or specified channel in lockdown by removing the "write_messages" permission from the default
        role in it. An information regarding this action will be posted in the affected channel.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_input (Optional[Union[discord.TextChannel, discord.VoiceChannel]]): The channel specified by the user.
        """
        channel = ch_input if ch_input else ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)

        if overwrite.send_messages is not None and not overwrite.send_messages:
            await ctx.send("Dieser Kanal befindet sich bereits im Lockdown. :cop:")
            return

        confirmation_embed = _build_lockdown_confirmation_embed(channel)
        is_confirmed = await self._send_confirmation_dialog(ctx, confirmation_embed)

        if is_confirmed:
            overwrite.update(send_messages=False, connect=False)
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite,
                                          reason=f"Der Kanal wurde von {ctx.author} in einen Lockdown versetzt.")
            log.info("Channel [#%s] has been put into Lockdown.", channel)

            embed = _build_lockdown_embed()
            await channel.send(embed=embed)

            modlog_embed = _build_modlog_embed("Channel-Lockdown :lock:", color=const.EMBED_COLOR_MODLOG_LOCKDOWN,
                                               moderator=ctx.author, user=None, reason=None)
            await self.ch_modlog.send(embed=modlog_embed)

    @lockdown.command(name='lift')
    @command_log
    async def lockdown_lift(self, ctx: commands.Context,
                            ch_input: Optional[Union[discord.TextChannel, discord.VoiceChannel]]):
        """Command Handler for the `lift` subcommand of the `lockdown` command.

        Lifts the lockdown for the current or specified channel by granting the "write_messages" permission to the
        default role in it. An information regarding this action will be posted in the affected channel.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            ch_input (Optional[Union[discord.TextChannel, discord.VoiceChannel]]): The channel specified by the user.
        """
        channel = ch_input if ch_input else ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)

        if overwrite.send_messages is None or overwrite.send_messages:
            await ctx.send("Dieser Kanal befindet sich derzeit nicht im Lockdown. :face_with_raised_eyebrow:")
            return

        overwrite.update(send_messages=None, connect=None)
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite,
                                      reason=f"Der Lockdown wurde von {ctx.author} aufgehoben.")
        log.info("Lockdown for channel [#%s] has been lifted.", channel)

        embed = _build_lockdown_lift_embed()
        await channel.send(embed=embed)

        modlog_embed = _build_modlog_embed("Aufhebung: Channel-Lockdown :unlock:",
                                           color=const.EMBED_COLOR_MODLOG_REPEAL, moderator=ctx.author, user=None,
                                           reason=None)
        await self.ch_modlog.send(embed=modlog_embed)

    @lockdown.group(name='server', invoke_without_command=True)
    @command_log
    async def lockdown_server(self, ctx: commands.Context):
        """Command Handler for the `server` subcommand of the `lockdown` command.

        Puts the whole server in lockdown by removing the "write_messages" permission from the default role. An
        information regarding this action will be posted in the configured news channel of the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        role = ctx.guild.default_role
        permissions = role.permissions

        if not permissions.send_messages:
            await ctx.send("Der Server befindet sich bereits im Lockdown. :police_car::dash:")
            return

        confirmation_embed = _build_lockdown_confirmation_embed(None)
        is_confirmed = await self._send_confirmation_dialog(ctx, confirmation_embed)

        if is_confirmed:
            permissions.send_messages = False
            permissions.connect = False
            await role.edit(permissions=permissions, reason=f"Der Server wurde von {ctx.author} in einen Lockdown "
                                                            f"versetzt.")
            log.info("The whole Server has been put into Lockdown.")

            embed = _build_server_lockdown_embed()
            await self.ch_server_news.send(embed=embed)

            modlog_embed = _build_modlog_embed("Server-Lockdown :lock:", color=const.EMBED_COLOR_MODLOG_LOCKDOWN,
                                               moderator=ctx.author, user=None, reason=None)
            await self.ch_modlog.send(embed=modlog_embed)

    @lockdown_server.command(name='lift')
    @command_log
    async def lockdown_server_lift(self, ctx: commands.Context):
        """Command Handler for the `lift` subcommand of the command `lockdown server`.

        Lifts the server-wide lockdown by granting the "write_messages" permission to the default role. An information
        regarding this action will be posted in the configured news channel of the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        role = ctx.guild.default_role
        permissions = role.permissions

        if permissions.send_messages:
            await ctx.send("Der Server befindet sich derzeit nicht im Lockdown. :face_with_raised_eyebrow:")
            return

        permissions.send_messages = True
        permissions.connect = True
        await role.edit(permissions=permissions, reason=f"Der serverweite Lockdown wurde von {ctx.author} aufgehoben.")
        log.info("The server-wide Lockdown has been lifted.")

        embed = _build_server_lockdown_lift_embed()
        await self.ch_server_news.send(embed=embed)

        modlog_embed = _build_modlog_embed("Aufhebung: Server-Lockdown :unlock:",
                                           color=const.EMBED_COLOR_MODLOG_REPEAL,
                                           moderator=ctx.author, user=None, reason=None)
        await self.ch_modlog.send(embed=modlog_embed)

    @commands.command(name='warnings', hidden=True)
    @command_log
    async def get_warnings(self, ctx: commands.Context, user: discord.Member):
        """Command Handler for the `warnings` command.

        Posts an embed listing all the warnings the specified member has received.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose warnings have been requested.
        """
        warnings = self._db_connector.get_member_warnings(user.id)

        if warnings:
            embed = _build_warnings_embed(user, warnings)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Dieser Nutzer wurde bisher von niemanden verwarnt. :relieved:")

    @commands.group(name='warning', hidden=True, aliases=["warn"], invoke_without_command=True)
    @command_log
    async def warn_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the `warning` command.

        Warns the specified member. If enough warnings have been received, the bot will award configured punishments
        automatically.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose has been warned.
            reason (Optional[str]): The reason provided by the moderator.
        """
        self._db_connector.add_member_warning(user.id, datetime.utcnow(), reason)
        log.info("Member %s has been warned.", user)

        await ctx.send(f"{user.mention} wurde verwarnt. :warning:")

        embed = _build_mod_action_embed("Verwarnungs", f"Du wurdest von **__{ctx.author}__** verwarnt.", reason,
                                        self.ch_rules)
        await user.send(embed=embed)

        modlog_embed = _build_modlog_embed("Verwarnung :warning:", color=const.EMBED_COLOR_MODLOG_WARN,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

        await self.check_warnings(ctx, user)

    @warn_user.command(name='remove')
    @command_log
    async def remove_warning(self, ctx: commands.Context, warning_id: int, *, reason: Optional[str]):
        """Command Handler for the subcommand `remove` of the command `warning`.

        Removes the warning with the specified id from a member.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            warning_id (int): The id of the warning which should be removed.
            reason (Optional[str]): The reason provided by the moderator.
        """
        user_id = self._db_connector.get_warning_userid(warning_id)

        if not user_id:
            raise commands.BadArgument("The warning with the specified ID doesn't exist.")

        user = self.bot.get_guild(int(const.SERVER_ID)).get_member(user_id)

        self._db_connector.remove_member_warning(warning_id)
        log.info("Warning #%s has been removed from %s.", warning_id, user)

        # Check warnings and recalculate expiration date if needed
        await self.check_warnings(ctx, user, False)

        modlog_embed = _build_modlog_embed("Aufhebung: Verwarnung", color=const.EMBED_COLOR_MODLOG_REPEAL,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

        await ctx.send(f"Die Verwarnung für {user.mention} wurde erfolgreich aufgehoben. :white_check_mark:")

    @remove_warning.error
    async def remove_warning_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for subcommand `remove` of the command `warning`.

        Handles an exception which occurs if the specified warning id is invalid.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send("Ich konnte leider keine Verwarnung mit der von dir angegebenen ID finden. :cold_sweat: "
                           "Hast du dich möglicherweise vertippt?")

    @warn_user.command(name='clear')
    @command_log
    async def clear_warnings(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the subcommand `clear` of the command `warning`.

        Removes all warnings given to the specified member.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose warnings should be cleared.
            reason (Optional[str]): The reason provided by the moderator.
        """
        self._db_connector.remove_member_warnings(user.id)
        log.info("All warnings have been removed from %s.", user)

        # Remove scheduler job from DB because it isn't needed anymore
        clear_warnings_job = singletons.SCHEDULER.get_job(f"warns_expire_{user.id}")
        if clear_warnings_job:
            clear_warnings_job.remove()

        modlog_embed = _build_modlog_embed("Aufhebung: Alle Verwarnungen", color=const.EMBED_COLOR_MODLOG_REPEAL,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

        await ctx.send(f"Alle Verwarnungen für {user.mention} wurden erfolgreich aufgehoben. :white_check_mark:")

    @commands.command(name='mute', hidden=True)
    @command_log
    async def mute_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the `mute` command.

        Mutes the specified member server-wide. This means the user won't be able to write messages, join voice channels
        or even add reactions. This is done by granting the configured mute role.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be muted.
            reason (Optional[str]): The reason provided by the moderator.
        """
        if self.role_muted in user.roles:
            await ctx.send("Dieser Nutzer ist bereits stummgeschalten. :flushed:")
            return

        await user.add_roles(self.role_muted, reason=reason)
        log.info("Member %s has been muted.", user)

        await ctx.send(f"{user.mention} wurde stummgeschalten. :mute:")
        embed = _build_mod_action_embed("Stummschaltungs", f"Du wurdest von **__{ctx.author}__** auf unbestimmte Zeit "
                                                           f"stummgeschalten.", reason, self.ch_rules)
        await user.send(embed=embed)

        modlog_embed = _build_modlog_embed("Stummschaltung :mute:", color=const.EMBED_COLOR_MODLOG_MUTE,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

    @commands.command(name='unmute', hidden=True)
    @command_log
    async def unmute_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the `unmute` command.

        Unmutes the specified member on the server. This is done by removing the configured mute role from him.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be unmuted.
            reason (Optional[str]): The reason provided by the moderator.
        """
        if self.role_muted not in user.roles:
            await ctx.send("Dieser Nutzer ist nicht stummgeschalten. :thinking:")
            return

        # Check if the user has been tempmuted and remove the job in the DB if that's the case
        unmute_job = singletons.SCHEDULER.get_job(f"tempmute_expire_{user.id}")
        if unmute_job:
            unmute_job.remove()

        await user.remove_roles(self.role_muted, reason=reason)
        log.info("Member %s has been unmuted.", user)

        modlog_embed = _build_modlog_embed("Aufhebung: Stummschaltung :speaker:",
                                           color=const.EMBED_COLOR_MODLOG_REPEAL,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

        await ctx.send(f"{user.mention} ist nicht mehr stummgeschalten. :speaker:")
        await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr stummgeschalten! :speaker: Versuch "
                        f"bitte, dich in Zukunft besser an unsere {self.ch_rules.mention} zu halten, da wir ansonsten "
                        f"gezwungen sind, härtere Strafen zu verhängen. :scales:")

    @commands.command(name='tempmute', hidden=True)
    @command_log
    async def tempmute_user(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: Optional[str],
                            bot_activated: bool = False):
        """Command Handler for the `tempmute` command.

        Temporarily mutes the specified member server-wide for the duration given. This means the user won't be able to
        write messages, join voice channels or even add reactions. This is done by granting the configured mute role.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be muted.
            duration (str): The amount of time the user should be banned from the server.
                            Visit https://github.com/wroberts/pytimeparse for a complete list of accepted formats.
            reason (Optional[str]): The reason provided by the moderator.
            bot_activated (bool): A boolean indicating if this command was automatically invoked by the bot.
        """
        if self.role_muted in user.roles:
            await ctx.send("Dieser Nutzer ist bereits stummgeschalten. :flushed:")
            return

        prosecutor = self.bot.user if bot_activated else ctx.author
        run_date = get_future_timestamp(duration)
        pretty_duration = get_pretty_string_duration(duration)

        await user.add_roles(self.role_muted, reason=reason)
        log.info("Member %s has been muted until %s.", user, run_date.strftime("%d.%m.%Y %H:%M:%S"))

        await ctx.send(f"{user.mention} wurde für {pretty_duration} stummgeschalten. :mute:")
        embed = _build_mod_action_embed("Tempmute", f"Du wurdest von **__{prosecutor}__** für {pretty_duration} "
                                                    f"stummgeschalten.", reason, self.ch_rules)
        await user.send(embed=embed)

        details = "Endet in {0} ({1})".format(pretty_duration, run_date.strftime("%d.%m.%Y %H:%M:%S"))
        modlog_embed = _build_modlog_embed("Temporäre Stummschaltung :mute:", color=const.EMBED_COLOR_MODLOG_MUTE,
                                           moderator=ctx.author, user=user, reason=reason, details=details)
        await self.ch_modlog.send(embed=modlog_embed)

        singletons.SCHEDULER.add_job(_scheduled_unmute_user, trigger="date", run_date=run_date, args=[user.id],
                                     id=f"tempmute_expire_{user.id}", replace_existing=True)

    @commands.command(name='ban', hidden=True)
    @command_log
    async def ban_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str],
                       bot_activated: bool = False):
        """Command Handler for the `ban` command.

        Bans the specified member from the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be banned.
            reason (Optional[str]): The reason provided by the moderator.
            bot_activated (bool): A boolean indicating if this command was automatically invoked by the bot.
        """
        prosecutor = self.bot.user if bot_activated else ctx.author

        embed = _build_mod_action_embed("Bann", "Du wurdest durch **__{0}__** von **__{1}__** gebannt."
                                        .format(prosecutor, self.bot.get_guild(int(const.SERVER_ID))),
                                        reason, self.ch_rules)
        await user.send(embed=embed)

        await user.ban(reason=reason, delete_message_days=0)
        log.info("Member %s has been banned from the server.", user)

        await ctx.send(f"{user.mention} wurde gebannt. :do_not_litter:")

        modlog_embed = _build_modlog_embed("Server-Bann :do_not_litter:", color=const.EMBED_COLOR_MODLOG_BAN,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

    @commands.command(name='tempban', hidden=True)
    @command_log
    async def tempban_user(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: Optional[str],
                           bot_activated: bool = False):
        """Command Handler for the `tempban` command.

        Temporarily bans the specified member from the server for the duration given.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be banned.
            duration (str): The amount of time the user should be banned from the server.
                            Visit https://github.com/wroberts/pytimeparse for a complete list of accepted formats.
            reason (Optional[str]): The reason provided by the moderator.
            bot_activated (bool): A boolean indicating if this command was automatically invoked by the bot.
        """
        prosecutor = self.bot.user if bot_activated else ctx.author
        run_date = get_future_timestamp(duration)
        pretty_duration = get_pretty_string_duration(duration)

        embed = _build_mod_action_embed("TempBann", "Du wurdest durch **__{0}__** von **__{1}__** für {2} gebannt."
                                        .format(prosecutor, self.bot.get_guild(int(const.SERVER_ID)),
                                                pretty_duration), reason, self.ch_rules)
        await user.send(embed=embed)

        await user.ban(reason=reason, delete_message_days=0)
        log.info("Member %s has been banned from the server until %s.", user, run_date.strftime("%d.%m.%Y %H:%M:%S"))

        await ctx.send(f"{user.mention} wurde für {pretty_duration} gebannt. :do_not_litter:")

        modlog_embed = _build_modlog_embed("Temporärer Server-Bann :do_not_litter:",
                                           color=const.EMBED_COLOR_MODLOG_BAN,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

        singletons.SCHEDULER.add_job(_scheduled_unban_user, trigger="date", run_date=run_date, args=[user.id])

    @tempmute_user.error
    @tempban_user.error
    async def temp_action_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for commands imposing temporary punishments.

        Handles an exception which occurs if the specified amount of time is invalid.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, ValueError):
            await ctx.send("**__Error:__** Die angegebene Zeitdauer ist ungültig. :clock330:")

    @commands.command(name='kick', hidden=True)
    @command_log
    async def kick_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the `kick` command.

        Kicks the specified member from the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be kicked.
            reason (Optional[str]): The reason provided by the moderator.
        """
        embed = _build_mod_action_embed("Kick", "Du wurdest durch **__{0}__** von **__{1}__** gekickt."
                                        .format(ctx.author, self.bot.get_guild(int(const.SERVER_ID))),
                                        reason, self.ch_rules)
        await user.send(embed=embed)

        await user.kick(reason=reason)
        log.info("Member %s has been kicked from the server.", user)

        await ctx.send(f"{user.mention} wurde gekickt. :anger:")

        modlog_embed = _build_modlog_embed("Server-Kick :anger:", color=const.EMBED_COLOR_MODLOG_KICK,
                                           moderator=ctx.author, user=user, reason=reason)
        await self.ch_modlog.send(embed=modlog_embed)

    @commands.command(name='namehistory', hidden=True, aliases=["aka"])
    @command_log
    async def member_nicknames(self, ctx: commands.Context, *, user: discord.Member):
        """Command Handler for the `namehistory` command.

        Posts an embed listing all the different names which the specified member has used on the server. Additional
        timestamps representing when the members name has been changed are also provided.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose names are being requested.
        """
        nicknames = self._db_connector.get_member_names(user.id)
        description = "Es werden maximal die __letzten {0} Namen__ eines Mitglieds angezeigt, welche auf diesem " \
                      "Server verwendet wurden." \
            .format(const.LIMIT_NICKNAMES)

        if nicknames:
            embed = discord.Embed(title=f"Namensverlauf von {user} :page_with_curl:", description=description,
                                  color=const.EMBED_COLOR_MODERATION, timestamp=datetime.utcnow())
            embed.set_footer(text="Stand")
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(name=user.display_name, value="aktuell")

            time_difference = datetime.utcnow().astimezone().utcoffset()
            for name in nicknames[:const.LIMIT_NICKNAMES]:
                timestamp = datetime.strptime(name[1], '%Y-%m-%d %H:%M:%S.%f')
                local_timestamp = timestamp + time_difference if time_difference else timestamp
                str_time = local_timestamp.strftime("%d.%m.%Y\num *%X*")
                embed.add_field(name=name[0], value=f"bis {str_time}")

            await ctx.send(embed=embed)
        else:
            await ctx.send(f"**__{user}__** hatte bisher keinen anderen Namen auf diesem Server. "
                           ":face_with_monocle:")

    @commands.command(name='newmembers', hidden=True)
    @command_log
    async def new_members(self, ctx: commands.Context, amount: int = 12):
        """Command Handler for the `newmembers` command.

        Posts an embed listing the specified amount of new members on the server and individual timestamps representing
        when exactly a user has joined.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            amount (int): The amount of new members which should be displayed.
        """
        if amount > const.LIMIT_NEW_MEMBERS:
            raise commands.BadArgument("The amount of new members to be displayed is too big.")

        members = sorted(ctx.guild.members, key=operator.attrgetter("joined_at"), reverse=True)[:amount]
        description = "Füge an das Ende des Befehls eine beliebige Zahl an, um die Menge an neuen Mitgliedern " \
                      "individuell festzulegen. **(max. {0})**".format(const.LIMIT_NEW_MEMBERS)

        embed = discord.Embed(title="Neueste Mitglieder :couple:", color=const.EMBED_COLOR_MODERATION,
                              description=description, timestamp=datetime.utcnow())
        embed.set_footer(text="Stand")

        time_difference = datetime.utcnow().astimezone().utcoffset()
        for member in members:
            local_joined_at = member.joined_at + time_difference
            embed.add_field(name=str(member), value=datetime.strftime(local_joined_at, "%d.%m.%Y | *%X*"))

        await ctx.send(embed=embed)

    @new_members.error
    async def new_members_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `newmembers` command.

        Handles an exception which occurs if the specified amount of new members is smaller than one or bigger the
        specified maximum.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send("**__Error:__** Die angegebene Menge an neuen Mitgliedern ist entweder nicht numerisch oder "
                           "leider zu groß. Sie darf **{0}** nicht überschreiten.".format(const.LIMIT_NEW_MEMBERS))

    @commands.command(name='avatar', hidden=True)
    @command_log
    async def user_avatar(self, ctx: commands.Context, *, user: discord.Member):
        """Command Handler for the `avatar` command.

        Posts an embed containing the currently used avatar by the specified user and links to identical versions but
        with different file types.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose avatar is being requested.
        """
        description = "[.jpg]({0}) | [.png]({1}) | [.webp]({2})".format(user.avatar_url_as(format="jpg"),
                                                                        user.avatar_url_as(format="png"),
                                                                        user.avatar_url_as(format="webp"))

        if user.is_avatar_animated():
            description += " | [.gif]({0})".format(user.avatar_url_as(format="gif"))

        embed = discord.Embed(title=f"Avatar von {user}", color=const.EMBED_COLOR_MODERATION,
                              timestamp=datetime.utcnow(), description=description)
        embed.set_footer(text="Erstellt am")
        embed.set_image(url=user.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=["info"], hidden=True)
    @command_log
    async def user_info(self, ctx: commands.Context, *, user: discord.Member):
        """Command Handler for the `info` command.

        Posts an embed containing various information about the member specified. This includes creation date, join date
        the currently used name on the server, server roles and the date since when he's boosting the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose information is being requested.
        """
        time_difference = datetime.utcnow().astimezone().utcoffset()

        created_at = datetime.strftime(user.created_at + time_difference, "%d.%m.%Y | %X")
        joined_at = datetime.strftime(user.joined_at + time_difference, "%d.%m.%Y | %X")
        roles = " ".join([role.mention for role in reversed(user.roles[1:])]) if len(user.roles) > 1 else "\U0000274C" \
                                                                                                          " - Keine."
        num_total_roles = len(user.roles)
        if len(roles) > 1024:
            roles = _trim_role_string(roles, num_total_roles)

        description = f"**Name am Server:** {user.display_name} | {user.mention}"

        if user.premium_since:
            premium_since = datetime.strftime(user.premium_since + time_difference, "%d.%m.%Y %X")
            description += f"\n**Boostet seit:** {premium_since}"

        embed = discord.Embed(title=str(user), description=description, color=const.EMBED_COLOR_MODERATION)
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text=f"UserID: {user.id}")
        embed.add_field(name="Erstellt am:", value=created_at, inline=True)
        embed.add_field(name="Beigetreten am:", value=joined_at, inline=True)
        embed.add_field(name="Rollen:", value=roles, inline=False)

        await ctx.send(embed=embed)

    @get_warnings.error
    @warn_user.error
    @clear_warnings.error
    @mute_user.error
    @unmute_user.error
    @tempmute_user.error
    @ban_user.error
    @tempban_user.error
    @kick_user.error
    @member_nicknames.error
    @user_info.error
    @user_avatar.error
    async def convert_user_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for commands which take a username and try to convert them to a user/member object.

        Handles an exception which may occurs during the execution of commands when trying to convert a username to a
        user/member object. The global error handler will still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            regex = re.search(r"\"(.*)\"", error.args[0])  # Regex for getting text between two quotes.
            user = regex.group(1) if regex else None

            await ctx.send(f"**__Error:__** Ich konnte leider keinen Nutzer namens **{user}** finden. :confused: "
                           f"Hast du dich möglicherweise vertippt?")

    @commands.command(name='report')
    @command_log
    async def report_user(self, ctx: commands.Context, offender: discord.Member, *, description: str):
        """Command Handler for the `report` command.

        Allows users to report other members to the moderators by using their ID, name + discriminator, name, nickname
        or by simply mentioning them. Everything after that will be used as the description for the report. The
        complete report will then be posted in the configured report channel, which (hopefully) can only be accessed by
        by the moderators.
        If no member could be found, the user who invoked the command will be informed via a direct message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            offender (discord.Member): The person accused of doing something wrong.
            description (str): A description of why this person has been reported.
        """
        if not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        embed = _create_report_embed(offender, ctx.author, ctx.channel, ctx.message, description)
        await self.ch_report.send(embed=embed)
        log.info("Member %s has been reported to the moderators.", offender)

    @report_user.error
    async def report_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `report` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        await ctx.message.delete()

        if isinstance(error, commands.BadArgument):
            regex = re.search(r"\"(.*)\"", error.args[0])  # Regex for getting text between two quotes.
            user = regex.group(1) if regex else None

            await ctx.author.send(f"Ich konnte leider keinen Nutzer namens **{user}** finden. :confused: Hast du dich "
                                  f"möglicherweise vertippt?")

    @commands.command(name='purge', hidden=True)
    @command_log
    async def purge_messages(self, ctx: commands.Context, channel: Optional[discord.TextChannel], amount: int):
        """Command Handler for the `purge` command.

        Allows moderators to delete the specified amount of messages in a channel. After invocation, a confirmation
        message with all relevant information will be posted by SAM which the author needs to confirm in order to
        proceed with the operation. If the moderator chooses an invalid amount of messages (negative or higher than the
        configured limit), a temporary error message will be posted by the bot to inform the user.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            channel (Optional[discord.TextChannel]): The channel in which the messages should be deleted.
            amount (int): The amount of messages which need to be purged.
        """
        purge_channel = channel if channel else ctx.channel

        if amount <= 0 or amount > const.LIMIT_PURGE_MESSAGES:
            raise commands.BadArgument("Invalid amount of messages to be purged was passed. "
                                       "Maximum: {0}, Passed limit: {1}".format(const.LIMIT_PURGE_MESSAGES, amount))

        confirmation_embed = _build_purge_confirmation_embed(purge_channel, amount)
        is_confirmed = await self._send_confirmation_dialog(ctx, confirmation_embed)
        is_posted_in_purge_channel = purge_channel is ctx.channel
        if is_confirmed:
            deleted_messages = await purge_channel.purge(limit=amount + 1 if is_posted_in_purge_channel else amount)
            deleted_messages_count = len(deleted_messages)-1 if is_posted_in_purge_channel else len(deleted_messages)
            await purge_channel.send(
                '**Ich habe __{0} Nachrichten__ erfolgreich gelöscht.**'.format(deleted_messages_count),
                delete_after=const.TIMEOUT_INFORMATION)
            log.info("SAM deleted %s messages in [#%s]", deleted_messages_count, purge_channel)

            details = f"Deleted {deleted_messages_count} messages in channel {purge_channel.mention}"
            embed = _build_modlog_embed("Purge", color=const.EMBED_COLOR_MODLOG_PURGE,
                                        moderator=ctx.author, user=None, reason=None, details=details)
            await self.ch_modlog.send(embed=embed)

    @purge_messages.error
    async def purge_messages_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `purge` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send(content="**__Error:__** Die Anzahl der Nachrichten welche gelöscht werden sollen, muss im "
                                   "__positiven Bereich__ liegen und darf __{0} nicht überschreiten__!"
                           .format(const.LIMIT_PURGE_MESSAGES),
                           delete_after=const.TIMEOUT_INFORMATION)

    @commands.group(name='modmail', invoke_without_command=True)
    @command_log
    async def modmail(self, ctx: commands.Context, *, message):
        """Command Handler for the `modmail` command.

        Allows users to write a message to all the moderators of the server. The message is going to be posted in a
        specified modmail channel which can (hopefully) only be accessed by said moderators. The user who invoked the
        command will get a confirmation via DM and the invocation will be deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            message (str): The message which should be send to the moderators.
        """
        if ctx.channel.type not in [discord.ChannelType.private, discord.ChannelType.group] \
                and not self._db_connector.is_botonly(ctx.channel.id):
            await ctx.message.delete()

        msg_author_name = str(ctx.message.author)
        msg_timestamp = ctx.message.created_at

        image = next((a for a in ctx.message.attachments if a.filename.split(".")[-1].lower()
                      in ["jpg", "jpeg", "png", "gif"]), None)
        files = [await a.to_file() for a in ctx.message.attachments if a != image]

        embed = discord.Embed(title="Status: Offen", color=const.EMBED_COLOR_MODMAIL_OPEN,
                              timestamp=datetime.utcnow(), description=message)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
        embed.set_footer(text="Erhalten am")

        if image:
            embed.set_image(url=image.url)

        msg_modmail = await self.ch_modmail.send(embed=embed, files=files)
        self._db_connector.add_modmail(msg_modmail.id, msg_author_name, msg_timestamp)
        log.info("Member %s submitted a modmail.", ctx.author)

        await msg_modmail.add_reaction(const.EMOJI_MODMAIL_DONE)
        await msg_modmail.add_reaction(const.EMOJI_MODMAIL_ASSIGN)

        embed_confirmation = embed.to_dict()
        embed_confirmation["title"] = "Deine Nachricht:"
        embed_confirmation["color"] = const.EMBED_COLOR_INFO
        embed_confirmation = discord.Embed.from_dict(embed_confirmation)
        await ctx.author.send("Deine Nachricht wurde erfolgreich an die Moderatoren weitergeleitet!\n"
                              "__Hier deine Bestätigung:__", embed=embed_confirmation)

    @modmail.command(name='get')
    @command_log
    async def get_modmail_with_status(self, ctx: commands.Context, *, status: str):
        """Command Handler for the modmail subcommand `get`.

        Allows moderators to generate an embedded message (Embed) in the modmail channel which contains a list of all
        modmail with the specified status. Each list element is a hyperlink which, if clicked, brings you to the
        corresponding modmail message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            status (str): The status specified by the moderator.
        """
        if ctx.channel.id != self.ch_modmail.id:
            if not self._db_connector.is_botonly(ctx.channel.id):
                await ctx.message.delete()

            await ctx.author.send(f"Dieser Befehl wird nur in {self.ch_modmail.mention} unterstützt. Bitte "
                                  f"versuche es dort noch einmal.")
            return

        enum_status = ModmailStatus[status.upper()]
        modmail = self._db_connector.get_all_modmail_with_status(enum_status)

        embed = _modmail_create_list_embed(enum_status, modmail)
        await self.ch_modmail.send(embed=embed)

    @get_modmail_with_status.error
    async def get_modmail_error(self, _ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `get` subcommand of the `modmail` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            _ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, KeyError):
                await self.ch_modmail.send("**__Error:__** Ungültiger Modmail-Status `{0}`."
                                           .format(error.original.args[0].title()))

            elif isinstance(error.original, ValueError):
                regex = re.search(r"\'(.*)\'", error.args[0])  # Regex for getting text between two quotes.
                status = regex.group(1) if regex else None

                await self.ch_modmail.send(f"**__Error:__** Nicht unterstützter Modmail-Status `{status}`.")

    @commands.Cog.listener(name='on_raw_reaction_add')
    async def modmail_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been added by a user.

        If the affected message is in the configured modmail channel and the added reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_modmail.id and not payload.member.bot:
            modmail = await self.ch_modmail.fetch_message(payload.message_id)
            reaction = next(x for x in modmail.reactions if x.emoji == payload.emoji.name)

            if payload.emoji.name in (const.EMOJI_MODMAIL_DONE, const.EMOJI_MODMAIL_ASSIGN) \
                    and reaction.count <= 2:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, True)
                await modmail.edit(embed=new_embed)
            else:
                await reaction.remove(payload.member)

    @commands.Cog.listener(name='on_raw_reaction_remove')
    async def modmail_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Event listener which triggers if a reaction has been removed.

        If the affected message is in the configured modmail channel and the removed reaction is one of the two emojis
        specified in constants.py, changes will be made to the current status of the modmail and visualized accordingly
        by the corresponding embed.

        Args:
            payload (discord.RawReactionActionEvent): The payload for the triggered event.
        """
        if payload.channel_id == self.ch_modmail.id:
            modmail = await self.ch_modmail.fetch_message(payload.message_id)

            if payload.emoji.name in (const.EMOJI_MODMAIL_DONE, const.EMOJI_MODMAIL_ASSIGN) \
                    and next(x for x in modmail.reactions if x.emoji == payload.emoji.name).count <= 1:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, False)
                await modmail.edit(embed=new_embed)

    async def check_warnings(self, ctx: commands.Context, user: discord.Member, was_warning_added: bool = True):
        """Method which checks the amount of warnings a user has and punishes him if necessary. It also creates/updates
        scheduler jobs to remove them after some time.

        The individual punishments and the amount of warnings needed to trigger it are stored in a dictionary and can
        therefore be easily modified or expanded. If a specific limit has been reached the bot simply invokes one of his
        own mod commands.
        For the expiration of warnings, a specific formular is being used to calculate the amount of weeks a warning is
        valid. After that, a job for the scheduler will be created, or updated, if one already exists.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member which has been warned.
            was_warning_added (bool): Specifies if a warning has been added or not to prevent that a user gets punished multiple times.
        """
        warnings = self._db_connector.get_member_warnings(user.id)
        cntr_warnings = len(warnings) if warnings else 0
        punishments = {
            const.LIMIT_WARNINGS_LVL_1:      ("tempmute", "1 week"),
            const.LIMIT_WARNINGS_LVL_2:      ("tempban", "2 weeks"),
            const.LIMIT_WARNINGS_LVL_3:      ("ban", None)
        }

        if cntr_warnings != 0:
            # Punishment
            if was_warning_added and (cntr_warnings in punishments):
                punishment = punishments[cntr_warnings]
                reason = f"Automatisch durchgeführte Aktion aufgrund von insgesamt {cntr_warnings} Verwarnungen."

                if punishment[1]:
                    await ctx.invoke(self.bot.get_command(punishment[0]), user=user, duration=punishment[1], reason=reason,
                                     bot_activated=True)
                else:
                    await ctx.invoke(self.bot.get_command(punishment[0]), user=user, reason=reason, bot_activated=True)

            # Expiration Date
            weeks = (cntr_warnings + 1) * 4 if cntr_warnings > 1 else 4
            run_date = get_future_timestamp("{0}w".format(weeks))

            if not was_warning_added:
                expiration_job = singletons.SCHEDULER.get_job(f"warns_expire_{user.id}")
                run_date = expiration_job.next_run_time - timedelta(weeks=(((cntr_warnings + 2) * 4) - weeks))

            singletons.SCHEDULER.add_job(_scheduled_clear_warnings, trigger="date", run_date=run_date, args=[user.id],
                                         id=f"warns_expire_{user.id}", replace_existing=True)
        else:
            # Remove scheduler job from DB because it isn't needed anymore
            singletons.SCHEDULER.get_job(f"warns_expire_{user.id}").remove()

    async def change_modmail_status(self, modmail: discord.Message, emoji: str, reaction_added: bool) -> discord.Embed:
        """Method which changes the status of a modmail depending on the given emoji.

        This is done by changing the StatusID in the database for the respective message and visualized by changing the
        color of the Embed posted on Discord.

        Args:
            modmail (discord.Message): The Discord message in the specified modmail channel.
            emoji (str): A String containing the Unicode for a specific emoji.
            reaction_added (Boolean): A boolean indicating if a reaction has been added or removed.

        Returns:
            discord.Embed: An adapted Embed corresponding to the new modmail status.
        """
        dict_embed = modmail.embeds[0].to_dict()
        dict_embed["title"] = "Status: "

        if reaction_added and emoji == const.EMOJI_MODMAIL_DONE:
            await modmail.clear_reaction(const.EMOJI_MODMAIL_ASSIGN)
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.CLOSED)
            dict_embed["title"] += "Erledigt"
            dict_embed["color"] = const.EMBED_COLOR_MODMAIL_CLOSED
        elif reaction_added and emoji == const.EMOJI_MODMAIL_ASSIGN:
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.ASSIGNED)
            dict_embed["title"] += "In Bearbeitung"
            dict_embed["color"] = const.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)
            dict_embed["title"] += "Offen"
            dict_embed["color"] = const.EMBED_COLOR_MODMAIL_OPEN

            if emoji == const.EMOJI_MODMAIL_DONE:
                await modmail.add_reaction(const.EMOJI_MODMAIL_ASSIGN)

        return discord.Embed.from_dict(dict_embed)

    async def _send_confirmation_dialog(self, ctx: commands.Context, embed: discord.Embed) -> bool:
        """Posts a confirmation dialog and returns the users answer.

        Posts an embed and adds reactions for confirmation and cancellation to it. A bool indicating if the user has
        confirmed or aborted the operation will be returned. Regardless of the return value the embed will be deleted
        shortly after.

        Args:
            ctx (commands.Context): The context of invocation. Used to send the message.
            embed (discord.Embed): The embed that will be posted. It should contain some explanation about what should
            be confirmed.

        Returns:
            (bool):A bool representing the users decision.
        """
        message = await ctx.send(embed=embed, delete_after=const.TIMEOUT_USER_SELECTION)
        await message.add_reaction(const.EMOJI_CONFIRM)
        await message.add_reaction(const.EMOJI_CANCEL)

        def check_reaction(_reaction, user):
            return user == ctx.author and _reaction.message.id == message.id and \
                   str(_reaction.emoji) in [const.EMOJI_CANCEL, const.EMOJI_CONFIRM]

        reaction = await self.bot.wait_for('reaction_add', timeout=const.TIMEOUT_USER_SELECTION,
                                           check=check_reaction)
        await message.delete()

        if str(reaction[0].emoji) == const.EMOJI_CANCEL:
            await ctx.message.delete()

        return str(reaction[0].emoji) == const.EMOJI_CONFIRM

    @commands.Cog.listener(name='on_member_update')
    @commands.Cog.listener(name='on_user_update')
    async def name_change(self, before: discord.Member, after: discord.Member):
        """Event listener which triggers if a member has changed his name.

        The old name (or serverwide nickname) will be saved along with the user id and a timestamp in our database.
        This way we can have an overview about who had which name on the server during a specific timespan.

        Args:
            before (discord.Member): The old member object before the update.
            after (discord.Member): The new member object after the update.
        """
        if before.display_name != after.display_name:
            self._db_connector.add_member_name(before.id, before.display_name, datetime.utcnow())


async def _scheduled_unmute_user(user_id: int):
    """Method which is being called by the scheduler if the specified amount of time for the corresponding tempmute has
    ran out.

    Unmutes a user with the specified ID on a specific server.

    Args:
        user_id (int): The id of the user who should be unmuted.
    """
    guild = ModerationCog.bot.get_guild(int(const.SERVER_ID))
    user = guild.get_member(int(user_id))
    role = guild.get_role(int(const.ROLE_ID_MUTED))
    ch_rules = guild.get_channel(int(const.CHANNEL_ID_RULES))
    ch_modlog = guild.get_channel(int(const.CHANNEL_ID_MODLOG))

    await user.remove_roles(role, reason="Die für den Tempmute festgelegte Zeitdauer ist ausgelaufen.")
    await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr stummgeschalten! :speaker: Versuch "
                    f"bitte, dich in Zukunft besser an unsere {ch_rules.mention} zu halten, da wir ansonsten "
                    f"gezwungen sind, härtere Strafen zu verhängen. :scales:")

    modlog_embed = _build_modlog_embed("Aufhebung: Temporäre Stummschaltung :speaker:",
                                       color=const.EMBED_COLOR_MODLOG_REPEAL, moderator=ModerationCog.bot.user,
                                       user=user, reason="Automatisch durchgeführte Aktion, da die spezifizierte Dauer "
                                                         "abgelaufen ist.")
    await ch_modlog.send(embed=modlog_embed)


async def _scheduled_unban_user(user_id: int):
    """Method which is being called by the scheduler if the specified amount of time for the corresponding tempban has
    ran out.

    Unbans a user with the specified ID on a specific server.

    Args:
        user_id (int): The id of the user who should be unbanned.
    """
    guild = ModerationCog.bot.get_guild(int(const.SERVER_ID))
    user = await ModerationCog.bot.fetch_user(int(user_id))
    ch_rules = guild.get_channel(int(const.CHANNEL_ID_RULES))
    ch_modlog = guild.get_channel(int(const.CHANNEL_ID_MODLOG))

    await user.unban(reason="Die für den Tempban festgelegte Zeitdauer ist ausgelaufen.")
    await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr von **__{guild}__** gebannt! :unlock: "
                    f"Versuch bitte, dich in Zukunft besser an unsere {ch_rules.mention} zu halten, da wir ansonsten "
                    f"gezwungen sind, dich dauerhaft zu bannen. :scales:")

    modlog_embed = _build_modlog_embed("Aufhebung: Temporärer Server-Bann", color=const.EMBED_COLOR_MODLOG_REPEAL,
                                       moderator=ModerationCog.bot.user, user=user,
                                       reason="Automatisch durchgeführte Aktion, da die spezifizierte Dauer abgelaufen "
                                              "ist.")
    await ch_modlog.send(embed=modlog_embed)


async def _scheduled_clear_warnings(user_id: int):
    """Method which is being called by the scheduler if the expiration date of someones warnings has been reached.

    Clears all warnings given to the specified member.

    Args:
        user_id (int): The id of the user whose warnings should be removed.
    """
    guild = ModerationCog.bot.get_guild(int(const.SERVER_ID))
    user = guild.get_member(int(user_id))
    ch_modlog = guild.get_channel(int(const.CHANNEL_ID_MODLOG))

    ModerationCog.db_connector.remove_member_warnings(user.id)
    log.info("All warnings have been removed from %s.", user)

    modlog_embed = _build_modlog_embed("Aufhebung: Alle Verwarnungen", color=const.EMBED_COLOR_MODLOG_REPEAL,
                                       moderator=ModerationCog.bot.user, user=user,
                                       reason="Automatisch durchgeführte Aktion, da die spezifizierte Dauer abgelaufen "
                                              "ist.")
    await ch_modlog.send(embed=modlog_embed)


def _build_modlog_embed(action: str, color: discord.Colour, moderator: Union[discord.Member, discord.ClientUser],
                        user: Optional[discord.Member], reason: Optional[str],
                        details: Optional[str] = None) -> discord.Embed:
    """Creates an embed which gets posted in the configured modlog channel.

     The embed serves as an information for other moderators about what happend on the server and is therefore in
     general nothing more than a simple log message. It contains the moderator who performed the action, the affected
     member (if any) and the optional reason provided by said moderator why this has happened, as well as optional
     details about the incident.

    Returns:
        (discord.Embed): The info embed.
    """
    description = f"**Betroffener:** {user}\n" if user else ""
    description += f"**Moderator:** {moderator}"
    if reason:
        description += f"\n**Begründung:** {reason}"
    if details:
        description += f"\n**Details:** {details}"

    return discord.Embed(title=action, color=color, description=description)


def _build_lockdown_embed() -> discord.Embed:
    """Creates an embed which informs members that the current channel has been locked down.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Dieser Kanal befindet sich aufgrund von Unruhen derzeit im Lockdown, weswegen das Versenden " \
                  "von Nachrichten vorübergehend nicht möglich ist. :mailbox_with_no_mail:\n\nDie Moderatoren sind " \
                  "bemüht, die Ordnung schnellstmöglich wiederherzustellen. Bitte haltet davon ab, sie bezüglich der " \
                  "aktuellen Situation zu kontaktieren, da dies die Wiedereröffnung des Kanals nur unnötig verzögern " \
                  "würde.\n\n**__Wir bitten um Verständnis.__ :heart:**"

    embed = discord.Embed(title=":rotating_light: LOCKDOWN :rotating_light:", color=const.EMBED_COLOR_WARNING,
                          description=description)

    return embed


def _build_server_lockdown_embed() -> discord.Embed:
    """Creates an embed which informs members that the whole server has been locked down.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Der gesamte Server befindet sich aufgrund von Unruhen derzeit im Lockdown, weswegen das Versenden " \
                  "von Nachrichten vorübergehend nicht möglich ist. :mailbox_with_no_mail:\n\nDie Moderatoren sind " \
                  "bemüht, die Ordnung schnellstmöglich wiederherzustellen. Bitte haltet davon ab, sie bezüglich der " \
                  "aktuellen Situation zu kontaktieren, da dies die Wiedereröffnung des Kanals nur unnötig verzögern " \
                  "würde.\n\n**__Wir bitten um Verständnis.__ :heart:**"

    embed = discord.Embed(title=":rotating_light: LOCKDOWN :rotating_light:", color=const.EMBED_COLOR_WARNING,
                          description=description)

    return embed


def _build_lockdown_lift_embed() -> discord.Embed:
    """Creates an embed which informs members that the lockdown in a specific channel has been lifted.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Der Lockdown für diesen Kanal wurde aufgehoben und es können wieder ungehindert Nachrichten " \
                  "versendet werden. \n\n**__Vielen Dank für die Geduld.__** :handshake:"

    embed = discord.Embed(title=":sparkles: Lockdown-Aufhebung :sparkles:", color=const.EMBED_COLOR_INFO,
                          description=description)

    return embed


def _build_server_lockdown_lift_embed() -> discord.Embed:
    """Creates an embed which informs members that the server-wide lockdown has been lifted.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Der serverweite Lockdown wurde aufgehoben und es können wieder ungehindert Nachrichten " \
                  "versendet werden. \n\n**__Vielen Dank für die Geduld.__** :handshake:"

    embed = discord.Embed(title=":sparkles: Lockdown-Aufhebung :sparkles:", color=const.EMBED_COLOR_INFO,
                          description=description)

    return embed


def _build_warnings_embed(user: discord.Member, warnings: List[tuple]) -> discord.Embed:
    """Creates an embed listing all the warnings a specific user has received by the moderators.

    An entry consists of the warning id, a timestamp representing when it has been imposed and an optional reason.

    Args:
        user (discord.Member): The user which received the warnings.
        warnings (List[tuple]): A list of tuples containing id, timestamp and the reason of a warning.

    Returns:
        (discord.Embed): The embed listing the warnings of a user.
    """
    embed = discord.Embed(title=f"Verwarnungen von {user.display_name} :rotating_light:", timestamp=datetime.utcnow(),
                          description="__Gesamt:__ {0}".format(len(warnings)),
                          color=const.EMBED_COLOR_MODERATION)
    embed.set_footer(text="Stand")
    embed.set_thumbnail(url=user.avatar_url)

    time_difference = datetime.utcnow().astimezone().utcoffset()
    for warning in warnings:
        timestamp = datetime.strptime(warning[1], '%Y-%m-%d %H:%M:%S.%f')
        local_timestamp = timestamp + time_difference if time_difference else timestamp
        str_time = local_timestamp.strftime('%d.%m.%Y um %H:%M')
        reason = warning[2] if warning[2] else "Keine Angabe."

        embed.add_field(name=f"#{warning[0]} :small_orange_diamond: {str_time}", value=f"**Grund:** {reason}",
                        inline=False)
    return embed


def _build_mod_action_embed(action: str, description: str, reason: Optional[str],
                            ch_rules: discord.TextChannel) -> discord.Embed:
    """Creates an info embed for a specific mod action.

    The embed contains information about the action which has been performed, the moderator who did it and an optional
    reason why this has happened to the user.

    Args:
        action (str): The mod action which has been performed.
        description (str): A description explaining what happened.
        reason (Optional[str])

    Returns:
        (discord.Embed): The final info embed dialog
    """
    embed = discord.Embed(title=f"{action}-Info", description=description, color=const.EMBED_COLOR_WARNING)

    if reason:
        embed.add_field(name="Begründung des Moderators:", value=reason)

    if action != "Bann":
        embed.add_field(name="Hinweis :information_source:", inline=False,
                        value=f"Versuch bitte, dich in Zukunft besser an unsere {ch_rules.mention} zu halten, da "
                              f"wir ansonsten gezwungen sind, härtere Strafen zu verhängen. :scales:")

    return embed


def _build_purge_confirmation_embed(channel: discord.TextChannel, amount: int) -> discord.Embed:
    """Creates an embed for confirmation of the `purge` command.

    Args:
        channel (discord.TextChannel): The channel in which the messages should be deleted.
        amount (int): The amount of messages the user wants to remove.

    Returns:
        (discord.Embed): The embed with the confirmation dialog
    """
    description = "**Bist du dir sicher, dass du im Kanal {0} __{1} Nachrichten__ löschen möchtest?**\nDiese " \
                  "Operation kann nicht rückgängig gemacht werden! Überlege dir daher gut, ob du das auch wirklich " \
                  "tun möchtest.".format(channel.mention, amount)

    return discord.Embed(title=":warning: Purge-Bestätigung :warning:", description=description,
                         color=const.EMBED_COLOR_WARNING)


def _build_lockdown_confirmation_embed(channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]]) \
        -> discord.Embed:
    """Creates an embed for confirmation of the `lockdown` command.

    Args:
        channel (Optional[Union[discord.TextChannel, discord.VoiceChannel]]): The channel which should be locked down.

    Returns:
        (discord.Embed): The embed with the confirmation dialog
    """
    if channel:
        description = f"Bist du dir sicher, dass du den Kanal {channel.mention} in einen Lockdown versetzen möchtest? "\
                      f"Niemand außer den Moderatoren ist dann noch in der Lage, hier Nachrichten zu versenden."
    else:
        description = "Bist du dir sicher, dass du **__den gesamten Server__** in einen Lockdown versetzen möchtest? "\
                      "Niemand außer den Moderatoren ist dann noch in der Lage, Nachrichten zu versenden."

    return discord.Embed(title=":warning: Lockdown-Bestätigung :warning:", description=description,
                         color=const.EMBED_COLOR_WARNING)


def _create_report_embed(offender: discord.Member, reporter: discord.Member, channel: discord.TextChannel,
                         message: discord.Message, description: str) -> discord.Embed:
    """Method which creates an embed containing information about a possible incident on the server.

    Each embed consists of information about the person who reported a problem, the possible offender and a description
    about why the person has been reported.

    Args:
        offender (discord.Member): The user who has been reported.
        reporter (discord.Member): The person who submitted the report.
        channel (discord.TextChannel): The channel from where the report has been submitted.
        message (discord.Message): The message which invoked the command.
        description (str): The description why this person has been reported.

    Returns:
        discord.Embed: An embedded message containing information about a possible offender.
    """
    joined_at = offender.joined_at.strftime("%d.%m.%Y - %H:%M")
    created_at = offender.created_at.strftime("%d.%m.%Y - %H:%M")

    embed = discord.Embed(title="Nutzer-Infos", color=const.EMBED_COLOR_REPORT, timestamp=datetime.utcnow(),
                          description=f"**Name:** {offender}\n**Beitritt am:** {joined_at}\n"
                                      f"**Erstellt am:** {created_at}")
    embed.set_author(name=f"Neue Meldung aus [#{channel}]")
    embed.set_footer(text=f"Gemeldet von {reporter}", icon_url=reporter.avatar_url)
    embed.add_field(name="Beschreibung:", value=f"{description}\n[Gehe zum Channel]({message.jump_url})")
    embed.set_thumbnail(url=offender.avatar_url)

    return embed


def _modmail_create_ticket_list(messages: List[tuple]) -> str:
    """Method which creates a string representing a list of modmail tickets.

    Each entry of the list consists of a timestamp representing the moment this ticket has been submitted and a link to
    the corresponding embedded message in the modmail channel. The text of each hyperlink represents the user who
    submitted the ticket.

    Args:
        messages (List[tuple]): A list containing tuples consisting of a message id and the authors name.

    Returns:
        str: A listing of hyperlinks with the specified Discord messages as their targets.
    """
    string = ""

    time_difference = datetime.utcnow().astimezone().utcoffset()
    for message in messages:
        timestamp = datetime.strptime(message[2], '%Y-%m-%d %H:%M:%S.%f')
        local_timestamp = timestamp + time_difference if time_difference else timestamp
        str_time = local_timestamp.strftime('%d.%m.%Y %H:%M')

        string += "- {0} | [{1[1]}]({2}/channels/{3}/{4}/{1[0]})\n" \
            .format(str_time, message, const.URL_DISCORD, const.SERVER_ID, const.CHANNEL_ID_MODMAIL)

    return string


def _modmail_create_list_embed(status: ModmailStatus, modmail: List[tuple]) -> discord.Embed:
    """Method which creates an Embed containing a list of hyperlinks to all the modmail with the specified status.

    Args:
        status (ModmailStatus): The status specified by a moderator.
        modmail (List[tuple]): A list containing tuples consisting of a message id and the authors name.

    Returns:
        discord.Embed: The embed containing the list of hyperlinks with the authors name as the link text.
    """
    embed = discord.Embed(timestamp=datetime.utcnow())
    embed.set_footer(text="Erstellt am")
    dict_embed = embed.to_dict()

    if modmail is not None:
        dict_embed = embed.to_dict()
        dict_embed["description"] = _modmail_create_ticket_list(modmail)

        if status == ModmailStatus.OPEN:
            dict_embed["title"] = "Offenen Tickets: " + str(len(modmail))
            dict_embed["color"] = const.EMBED_COLOR_MODMAIL_OPEN
        elif status == ModmailStatus.ASSIGNED:
            dict_embed["title"] = "Zugewiesene Tickets: " + str(len(modmail))
            dict_embed["color"] = const.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            raise ValueError("Nicht unterstützter Modmail-Status '{0}'.".format(status.name.title()))
    elif status == ModmailStatus.OPEN:
        dict_embed["title"] = "Keine offenen Tickets! :tada:"
        dict_embed["color"] = const.EMBED_COLOR_MODMAIL_CLOSED
        dict_embed["description"] = "Lehne dich zurück und entspanne ein wenig. Momentan gibt es für dich keine " \
                                    "Tickets, welche du abarbeiten könntest. :beers:"
    elif status == ModmailStatus.ASSIGNED:
        dict_embed["title"] = "Keine Tickets in Bearbeitung! :eyes:"
        dict_embed["color"] = const.EMBED_COLOR_MODMAIL_ASSIGNED
        dict_embed["description"] = "**Es ist ruhig, zu ruhig...** Vielleicht gibt es momentan ja ein paar offene " \
                                    "Tickets die bearbeitet werden müssten."
    else:
        raise ValueError("Nicht unterstützter Modmail-Status '{0}'.".format(status.name.title()))

    return discord.Embed.from_dict(dict_embed)

def _trim_role_string(roles: str, num_total_roles: int):
    """Cuts the role string for the role field to the embed limit of 1024 and appends the text 'und x weitere' where x is the number of cut off roles.

     Args:
        roles (str): String of all roles the user has by ids (eg. '<@1234...> <@456...> ...' .
        num_total_roles (int): Number of roles the user has.

    Returns:
        str: The passed role string, trimmed down to less than 1024 characters.
    """
    roles_shortened = roles[:1009]
    num_printed_roles = roles_shortened.count(">")  # Count number of non-cut roles that are still in the string (they end with '>')
    remaining_roles = num_total_roles - num_printed_roles

    cut_index = roles_shortened.rfind(" ")
    roles_shortened = roles_shortened[:cut_index]
    roles = f"{roles_shortened} und {remaining_roles} weitere."
    return roles


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(ModerationCog(bot))
