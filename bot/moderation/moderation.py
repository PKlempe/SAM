"""Contains a Cog for all functionality regarding Moderation."""

from datetime import datetime
from typing import List, Optional, Union
import re
import operator

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from bot import constants
from bot.logger import command_log, log
from bot.moderation import ModmailStatus
from bot.persistence import DatabaseConnector
from bot.util.time_parsing import get_future_timestamp


class ModerationCog(commands.Cog):
    """Cog for Moderation Functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)
        self.scheduler = AsyncIOScheduler(job_defaults={'misfire_grace_time': 24*60*60},
                                          jobstores={'default': SQLAlchemyJobStore(
                                              url=f'sqlite:///{constants.DB_FILE_PATH}')})
        self.scheduler.start()

        # Static variable which is needed for running jobs created by the scheduler. A lot of data structures provided
        # by discord.py can't be pickled (serialized) which is why IDs are being used instead. For converting them into
        # usable objects, a bot/client object is needed, which should be the same for the whole application anyway.
        ModerationCog.bot = bot
        self.guild = self.bot.get_guild(int(constants.SERVER_ID))

        # Channel instances
        self.ch_report = self.guild.get_channel(int(constants.CHANNEL_ID_REPORT))
        self.ch_modmail = self.guild.get_channel(int(constants.CHANNEL_ID_MODMAIL))
        self.ch_rules = self.guild.get_channel(int(constants.CHANNEL_ID_RULES))
        self.ch_server_news = self.guild.get_channel(int(constants.CHANNEL_ID_NEWS))

        # Role instances
        self.role_moderator = self.guild.get_role(int(constants.ROLE_ID_MODERATOR))
        self.role_muted = self.guild.get_role(int(constants.ROLE_ID_MUTED))

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

            embed = _create_lockdown_embed()
            await channel.send(embed=embed)

    @lockdown.command(name='lift', hidden=True)
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

        embed = _build_lockdown_lift_embed()
        await channel.send(embed=embed)

    @lockdown.group(name='server', hidden=True, invoke_without_command=True)
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

            embed = _build_server_lockdown_embed()
            await self.ch_server_news.send(embed=embed)

    @lockdown_server.command(name='lift', hidden=True)
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

        embed = _build_server_lockdown_lift_embed()
        await self.ch_server_news.send(embed=embed)

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

        # TODO: Check warnings and take actions if necessary.

        await ctx.send(f"{user.mention} wurde verwarnt. :warning:")
        await user.send(content=f"Hey, {user.display_name}! :wave:\nDu wurdest von **__{ctx.author}__** verwarnt. "
                                f"Bitte halte dich in Zukunft an unsere {self.ch_rules.mention}, da wir ansonsten "
                                f"gezwungen sind, härtere Strafen zu verhängen. :scales:")

    @warn_user.command(name='remove', hidden=True)
    @command_log
    async def remove_warning(self, ctx: commands.Context, warning_id: int):
        """Command Handler for the subcommand `remove` of the command `warning`.

        Removes the warning with the specified id from a member.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            warning_id (int): The id of the warning which should be removed.
        """
        user_id = self._db_connector.get_warning_userid(warning_id)

        if not user_id:
            raise commands.BadArgument("The warning with the specified ID doesn't exist.")

        user = self.guild.get_member(int(user_id))
        self._db_connector.remove_member_warning(warning_id)

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

    @warn_user.command(name='clear', hidden=True)
    @command_log
    async def clear_warnings(self, ctx: commands.Context, *, user: discord.Member):
        """Command Handler for the subcommand `clear` of the command `warning`.

        Removes all warnings given to the specified member.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose warnings should be cleared.
        """
        self._db_connector.remove_member_warnings(user.id)
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
        """
        if self.role_muted in user.roles:
            await ctx.send("Dieser Nutzer ist bereits stummgeschalten. :flushed:")
            return

        await user.add_roles(self.role_muted, reason=reason)
        await ctx.send(f"{user.mention} wurde stummgeschalten. :mute:")

    @commands.command(name='unmute', hidden=True)
    @command_log
    async def unmute_user(self, ctx: commands.Context, user: discord.Member):
        """Command Handler for the `unmute` command.

        Unmutes the specified member on the server. This is done by removing the configured mute role from him.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be unmuted.
        """
        if self.role_muted not in user.roles:
            await ctx.send("Dieser Nutzer ist nicht stummgeschalten. :thinking:")
            return

        await user.remove_roles(self.role_muted)
        await ctx.send(f"{user.mention} ist nicht mehr stummgeschalten. :speaker:")
        await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr stummgeschalten! :speaker: Versuch "
                        f"bitte in Zukunft, dich mehr an unsere {self.ch_rules.mention} zu halten, da wir ansonsten "
                        f"gezwungen sind, härtere Strafen zu verhängen. :scales:")

    @commands.command(name='tempmute', hidden=True)
    @command_log
    async def tempmute_user(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: Optional[str]):
        """Command Handler for the `tempmute` command.

        Temporarily mutes the specified member server-wide for the duration given. This means the user won't be able to
        write messages, join voice channels or even add reactions. This is done by granting the configured mute role.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be muted.
            duration (str): The amount of time the user should be banned from the server.
            reason (Optional[str]): The reason provided by the moderator.
        """
        if self.role_muted in user.roles:
            await ctx.send("Dieser Nutzer ist bereits stummgeschalten. :flushed:")
            return

        run_date, pretty_duration = get_future_timestamp(duration)

        await user.add_roles(self.role_muted, reason=reason)
        await ctx.send(f"{user.mention} wurde für {pretty_duration} stummgeschalten. :mute:")

        self.scheduler.add_job(_scheduled_unmute_user, 'date', run_date=run_date,
                               args=[self.guild.id, self.ch_rules.id, self.role_muted.id, user.id])

    @commands.command(name='ban', hidden=True)
    @command_log
    async def ban_user(self, ctx: commands.Context, user: discord.Member, *, reason: Optional[str]):
        """Command Handler for the `ban` command.

        Bans the specified member from the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be banned.
            reason (Optional[str]): The reason provided by the moderator.
        """
        await user.ban(reason=reason, delete_message_days=0)
        await ctx.send(f"{user.mention} wurde gebannt. :do_not_litter:")

        embed = _build_mod_action_embed("Bann", f"Du wurdest von **__{self.guild}__** gebannt.", ctx.author, reason)
        await user.send(embed=embed)

    @commands.command(name='tempban', hidden=True)
    @command_log
    async def tempban_user(self, ctx: commands.Context, user: discord.Member, duration: str, *, reason: Optional[str]):
        """Command Handler for the `tempban` command.

        Temporarily bans the specified member from the server for the duration given.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member who should be banned.
            duration (str): The amount of time the user should be banned from the server.
            reason (Optional[str]): The reason provided by the moderator.
        """
        run_date, pretty_duration = get_future_timestamp(duration)

        await user.ban(reason=reason, delete_message_days=0)
        await ctx.send(f"{user.mention} wurde für {pretty_duration} gebannt. :do_not_litter:")

        embed = _build_mod_action_embed("Bann", f"Du wurdest von **__{self.guild}__** für {pretty_duration} gebannt.",
                                        ctx.author, reason)
        await user.send(embed=embed)

        self.scheduler.add_job(_scheduled_unban_user, 'date', run_date=run_date,
                               args=[self.guild.id, self.ch_rules.id, user.id])

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
        await user.kick(reason=reason)
        await ctx.send(f"{user.mention} wurde gekickt. :anger:")

        embed = _build_mod_action_embed("Kick", f"Du wurdest von **__{self.guild}__** gekickt.", ctx.author, reason)
        await user.send(embed=embed)

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
            .format(constants.LIMIT_NICKNAMES)

        if nicknames:
            embed = discord.Embed(title=f"Namensverlauf von {user} :page_with_curl:", description=description,
                                  color=constants.EMBED_COLOR_MODERATION, timestamp=datetime.utcnow())
            embed.set_footer(text="Stand")
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(name=user.display_name, value="aktuell")

            for name in nicknames[:constants.LIMIT_NICKNAMES]:
                timestamp = datetime.strptime(name[1], '%Y-%m-%d %H:%M:%S.%f').strftime("%d.%m.%Y\num *%H:%M:%S*")
                embed.add_field(name=name[0], value=f"bis {timestamp}")

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
        if amount > constants.LIMIT_NEW_MEMBERS:
            raise commands.BadArgument("The amount of new members to be displayed is too big.")

        members = sorted(ctx.guild.members, key=operator.attrgetter("joined_at"), reverse=True)[:amount]
        description = "Füge an das Ende des Befehls eine beliebige Zahl an, um die Menge an neuen Mitgliedern " \
                      "individuell festzulegen. **(max. {0})**".format(constants.LIMIT_NEW_MEMBERS)

        embed = discord.Embed(title="Neueste Mitglieder :couple:", color=constants.EMBED_COLOR_MODERATION,
                              description=description, timestamp=datetime.utcnow())
        embed.set_footer(text="Stand")

        for member in members:
            embed.add_field(name=str(member), value=datetime.strftime(member.joined_at, "%d.%m.%Y | *%H:%M:%S*"))

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
                           "leider zu groß. Sie darf **{0}** nicht überschreiten.".format(constants.LIMIT_NEW_MEMBERS))

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

        embed = discord.Embed(title=f"Avatar von {user}", color=constants.EMBED_COLOR_MODERATION,
                              timestamp=datetime.utcnow(),
                              description=description)
        embed.set_footer(text="Erstellt am")
        embed.set_image(url=user.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name='info', hidden=True)
    @command_log
    async def user_info(self, ctx: commands.Context, *, user: discord.Member):
        """Command Handler for the `info` command.

        Posts an embed containing various information about the member specified. This includes creation date, join date
        the currently used name on the server, server roles and the date since when he's boosting the server.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            user (discord.Member): The member whose information is being requested.
        """
        created_at = datetime.strftime(user.created_at, "%d.%m.%Y | %H:%M:%S")
        joined_at = datetime.strftime(user.joined_at, "%d.%m.%Y | %H:%M:%S")
        roles = " ".join([role.mention for role in reversed(user.roles[1:])])
        description = f"Name am Server: {user.mention}"

        if user.premium_since:
            premium_since = datetime.strftime(user.premium_since, "%d.%m.%Y %H:%M:%S")
            description += f"Boostet seit: {premium_since}"

        embed = discord.Embed(title=str(user), description=description,
                              color=constants.EMBED_COLOR_MODERATION)
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
        await ctx.message.delete()

        embed = _create_report_embed(offender, ctx.author, ctx.channel, ctx.message, description)
        await self.ch_report.send(embed=embed)

    @report_user.error
    async def report_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `report` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            regex = re.search(r"\"(.*)\"", error.args[0])  # Regex for getting text between two quotes.
            user = regex.group(1) if regex else None

            await ctx.author.send(f"Ich konnte leider keinen Nutzer namens **{user}** finden. :confused: Hast du dich "
                                  f"möglicherweise vertippt?")

    @commands.group(name='purge', hidden=True)
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

        if amount <= 0 or amount > constants.LIMIT_PURGE_MESSAGES:
            raise commands.BadArgument("Invalid amount of messages to be purged was passed. "
                                       "Maximum: {0}, Passed limit: {1}".format(constants.LIMIT_PURGE_MESSAGES, amount))

        confirmation_embed = _build_purge_confirmation_embed(purge_channel, amount)
        is_confirmed = await self._send_confirmation_dialog(ctx, confirmation_embed)

        if is_confirmed:
            deleted_messages = await purge_channel.purge(limit=amount + 1)
            await purge_channel.send('**Ich habe __{0} Nachrichten__ erfolgreich gelöscht.**'
                                     .format(len(deleted_messages)), delete_after=constants.TIMEOUT_INFORMATION)
            log.info("SAM deleted %s messages in [#%s]", len(deleted_messages), purge_channel)

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
                           .format(constants.LIMIT_PURGE_MESSAGES),
                           delete_after=constants.TIMEOUT_INFORMATION)

    @commands.group(name='modmail', invoke_without_command=True)
    @command_log
    async def modmail(self, ctx: commands.Context):
        """Command Handler for the `modmail` command.

        Allows users to write a message to all the moderators of the server. The message is going to be posted in a
        specified modmail channel which can (hopefully) only be accessed by said moderators. The user who invoked the
        command will get a confirmation via DM and the invocation will be deleted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        await ctx.message.delete()

        msg_content = ctx.message.content[len(ctx.prefix + ctx.command.name):]
        msg_attachments = ctx.message.attachments
        msg_author_name = str(ctx.message.author)
        msg_timestamp = ctx.message.created_at

        embed = discord.Embed(title="Status: Offen", color=constants.EMBED_COLOR_MODMAIL_OPEN,
                              timestamp=datetime.utcnow(), description=msg_content)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
        embed.set_footer(text="Erhalten am")

        msg_modmail = await self.ch_modmail.send(embed=embed, files=msg_attachments)
        self._db_connector.add_modmail(msg_modmail.id, msg_author_name, msg_timestamp)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_DONE)
        await msg_modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)

        embed_confirmation = embed.to_dict()
        embed_confirmation["title"] = "Deine Nachricht:"
        embed_confirmation["color"] = constants.EMBED_COLOR_INFO
        embed_confirmation = discord.Embed.from_dict(embed_confirmation)
        await ctx.author.send("Deine Nachricht wurde erfolgreich an die Moderatoren weitergeleitet!\n"
                              "__Hier deine Bestätigung:__", embed=embed_confirmation)

    @modmail.command(name='get', hidden=True)
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
        if not payload.member.bot and payload.channel_id == self.ch_modmail.id and \
                self.role_moderator in payload.member.roles:
            modmail = await self.ch_modmail.fetch_message(payload.message_id)

            if payload.emoji.name in (constants.EMOJI_MODMAIL_DONE, constants.EMOJI_MODMAIL_ASSIGN):
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, True)
                await modmail.edit(embed=new_embed)

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

            if payload.emoji.name == constants.EMOJI_MODMAIL_DONE or \
                    payload.emoji.name == constants.EMOJI_MODMAIL_ASSIGN:
                new_embed = await self.change_modmail_status(modmail, payload.emoji.name, False)
                await modmail.edit(embed=new_embed)

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
        curr_status = self._db_connector.get_modmail_status(modmail.id)
        dict_embed = modmail.embeds[0].to_dict()
        dict_embed["title"] = "Status: "

        if reaction_added and emoji == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.CLOSED:
            await modmail.clear_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.CLOSED)

            dict_embed["title"] += "Erledigt"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
        elif reaction_added and emoji == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.ASSIGNED:
            self._db_connector.change_modmail_status(modmail.id, ModmailStatus.ASSIGNED)

            dict_embed["title"] += "In Bearbeitung"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            dict_embed["title"] += "Offen"
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN

            if emoji == constants.EMOJI_MODMAIL_DONE and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)
                await modmail.add_reaction(constants.EMOJI_MODMAIL_ASSIGN)
            elif emoji == constants.EMOJI_MODMAIL_ASSIGN and curr_status != ModmailStatus.OPEN:
                self._db_connector.change_modmail_status(modmail.id, ModmailStatus.OPEN)

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
        message = await ctx.send(embed=embed, delete_after=constants.TIMEOUT_USER_SELECTION)
        await message.add_reaction(constants.EMOJI_CONFIRM)
        await message.add_reaction(constants.EMOJI_CANCEL)

        def check_reaction(_reaction, user):
            return user == ctx.author and _reaction.message.id == message.id and \
                   str(_reaction.emoji) in [constants.EMOJI_CANCEL, constants.EMOJI_CONFIRM]

        reaction = await self.bot.wait_for('reaction_add', timeout=constants.TIMEOUT_USER_SELECTION,
                                           check=check_reaction)
        await message.delete()

        if str(reaction[0].emoji) == constants.EMOJI_CANCEL:
            await ctx.message.delete()

        return str(reaction[0].emoji) == constants.EMOJI_CONFIRM

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


async def _scheduled_unmute_user(server_id: int, ch_rules_id: int, role_id: int, user_id: int):
    """Method which is being called by the scheduler if the specified amount of time for the corresponding tempmute has
    ran out.

    Unmutes a user with the specified ID on a specific server.

    Args:
        server_id (int): The id of the server where the user should be unbanned from.
        ch_rules_id (int): The id of the rules channel.
        role_id (int): The id of the mute role which should be removed from the user.
        user_id (int): The id of the user who should be unmuted.
    """
    guild = ModerationCog.bot.get_guild(int(server_id))
    ch_rules = guild.get_channel(int(ch_rules_id))
    user = guild.get_member(int(user_id))
    role = guild.get_role(int(role_id))

    await user.remove_roles(role, reason="Die für den Tempmute festgelegte Zeitdauer ist ausgelaufen.")
    await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr stummgeschalten! :speaker: Versuch "
                    f"bitte in Zukunft, dich mehr an unsere {ch_rules.mention} zu halten, da wir ansonsten "
                    f"gezwungen sind, härtere Strafen zu verhängen. :scales:")


async def _scheduled_unban_user(server_id: int, ch_rules_id: int, user_id: int):
    """Method which is being called by the scheduler if the specified amount of time for the corresponding tempban has
    ran out.

    Unbans a user with the specified ID on a specific server.

    Args:
        server_id (int): The id of the server where the user should be unbanned from.
        ch_rules_id (int): The id of the rules channel.
        user_id (int): The id of the user who should be unbanned.
    """
    guild = ModerationCog.bot.get_guild(int(server_id))
    ch_rules = guild.get_channel(int(ch_rules_id))
    user = await ModerationCog.bot.fetch_user(int(user_id))

    await user.unban(reason="Die für den Tempban festgelegte Zeitdauer ist ausgelaufen.")
    await user.send(f"Hey, {user.display_name}! :wave:\nDu bist nicht mehr von **__{guild}__** gebannt! :unlock: "
                    f"Versuch bitte in Zukunft, dich mehr an unsere {ch_rules.mention} zu halten, da wir ansonsten "
                    f"gezwungen sind, dich dauerhaft zu bannen. :scales:")


def _create_lockdown_embed() -> discord.Embed:
    """Creates an embed which informs members that the current channel has been locked down.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Dieser Kanal befindet sich aufgrund von Unruhen derzeit im Lockdown, weswegen das Versenden " \
                  "von Nachrichten vorübergehend nicht möglich ist. :mailbox_with_no_mail:\n\nDie Moderatoren sind " \
                  "bemüht, die Ordnung schnellstmöglich wiederherzustellen. Bitte haltet davon ab, sie bezüglich der " \
                  "aktuellen Situation zu kontaktieren, da dies die Wiedereröffnung des Kanals nur unnötig verzögern " \
                  "würde.\n\n**__Wir bitten um Verständnis.__ :heart:**"

    embed = discord.Embed(title=":rotating_light: LOCKDOWN :rotating_light:", color=constants.EMBED_COLOR_WARNING,
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

    embed = discord.Embed(title=":rotating_light: LOCKDOWN :rotating_light:", color=constants.EMBED_COLOR_WARNING,
                          description=description)

    return embed


def _build_lockdown_lift_embed() -> discord.Embed:
    """Creates an embed which informs members that the lockdown in a specific channel has been lifted.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Der Lockdown für diesen Kanal wurde aufgehoben und es können wieder ungehindert Nachrichten " \
                  "versendet werden. \n\n**__Vielen Dank für die Geduld.__** :handshake:"

    embed = discord.Embed(title=":sparkles: Lockdown-Aufhebung :sparkles:", color=constants.EMBED_COLOR_INFO,
                          description=description)

    return embed


def _build_server_lockdown_lift_embed() -> discord.Embed:
    """Creates an embed which informs members that the server-wide lockdown has been lifted.

    Returns:
        (discord.Embed): The info embed.
    """
    description = "Der serverweite Lockdown wurde aufgehoben und es können wieder ungehindert Nachrichten " \
                  "versendet werden. \n\n**__Vielen Dank für die Geduld.__** :handshake:"

    embed = discord.Embed(title=":sparkles: Lockdown-Aufhebung :sparkles:", color=constants.EMBED_COLOR_INFO,
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
                          color=constants.EMBED_COLOR_MODERATION)
    embed.set_footer(text="Stand")
    embed.set_thumbnail(url=user.avatar_url)

    for warning in warnings:
        timestamp = datetime.strptime(warning[1], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y um %H:%M')
        reason = warning[2] if warning[2] else "Keine Angabe."

        embed.add_field(name=f"#{warning[0]} :small_orange_diamond: {timestamp}", value=f"**Grund:** {reason}",
                        inline=False)
    return embed


def _build_mod_action_embed(action: str, description: str, moderator: discord.Member, reason: Optional[str]) \
        -> discord.Embed:
    """Creates an info embed for a specific mod action.

    The embed contains information about the action which has been performed, the moderator who did it and an optional
    reason why this has happened to the user.

    Args:
        action (str): The mod action which has been performed.
        description (str): A description explaining what happened.
        moderator (discord.Member): The Moderator who triggered the action.
        reason (Optional[str])

    Returns:
        (discord.Embed): The final info embed dialog
    """
    embed = discord.Embed(title=f"{action}-Meldung", description=description, color=constants.EMBED_COLOR_WARNING)

    if reason:
        embed.add_field(name=f"Begründung von {moderator.display_name}", value=reason)

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
                         color=constants.EMBED_COLOR_WARNING)


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
                         color=constants.EMBED_COLOR_WARNING)


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

    embed = discord.Embed(title="Nutzer-Infos", color=constants.EMBED_COLOR_REPORT, timestamp=datetime.utcnow(),
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

    for message in messages:
        timestamp = datetime.strptime(message[2], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')

        string += "- {0} | [{1[1]}]({2}/channels/{3}/{4}/{1[0]})\n" \
            .format(timestamp, message, constants.URL_DISCORD, constants.SERVER_ID, constants.CHANNEL_ID_MODMAIL)

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
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_OPEN
        elif status == ModmailStatus.ASSIGNED:
            dict_embed["title"] = "Zugewiesene Tickets: " + str(len(modmail))
            dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        else:
            raise ValueError("Nicht unterstützter Modmail-Status '{0}'.".format(status.name.title()))
    elif status == ModmailStatus.OPEN:
        dict_embed["title"] = "Keine offenen Tickets! :tada:"
        dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_CLOSED
        dict_embed["description"] = "Lehne dich zurück und entspanne ein wenig. Momentan gibt es für dich keine " \
                                    "Tickets, welche du abarbeiten könntest. :beers:"
    elif status == ModmailStatus.ASSIGNED:
        dict_embed["title"] = "Keine Tickets in Bearbeitung! :eyes:"
        dict_embed["color"] = constants.EMBED_COLOR_MODMAIL_ASSIGNED
        dict_embed["description"] = "**Es ist ruhig, zu ruhig...** Vielleicht gibt es momentan ja ein paar offene " \
                                    "Tickets die bearbeitet werden müssten."
    else:
        raise ValueError("Nicht unterstützter Modmail-Status '{0}'.".format(status.name.title()))

    return discord.Embed.from_dict(dict_embed)


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(ModerationCog(bot))
