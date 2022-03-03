"""Contains a Cog for all functionality regarding our University."""
import itertools
import operator
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from sqlite3 import IntegrityError
from typing import Dict, List, Optional, Union, Iterable, Tuple

import discord
from discord.ext import commands

from bot import constants, singletons
from bot.logger import command_log, log
from bot.persistence import DatabaseConnector
from bot.utility import SelectionEmoji


class UniversityCog(commands.Cog):
    """Cog for Functions regarding the IT faculty or the University of Vienna as a whole."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

        # Static variable which is needed for running jobs created by the scheduler. A lot of data structures provided
        # by discord.py can't be pickled (serialized) which is why IDs are being used instead. For converting them into
        # usable objects, a bot/client object is needed, which should be the same for the whole application anyway.
        UniversityCog.bot = bot

        # Channel instances
        self.ch_group_exchange = bot.get_guild(int(constants.SERVER_ID))\
            .get_channel(int(constants.CHANNEL_ID_GROUP_EXCHANGE))

        # Adds jobs needed for reopening/closing the group exchange channel if they don't already exist.
        _initialize_scheduler_jobs()

    @commands.group(name="ufind", invoke_without_command=True)
    @command_log
    async def ufind(self, ctx: commands.Context):
        """Command Handler for the `ufind` command.

        Allows users to search the service `ufind` for various information regarding staff members, courses and exams
        and posts them on Discord. For each of these categories exists a corresponding subcommand. If no subcommand has
        been invoked, a help message for this command will be posted instead.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        await ctx.send_help(ctx.command)

    @ufind.command(name="staff")
    @command_log
    async def ufind_get_staff_data(self, ctx: commands.Context, *, search_term: str):
        """Command Handler for the `ufind` subcommand `staff`.

        Allows users to search the service `ufind` for information regarding staff members and posts them on Discord.
        If the search result contains more than one person, an embed with reactions will be posted. The user can then
        choose a person by reacting to said embed. If the result contains no person at all, the bot will inform the
        user by posting a sad message.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            search_term (str): The term to be searched for (most likely firstname, lastname or both).
        """
        async with ctx.channel.typing():
            search_filters = "%20%2Be%20c%3A6"  # URL Encoding
            query_url = constants.URL_UFIND_API + "/staff/?query=" + search_term + search_filters

            async with singletons.HTTP_SESSION.get(query_url) as response:
                response.raise_for_status()
                data_staff_multiple = await response.text(encoding='utf-8')
                xml_staff_multiple = ET.fromstring(data_staff_multiple)

            persons = xml_staff_multiple.findall("person")
            if not persons:
                raise ValueError("No person with the specified name was found.")

        index = await self._staff_selection(ctx.author, ctx.channel, persons) if len(persons) > 1 else 0
        staff_url = constants.URL_UFIND_API + "/staff/" + persons[index].attrib["id"]

        async with ctx.channel.typing():
            async with singletons.HTTP_SESSION.get(staff_url) as response2:
                response2.raise_for_status()
                data_staff_single = await response2.text(encoding='utf-8')

                dict_staff = _parse_staff_xml(data_staff_single)

            embed = _create_embed_staff(dict_staff)
            await ctx.channel.send(embed=embed)

    @ufind_get_staff_data.error
    async def ufind_error(self, ctx, error: commands.CommandError):
        """Error Handler for the `ufind` subcommand `staff`.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, ValueError):
            await ctx.send("Ich konnte leider niemanden unter dem von dir angegeben Namen finden. :slight_frown:\n"
                           "Hast du dich möglicherweise vertippt?")

    async def _staff_selection(self, author: discord.User, channel: discord.TextChannel, persons: List[ET.Element]) \
            -> int:
        """Method for handling multiple results when searching for a staff member on `ufind`.

        If multiple results have been returned by `ufind`, this method will post an embed containing the names of these.
        The user can then choose one person by reacting to the embed. If the user takes too long and the timeout is
        reached, the embed will be removed and the bot will post a message to inform the user about what happened.

        Args:
            author (discord.User): The user who invoked the command.
            channel (discord.TextChannel): The channel in which the command has been invoked.
            persons (List[ET.Element]): A list containing the person elements from the XML string returned by `ufind`.

        Returns:
            int: The index of the selected person.
        """
        list_selection_emojis = SelectionEmoji.to_list()

        embed = _create_embed_staff_selection(persons)
        message = await channel.send(embed=embed, delete_after=constants.TIMEOUT_USER_SELECTION)

        for i in range(len(embed.fields)):
            await message.add_reaction(list_selection_emojis[i])

        def check_reaction(_reaction, user):
            return _reaction.message.id == message.id and user == author and SelectionEmoji(_reaction.emoji) is not None

        reaction = await self.bot.wait_for('reaction_add', timeout=constants.TIMEOUT_USER_SELECTION,
                                           check=check_reaction)
        await message.delete()

        return list_selection_emojis.index(reaction[0].emoji)

    @commands.group(name='exchange', hidden=True, invoke_without_command=True)
    @command_log
    async def exchange(self, ctx: commands.Context, channel: discord.TextChannel, offered_group: int,
                       *, requested_groups_str: str):
        """Command Handler for the exchange command

       Creates a new request for group exchange. Posts an embed in the configured group exchange channel, adds the
       according entries in the DB and notifies the poster and all possible exchange partners via direct message.

        Args:
            ctx (Context): The context in which the command was called.
            channel (discord:TextChannel): The channel corresponding to the course for group change.
            offered_group (int): The group that the user offers.
            requested_groups_str (List[int]): A list of all groups the user would be willing to take.
        """
        if constants.EMOJI_CHANNEL_NAME_SEPARATOR not in channel.name:
            raise SyntaxError("Invalid course channel.")

        try:
            requested_groups = list(map(int, requested_groups_str.split(',')))
        except ValueError:
            raise SyntaxError("Invalid symbol in list of requested groups: " + requested_groups_str)

        if offered_group in requested_groups:
            raise ValueError("The offered Group was part of the requested groups. Offered Group {0}, "
                             "Requested Groups: {1}".format(offered_group, requested_groups))

        self._db_connector.add_group_offer_and_requests(ctx.author.id, channel.id, offered_group, requested_groups)
        embed = _build_group_exchange_offer_embed(ctx.author, channel, offered_group, requested_groups)
        message = await self.ch_group_exchange.send(embed=embed)
        self._db_connector.update_group_exchange_message_id(ctx.author.id, channel.id, message.id)

        if ctx.channel != self.ch_group_exchange:
            await ctx.send(":white_check_mark: Dein Tauschangebot wurde erfolgreich erstellt!")

        potential_candidates = self._db_connector.get_candidates_for_group_exchange(ctx.author.id, channel.id,
                                                                                    offered_group, requested_groups)
        if potential_candidates:
            await self._notify_author_about_candidates(ctx.author, potential_candidates, self.ch_group_exchange,
                                                       channel)
            notification_embed = _build_candidate_notification_embed(ctx.author, message, channel, offered_group,
                                                                     constants.BOT_PREFIX)
            await self._notify_candidates_about_new_offer(potential_candidates, notification_embed)

    @exchange.command(name="remove")
    @command_log
    async def remove_exchange(self, ctx: commands.Context, channel: discord.TextChannel):
        """Removes a group exchange request.

        Deletes the message in the exchange channel as well as all corresponding entries in the db.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            channel (discord.TextChannel): The channel corresponding to the course.
        """
        message_id = self._db_connector.get_group_exchange_message(ctx.author.id, channel.id)

        if message_id:
            self._db_connector.remove_group_exchange_offer(ctx.author.id, channel.id)
            msg = await self.ch_group_exchange.fetch_message(message_id)

            await msg.delete()
            await ctx.author.send(":white_check_mark: Dein Tauschangebot wurde erfolgreich gelöscht.")

        else:
            await ctx.author.send("Du besitzt derzeit kein aktives Tauschangebot für diesen Kurs. :face_with_monocle:")

    @exchange.error
    @remove_exchange.error
    async def exchange_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the exchange command.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, ValueError):
            await ctx.author.send(
                "**__Error:__** Die angebotene Gruppe kann nicht Teil der gewünschten Gruppen sein.")
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, IntegrityError):
            await ctx.author.send(
                "**__Error:__** Du hast für diesen Kurs bereits ein aktives Tauschangebot.\nDu musst das alte Angebot "
                "zuerst mit `{0}exchange remove <channel-mention>` löschen, bevor du ein neues einreichen kannst."
                .format(constants.BOT_PREFIX))
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, SyntaxError):
            await ctx.author.send(
                "**__Error:__** Der von dir eingegebene Befehl, zur Erstellung eines Tauschangebots, ist inkorrekt.\n"
                "Bitte achte darauf, einen gültigen LV-Kanal anzugeben und die Nummern der gewünschten Gruppen "
                "mittels Beistrich zu trennen. Für weitere Infos, siehe angepinnte Nachrichten in {0}. :pushpin:"
                .format(self.ch_group_exchange.mention))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.author.send("**__Error:__** Der von dir eingegebene Befehl ist unvollständig bzw. inkorrekt.\n"
                                  "Bitte lies dir die im Kanal {0} angepinnte Nachricht nochmals durch und versuche es "
                                  "dann erneut. :pushpin:".format(self.ch_group_exchange.mention))
        elif isinstance(error, commands.BadArgument):
            await ctx.author.send("**__Error:__** Der von dir angegebene LV-Kanal existiert nicht.\nVersuche ihn "
                                  "mittels einer Markierung (Bsp: #pr1...) anzugeben, um Probleme zu vermeiden. Für "
                                  "weitere Infos, siehe angepinnte Nachrichten in {0}. :pushpin:"
                                  .format(self.ch_group_exchange.mention))

    @exchange.command(name="list")
    @command_log
    async def list_exchanges(self, ctx: commands.Context):
        """Lists all active group exchange requests by a user.

        Sends the active requests in an embed via direct message to a user.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
        """
        exchange_requests = self._db_connector.get_group_exchange_for_user(ctx.author.id)
        if exchange_requests:
            embed = await self._build_group_exchange_list_embed(exchange_requests)
            await ctx.author.send(embed=embed)
        else:
            await ctx.author.send("Du hast zurzeit keine aktiven Tauschangebote. :hushed:")

    async def _notify_author_about_candidates(self, author: discord.User,
                                              potential_candidates: List[Tuple[str, str, int]],
                                              channel: discord.TextChannel, course_channel: discord.TextChannel):
        """Notifies the Author of a group exchange request about possible exchange candidates.

        The author is informed via a direct message which contains infos about all possible users he or she could
        exchange groups with.

        Args:
            author (discord.User): The author to be notified.
            potential_candidates (List[Tuple[str, str]]): The possible candidate ids and the message ids of their
            exchange messages.
            channel (discord.TextChannel): The channel in which the the message of potential candidates can be found
            course_channel (discord.TextChannel): The channel that refers to the course that the exchange is for.
        """
        course_name = _parse_course_from_channel_name(course_channel)
        embed = discord.Embed(title="Mögliche Tauschpartner - {0}".format(course_name),
                              description="Bitte vergiss nicht, deine Anfrage mit dem Befehl `{0}exchange remove "
                                          "<channel-mention>` wieder zu löschen, sobald du einen Tauschpartner "
                                          "gefunden hast.".format(constants.BOT_PREFIX),
                              color=constants.EMBED_COLOR_GROUP_EXCHANGE)

        async def group_by_group_nr(cand):
            """Async Generator function to group a tuple (user_id, message_id, group_nr) by group_nr.

            Args:
                cand (List[Tuple[str, str, int]]): The tuple list to group.

            Examples:
                 Example Result: [(1, [(user1, msg1), (user2, msg2)], (2, [(user3, msg3), (...),...]),...]
            """
            guild = self.bot.get_guild(int(constants.SERVER_ID))
            iterable_cand = itertools.groupby(cand, operator.itemgetter(2))

            for key, subiter in iterable_cand:
                group_text = "Gruppe {0}".format(key)
                user_list = []

                for item in subiter:
                    user = guild.get_member(int(item[0]))
                    msg = await channel.fetch_message(int(item[1]))
                    user_list.append("- [{0}]({1})".format(user, msg.jump_url))

                yield group_text, "\n".join(user_list)

        users_by_group = group_by_group_nr(potential_candidates)
        async for group in users_by_group:
            embed.add_field(name=group[0], value=group[1])
        await author.send(content="Ich habe potentielle Tauschpartner für dich gefunden:", embed=embed)

    async def _notify_candidates_about_new_offer(self, potential_candidates: List[tuple], embed: discord.Embed):
        """Notifies all potential candidates that a new relevant group exchange offer has been posted.

        The candidates are informed via a direct message which contains information about the members and their offers
        he/she could exchange groups with.

        Args:
            potential_candidates (List[tuple]): The user ids of the potential candidates and the message ids of the
                                                corresponding exchange messages.
            embed (discord.Embed): The embed which should be send to the potential candidates.
        """
        guild = self.bot.get_guild(int(constants.SERVER_ID))

        for candidate in potential_candidates:
            member = guild.get_member(int(candidate[0]))
            await member.send(content="Ich habe ein neues Tauschangebot für dich gefunden:", embed=embed)

    async def _build_group_exchange_list_embed(self, exchange_requests: List[tuple]):
        """Builds an embed that contains infos about all group exchange requests a user has currently open.

        Args:
            exchange_requests (List[tuple]): A list containing tuples consisting of channel_id, message_id,
            offered_group and requested groups joined with commas.

        Returns:
            (discord.Embed): The created embed.
        """
        embed = discord.Embed(title="Deine Gruppentausch-Anfragen:", color=constants.EMBED_COLOR_GROUP_EXCHANGE)
        for request in exchange_requests:
            course_channel = self.bot.get_guild(int(constants.SERVER_ID)).get_channel(int(request[0]))
            msg = await self.ch_group_exchange.fetch_message(int(request[1]))
            course = _parse_course_from_channel_name(course_channel)
            offered_group = request[2]
            requested_groups = request[3]
            embed.add_field(name=course, inline=False,
                            value="__Biete:__ Gruppe {0}\n__Suche:__ Gruppen {1}\n[[Zur Nachricht]]({2})"
                            .format(offered_group, requested_groups, msg.jump_url))
        return embed


async def _scheduled_group_exchange_opening():
    """Method which is being called by the scheduler and opens the group exchange channel.

    Makes the channel visible to all members by adding adding the read_messages permission to @everyone. It also
    posts an info message on how to use this service.
    """
    guild = UniversityCog.bot.get_guild(int(constants.SERVER_ID))
    ch_group_exchange = guild.get_channel(int(constants.CHANNEL_ID_GROUP_EXCHANGE))

    overwrite = ch_group_exchange.overwrites_for(guild.default_role)
    overwrite.update(read_messages=True)
    await ch_group_exchange.set_permissions(guild.default_role, overwrite=overwrite)

    embed = _build_group_exchange_info_embed()
    message = await ch_group_exchange.send(embed=embed)
    await message.pin(reason="Tauschbörse: Info-Nachricht")

    log.info("Group Exchange channel has been opened.")


async def _scheduled_group_exchange_closing_and_purge():
    """Method which is being called by the scheduler and closes the group exchange channel.

    Makes the channel invisible by removing the read_messages permission from @everyone and purging all messages in
    the channel.
    """
    guild = UniversityCog.bot.get_guild(int(constants.SERVER_ID))
    ch_group_exchange = guild.get_channel(int(constants.CHANNEL_ID_GROUP_EXCHANGE))

    overwrite = ch_group_exchange.overwrites_for(guild.default_role)
    overwrite.update(read_messages=False)
    await ch_group_exchange.set_permissions(guild.default_role, overwrite=overwrite)

    # Limit is set to a high number because we can't simply remove "all" messages.
    await ch_group_exchange.purge(limit=100000)

    log.info("Group Exchange channel has been closed.")


async def _remove_ersti_role():
    """Method which is being called by the scheduler and removes the 'ersti' role from older members."""
    role = UniversityCog.bot.get_guild(int(constants.SERVER_ID)).get_role(int(constants.ROLE_ID_ERSTI))
    date_now = datetime.now()
    date_threshold = datetime(date_now.year, date_now.month - 2, 1)

    for member in role.members:
        if member.joined_at < date_threshold:
            await member.remove_roles(role, reason="Member isn't an Ersti anymore.")

    log.info("Ersti Role members have been purged.")


def _initialize_scheduler_jobs():
    """Method which creates scheduler jobs for various tasks on the server.

    Convenience method which adds jobs to the applications scheduler if they don't alreday exist. The job is scheduled
    yearly as stated by the passed dictionary, which must contain the keys 'job_id', 'month', 'day', 'hour' and 'minute'.
    """

    # Group Exchange
    openings = [constants.JOB_OPEN_GROUP_EXCHANGE_WINTER_SEMESTER,
                constants.JOB_OPEN_GROUP_EXCHANGE_SUMMER_SEMESTER]
    closings = [constants.JOB_CLOSE_GROUP_EXCHANGE_WINTER_SEMESTER,
                constants.JOB_CLOSE_GROUP_EXCHANGE_SUMMER_SEMESTER]

    for opening in openings:
        singletons.SCHEDULER.add_job(_scheduled_group_exchange_opening, replace_existing=True, id=opening["job_id"],
                                     trigger="cron", day=opening["day"], month=opening["month"],
                                     hour=opening["hour"], minute=opening["minute"])

    for closing in closings:
        singletons.SCHEDULER.add_job(_scheduled_group_exchange_closing_and_purge, replace_existing=True,
                                     id=closing["job_id"], trigger="cron", day=closing["day"], month=closing["month"],
                                     hour=closing["hour"], minute=closing["minute"])

    # Ersti Role
    start_ws = constants.JOB_START_WINTER_SEMESTER
    start_ss = constants.JOB_START_SUMMER_SEMESTER

    singletons.SCHEDULER.add_job(_remove_ersti_role, replace_existing=True, id=start_ws["job_id"], trigger="cron",
                                 day=start_ws["day"], month=start_ws["month"], hour=start_ws["hour"],
                                 minute=start_ws["minute"])

    singletons.SCHEDULER.add_job(_remove_ersti_role, replace_existing=True, id=start_ss["job_id"], trigger="cron",
                                 day=start_ss["day"], month=start_ss["month"], hour=start_ss["hour"],
                                 minute=start_ss["minute"])


def _build_candidate_notification_embed(author: discord.User, message: discord.Message,
                                        course_channel: discord.TextChannel, offered_group: int, command_prefix: str):
    """Builds an embed with information about new group exchange offers.

    Args:
        author (discord.User): The author of the new offer.
        message (discord.Message): The message containing the new offer.
        course_channel (discord.TextChannel): The channel referring to the course of the offer.
        offered_group (int): The group that is offered.

    Returns:
        (discord.Embed): An embed containing all information above for the user.
    """
    course_name = _parse_course_from_channel_name(course_channel)
    return discord.Embed(title="Neuer potentieller Tauschpartner",
                         description="Bitte vergiss nicht, deine Anfrage mit dem Befehl `{0}exchange remove "
                                     "<channel-mention>` wieder zu löschen, sobald du einen Tauschpartner gefunden "
                                     "hast.".format(command_prefix),
                         color=constants.EMBED_COLOR_GROUP_EXCHANGE) \
        .set_thumbnail(url=author.avatar_url) \
        .add_field(name="Kurs:", value=course_name) \
        .add_field(name="User:", value=author) \
        .add_field(name="Bietet:", value="Gruppe {0}".format(offered_group)) \
        .add_field(name=constants.ZERO_WIDTH_SPACE,
                   value="[[Zur Nachricht]]({0})".format(message.jump_url),
                   inline=False)


def _build_group_exchange_offer_embed(author: discord.User, channel: discord.TextChannel, offered_group: int,
                                      requested_groups: Iterable[int]) -> discord.Embed:
    """Builds an embed for a group exchange offer.

    The embed contains information about who wants to exchange groups, which groups he offers and requests and for what
    courses.

    Args:
        author (discord.User): The author of the embed (aka the user who wants to change groups).
        channel (discord.TextChannel): The channel that refers to the course that should be changed.
        offered_group (int): The group that the user offers.
        requested_groups (List[int]): The groups that the user would accept.

    Returns:
        (discord.Embed): The embed representing the group exchange offer.
    """
    embed = discord.Embed(title=_parse_course_from_channel_name(channel), color=constants.EMBED_COLOR_GROUP_EXCHANGE) \
        .set_thumbnail(url=author.avatar_url) \
        .add_field(name="Biete:", value="Gruppe {0}".format(offered_group)) \
        .add_field(name="Suche:", value="Gruppe {0}".format(", ".join(map(str, requested_groups)))) \
        .add_field(name="Eingereicht von:", value="{0}\n{0.mention}".format(author), inline=False)

    return embed


def _build_group_exchange_info_embed() -> discord.Embed:
    """Builds an embed for the group exchange channel containing instructions on how to use the service.

    Returns:
        (discord.Embed): The embed representing the group exchange offer.
    """
    description = "Um ein Tauschangebot einzureichen, verwende den Befehl:\n" \
                  "```!exchange <channel-mention> <Biete> <Suche>```\n" \
                  "__SAM__ wird es daraufhin in diesem Kanal posten und dich regelmäßig über passende Angebote " \
                  "anderer informieren. Um das Tauschangebot für die richtige LV einzureichen, achte bitte immer " \
                  "darauf, den entsprechenden Kanal zu markieren.\n\n" \
                  "**Beispiel:** Tausche MOD-Gruppe 4 gegen 1,2 oder 3.\n`!exchange #mod🔹modellierung 4 1,2,3`\n" \
                  "Man beachte, dass beim letzten Parameter die Ziffern durch einen Beistrich getrennt sind.\n\n" \
                  "Um dein Angebot und somit auch deine jeweiligen Anfragen für einen Kurs zu löschen, nutze den " \
                  "Befehl:\n" \
                  "```!exchange remove <channel-mention>```\n" \
                  "Bitte verwende diesen auch, sobald du einen Tauschpartner gefunden hast, um zukünftig keine " \
                  "Benachrichtigungen oder Anfragen anderer Nutzer mehr zu erhalten."

    field_1 = "Wenn du einen Tauschpartner gefunden hast, __sende ihm eine private Nachricht__. Diskussionen hier zu " \
              "verhindern, hilft dabei den Kanal übersichtlich zu halten."

    field_2 = "Um eine Liste deiner aktiven Tauschangebote als private Nachricht zu erhalten, verwende den Befehl:\n" \
              "```!exchange list```"

    embed = discord.Embed(title="Wie wirds gemacht?", color=constants.EMBED_COLOR_INFO, description=description) \
        .add_field(name="Private Nachrichten", value=field_1, inline=False) \
        .add_field(name="Angebote anzeigen", value=field_2, inline=False) \
        .set_image(url="https://i.imgur.com/6oCcq9y.png")

    return embed


def _parse_course_from_channel_name(channel: discord.TextChannel):
    """Parses the course name from a discord text channel.

    The channel name must contain at least one channel name separator emoji (as specified in constants.py) and it will
    reformat the name to replace all dashes with spaces and capitalize every word.

    Args:
        channel (discord.TextChannel): The channel to parse.

    Returns:
        (str): The course name corresponding to the channel name.
    """
    course_name_words = channel.name.split(constants.EMOJI_CHANNEL_NAME_SEPARATOR)[1] \
        .replace('-', ' ') \
        .split(' ')
    return ' '.join(map(str.capitalize, course_name_words))


def _create_embed_staff_selection(persons: List[ET.Element]) -> discord.Embed:
    """Method which creates the embed for selecting a staff member.

    Args:
        persons (List[ET.Element]): A list containing the individual person elements from the XML string received by
        `ufind`.

    Returns:
        discord.Embed: Embedded message which lists all of the staff members returned by `ufind`.
    """
    list_selection_emojis = SelectionEmoji.to_list()
    description = "Sollte die gesuchte Person hier nicht aufgelistet sein, dann versuche bitte deine Suchanfrage zu " \
                  "spezifizieren.\n" + constants.ZERO_WIDTH_SPACE

    embed = discord.Embed(color=constants.EMBED_COLOR_SELECTION, title="Wähle einen Mitarbeiter aus:",
                          description=description)

    for index, person in enumerate(persons):
        name = "{0} {1} {2}".format(list_selection_emojis[index], person.findtext("firstname"),
                                    person.findtext("lastname"))
        embed.add_field(name=name, inline=True, value=constants.ZERO_WIDTH_SPACE)

    return embed


def _parse_staff_xml(str_xml: str) -> Dict[str, Union[datetime, str, None]]:
    """Method for parsing the staff member data returned by `ufind` in XML.

    Parses and prepares the data about a staff member and returns it in a dictionary so it can be posted in an
    embed later.

    Args:
        str_xml (str): String containing data about a staff member in XML.

    Returns:
        Dict[str, str]: A dictionary containing the wanted information about a staff member.
    """
    xml = ET.fromstring(str_xml)

    str_title = _create_staff_embed_title(xml.find("title"), xml.findtext("firstname"), xml.findtext("lastname"))
    str_contact = _create_staff_embed_contact(xml.attrib["id"], xml.find("contact"))
    str_office_hours = _create_staff_embed_office_hours(xml.findtext("hours"))
    str_weblinks = _create_staff_embed_weblinks(xml.attrib["id"], xml.findtext("url"), xml.findtext("ucris"))
    str_assignments = _create_staff_embed_assignments(xml.find("assignments"))
    str_teaching = _create_staff_embed_teaching(xml.attrib["id"], xml.find("teaching"))

    dict_staff = {
        "title": str_title,
        "contact": str_contact,
        "weblinks": str_weblinks,
        "office_hours": str_office_hours,
        "assignments": str_assignments,
        "teaching": str_teaching,
        "last_modified": datetime.strptime(xml.attrib["version"], "%Y-%m-%dT%H:%M:%S%z"),
    }
    return dict_staff


def _create_staff_embed_title(title: Optional[ET.Element], firstname: Optional[str], lastname: Optional[str]) \
        -> Optional[str]:
    """Method for building the string used as a title for the staff embed.

    Args:
        title (Optional[ET.Element]): Element containing the XML data regarding a staff members title.
        firstname (Optional[str]): The firstname of the staff member.
        lastname (Optional[str]): The lastname of the staff member.

    Returns:
        Optional[str]: The title for the staff embed.
    """
    if title is None:
        return None

    staff_title = (title.text or "")
    title_post = title.get("post", default="")

    if title_post != "":
        title_post = ", " + title_post

    return "{0} {1} {2}{3}".format(staff_title, firstname, lastname, title_post)


def _create_staff_embed_contact(staff_id: str, element: Optional[ET.Element]) -> Optional[str]:
    """Method for building the string used in the contact field of the staff embed.

    Args:
        staff_id (str): The ID of the staff member.
        element (Optional[ET.Element]): Element containing the XML data regarding a staff members contact information.

    Returns:
        Optional[str]: The string for the contact field of the staff embed.
    """
    if element is None:
        return None

    email = element.findtext("email", default="-")
    tel_nr = element.findtext("tel", default="-")
    fax_nr = element.findtext("fax", default="-")
    mobil_nr = element.findtext("mobile")
    v_card = constants.URL_UFIND_API + "/staff/" + staff_id + "/card.vcf"

    str_contact = "__Email:__ {0}\n__TelNr:__ {1}\n".format(email, tel_nr)
    if mobil_nr is not None:
        str_contact += "__MobilNr:__ {0}\n".format(mobil_nr)
    str_contact += "__Fax:__ {0}\n[Download vCard]({1})".format(fax_nr, v_card)

    return str_contact


def _create_staff_embed_office_hours(office_hours: Optional[str]) -> Optional[str]:
    """Method for building the string used in the office hours field of the staff embed.

    Args:
        office_hours (Optional[str]): A string containing information about a staff members office hours.

    Returns:
        Optional[str]: The string for the office hours field of the staff embed.
    """
    if office_hours is None:
        return None

    str_office_hours = office_hours

    # Regex substitutions to convert HTML tags into Markdown friendly strings.
    # - Remove mailto links
    str_office_hours = re.sub("<a href=['\"]mailto:(.*)['\"]>.*</a>", r"__\1__", str_office_hours)
    # - HTML to Markdown link
    str_office_hours = re.sub("<a href=['\"](.*)['\"]>(.*)</a>", r"[\1](\2)", str_office_hours)

    return str_office_hours


def _create_staff_embed_weblinks(staff_id: Optional[str], homepage: Optional[str], ucris: Optional[str]) \
        -> Optional[str]:
    """Method for building the string used in the weblinks field of the staff embed.

    Args:
        staff_id (str): The ID of the staff member.
        homepage (Optional[str]): A string containing the URL for a staff members homepage.
        ucris (Optional[str]): A string containing the URL for a staff members u:cris page containing his publications.

    Returns:
        Optional[str]: The string for the weblinks field of the staff embed.
    """
    if staff_id is None:
        return None

    web_ufind = constants.URL_UFIND + "/person.html?id=" + staff_id + "&more=true"
    str_weblinks = "- [u:find]({0})\n".format(web_ufind)

    if homepage is not None:
        str_weblinks += "- [Homepage]({0})\n".format(homepage)
    if ucris is not None:
        embed_friendly_link = ucris.replace("(", "%28").replace(")", "%29")  # URL Encoding
        str_weblinks += "- [Publikationen]({0})\n".format(embed_friendly_link)

    return str_weblinks


def _create_staff_embed_assignments(element: Optional[ET.Element]) -> Optional[str]:
    """Method for building the string used in the assignments field of the staff embed.

    Args:
        element (Optional[ET.Element]): Element containing the XML data regarding a staff members assignments.

    Returns:
        Optional[str]: The string for the assignments field of the staff embed.
    """
    if element is None or len(element) == 0:
        return None

    str_assignments = ""
    for assignment in element:
        str_assignments += "__{0}__\n- {1}\n".format(assignment.findtext("name"), assignment.findtext("role"))

    return str_assignments


def _create_staff_embed_teaching(staff_id: str, element: Optional[ET.Element]) -> Optional[str]:
    """Method for building the string used in the teaching field of the staff embed.

    Args:
        staff_id (str): The ID of the staff member.
        element (Optional[ET.Element]): Element containing the XML data regarding a staff members teaching history.

    Returns:
        Optional[str]: The string for the teaching field of the staff embed.
    """
    if element is None:
        return None

    str_teaching = ""
    for index, semester in enumerate(element):
        str_teaching += "__{0}__\n".format(semester.attrib["id"])

        for course in semester:
            course_type = course.findtext("type")
            course_name = course.findtext("longname")

            if course_type is None:
                course_type = "Undefined"
            if course_name is None:
                course_name = "Undefined"

            # Filter out every Bachelor and Master seminar.
            if course_type != "LP" and "Bachelorseminar" not in course_name and "Masterseminar" not in course_name:
                str_teaching += "- **{0}** {1}\n".format(course_type, course_name)

        if index >= 1:
            break

    url_ufind_teaching = "[Weitere Lehre]({0}/person.html?id={1}&teaching=true)" \
        .format(constants.URL_UFIND, staff_id)

    if len(str_teaching + url_ufind_teaching) > 1024:
        indicator = "- [...]\n"
        chars_remaining = (1024 - len(indicator + url_ufind_teaching))

        str_teaching = str_teaching[:chars_remaining]           # Shorten data to fit into embed
        str_teaching = str_teaching[:str_teaching.rfind("\n") + 1]  # Remove the last incomplete line
        str_teaching += indicator                               # Add indicator that the date has been shortened

    str_teaching += url_ufind_teaching
    return str_teaching


def _create_embed_staff(staff_data: Dict[str, Union[datetime, str, None]]) -> discord.Embed:
    """Method which creates the embed for presenting the data about a staff member.

    Args:
        staff_data (Dict[str, str]): Dictionary containing the data about a specific staff member.

    Returns:
        discord.Embed: Embedded message which lists all the information about staff members returned by `ufind`.
    """
    embed = discord.Embed(color=constants.EMBED_COLOR_UNIVERSITY, title=staff_data["title"],
                          timestamp=staff_data["last_modified"])

    embed.set_footer(text="powered by u:find \U000026A1 Zuletzt geändert")
    embed.add_field(name="Kontakt", inline=True, value=staff_data["contact"])
    embed.add_field(name="Weblinks", inline=True, value=staff_data["weblinks"])
    if staff_data["office_hours"] is not None:
        embed.add_field(name="Sprechstunde", inline=False, value=staff_data["office_hours"])
    if staff_data["assignments"] is not None:
        embed.add_field(name="Funktionen", inline=False, value=staff_data["assignments"])
    if staff_data["teaching"] is not None:
        embed.add_field(name="Lehre", inline=False, value=staff_data["teaching"])

    return embed


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(UniversityCog(bot))
