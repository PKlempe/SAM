"""Contains a Cog for all functionality regarding our University."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from sqlite3 import IntegrityError
from typing import Dict, List, Optional, Union, Iterable, Tuple

import discord
import requests
from discord.ext import commands

from bot import constants
from bot.logger import command_log
from bot.persistence import DatabaseConnector
from bot.util import SelectionEmoji


class UniversityCog(commands.Cog):
    """Cog for Functions regarding the IT faculty or the University of Vienna as a whole."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self._db_connector = DatabaseConnector(constants.DB_FILE_PATH, constants.DB_INIT_SCRIPT)

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

    @ufind.command(name='staff')
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
        search_filters = "%20%2Be%20c%3A6"  # URL Encoding
        response = requests.get(constants.URL_UFIND_API + "/staff/?query=" + search_term + search_filters)
        response.encoding = "utf-8"

        if response.status_code == 200:
            xml = ET.fromstring(response.text)
            persons = xml.findall("person")
            index = 0

            if len(persons) > 0:
                if len(persons) > 1:
                    index = await self._staff_selection(ctx.author, ctx.channel, persons)

                response = requests.get(constants.URL_UFIND_API + "/staff/" + persons[index].attrib["id"])
                response.encoding = "utf-8"

                staff_data = _parse_staff_xml(response.text)
                embed = _create_embed_staff(staff_data)
                await ctx.channel.send(embed=embed)
            else:
                raise ValueError("No person with the specified name was found.")
        else:
            response.raise_for_status()

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
            await ctx.send("Ich konnte leider niemanden unter dem von dir angegeben Namen finden. :slight_frown: "
                           "Möglicherweise hast du dich vertippt.")

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
        timeout = 15.0
        list_selection_emojis = SelectionEmoji.to_list()

        embed = _create_embed_staff_selection(persons)
        message = await channel.send(embed=embed)

        for i in range(len(embed.fields)):
            await message.add_reaction(list_selection_emojis[i])

        def check_reaction(_reaction, user):
            return user == author and SelectionEmoji(_reaction.emoji) is not None

        await message.delete(delay=timeout)
        reaction = await self.bot.wait_for('reaction_add', timeout=timeout + 0.1, check=check_reaction)
        await message.delete()

        return list_selection_emojis.index(reaction[0].emoji)

    @commands.group(name='exchange', hidden=True, invoke_without_command=True)
    @command_log
    async def exchange(self,
                       ctx: commands.Context,
                       channel: discord.TextChannel,
                       offered_group: int,
                       *, requested_groups_str: str):
        """Command Handler for the exchange command

        Creates a new request for group exchange. Posts an embed in the group exchange channel, adds according entries
        in the db and notifies the poster and all possible partners for group exchange with a DM.

        Args:
            ctx (Context): The context in which the command was called.
            channel (discord:TextChannel): The channel corresponding to the course for group change.
            offered_group (int): The group that the user offers.
            requested_groups (List[int]): A list of all groups the user would be willing to take.
        """

        def group_to_int(group):
            try:
                return int(group)
            except ValueError:
                raise SyntaxError("Invalid symbol in list of requested groups: " + group)

        requested_groups = list(map(group_to_int, requested_groups_str.split(',')))

        if offered_group in requested_groups:
            raise ValueError("Offered Group was in a requested Groups. Offered Group {0}, Requested Groups: {1}".format(
                offered_group, requested_groups)
            )
        self._db_connector.add_group_offer_and_requests(ctx.author.id,
                                                        channel.id,
                                                        offered_group,
                                                        requested_groups)
        embed = _build_group_exchange_embed(ctx.author, channel, offered_group, requested_groups)
        message = await ctx.guild.get_channel(constants.CHANNEL_ID_GROUP_EXCHANGE).send(embed=embed)
        self._db_connector.update_group_exchange_message_id(ctx.author.id, channel.id, message.id)
        potential_candidates = self._db_connector.get_candidates_for_group_exchange(ctx.author.id,
                                                                                    channel.id,
                                                                                    offered_group,
                                                                                    requested_groups)
        if potential_candidates is not None:
            await self._notfiy_author_about_candidates(ctx.author,
                                                       potential_candidates,
                                                       ctx.guild.get_channel(constants.CHANNEL_ID_GROUP_EXCHANGE),
                                                       channel)
            await self._notify_candidates_about_new_offer(potential_candidates,
                                                          ctx.author,
                                                          message,
                                                          channel,
                                                          offered_group)

    @exchange.error
    async def exchange_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, ValueError):
            await ctx.channel.send(
                "**__Error:__** Unter deinen Wunschgruppen befindet sich die Gruppe die du anbietest.",
                delete_after=15.0)
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, IntegrityError):
            await ctx.channel.send(
                "**__Error:__** Du hast für diesen Kurs bereits eine Tauschanfrage aktiv. Du kannst sie mit "
                "'exchange remove <channel-mention> löschen.'", delete_after=15.0)
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, SyntaxError):
            await ctx.channel.send(
                "**__Error:__** Du hast einen Fehler beim Eingeben deiner Wunschgruppen gemacht. Bitte gib die "
                "Gruppennummer mit Beistrichen getrennt und ohne Leerzeichen ein. Beispiel: 2,3,4",
                delete_after=15.0)

    @exchange.command(name="remove", hidden=True)
    @command_log
    async def remove_exchange(self, ctx: commands.Context, channel: discord.TextChannel):
        """Removes an group exchange request.

        Deletes the message in the exchange channel as well as all corresponding entries in the db.

        Args:
            ctx (discord.ext.commands.Context): The context from which this command is invoked.
            channel (discord.TextChannel): The channel corresponding to the course.
        """
        message_id = self._db_connector.get_group_exchange_message(ctx.author.id, channel.id)
        if message_id is not None:
            self._db_connector.remove_group_exchange_offer(ctx.author.id, channel.id)
            msg = await ctx.guild.get_channel(constants.CHANNEL_ID_GROUP_EXCHANGE).fetch_message(message_id)
            await msg.delete()

    async def _notfiy_author_about_candidates(self,
                                              author: discord.User,
                                              potential_candidates: List[Tuple[str, str, int]],
                                              channel: discord.TextChannel,
                                              course_channel: discord.TextChannel):
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
        embed = discord.Embed(title="Wir haben potentielle Tauschpartner für dich gefunden:",
                              description="Bitte vergiss nicht, deine Anfrage mit dem Befehl 'exchange remove "
                                          "<channel-mention>' wieder zu löschen, wenn du einen Tauschpartner gefunden "
                                          "hast",
                              color=constants.EMBED_COLOR_GROUP_EXCHANGE)
        user_string = ""
        group_string = ""
        course_name = "- " + _parse_course_from_channel_name(course_channel)
        course_name = "\n".join(course_name for _ in potential_candidates)

        for candidate in potential_candidates:
            user = self.bot.get_user(int(candidate[0]))
            msg = await channel.fetch_message(int(candidate[1]))
            group = candidate[2]
            user_string += "- [{0}]({1})\n".format(user, msg.jump_url)
            group_string += "- Gruppe {0}\n".format(group)

        embed.add_field(name="User:", value=user_string) \
            .add_field(name="Kurs:", value=course_name) \
            .add_field(name="Bietet:", value=group_string)

        await author.send(embed=embed)

    async def _notify_candidates_about_new_offer(self, potential_candidates: List[Tuple[str, str, int]],
                                                 author: discord.User,
                                                 message: discord.Message,
                                                 course_channel: discord.TextChannel,
                                                 offered_group: int):

        """Notifies all potential candidates that a new relevant group exchange offer has been posted.

        The candidates are informed via a direct message which contains infos about the new offer he or seh could
        exchange groups with.

        Args:
            potential_candidates (List[Tuple[str, str]]): The possible candidate ids and the message ids of their
            exchange messages. They are to be informed
            author (discord.User): The author to be notified.
            message: (discord.Message): The message containing the new offer.
            channel (discord.TextChannel): The channel that refers to the course that the exchange is for.
            offered_group (int): The group that the author offers.
        """
        course_name = _parse_course_from_channel_name(course_channel)
        embed = discord.Embed(title="Wir haben ein neues Tauschangebot für dich gefunden:",
                              description="Bitte vergiss nicht, deine Anfrage mit dem Befehl 'exchange remove "
                                          "<channel-mention>' wieder zu löschen, wenn du einen Tauschpartner gefunden "
                                          "hast",
                              color=constants.EMBED_COLOR_GROUP_EXCHANGE) \
            .set_thumbnail(url=author.avatar_url) \
            .add_field(name="User:", value="[{0}]({1})".format(author, message.jump_url)) \
            .add_field(name="Kurs:", value=course_name) \
            .add_field(name="Bietet:", value="Gruppe {0}".format(offered_group))
        for candidate in potential_candidates:
            print("sending")
            # await self.bot.get_user(int(candidate[0])).send(embed=embed)


def _build_group_exchange_embed(author: discord.User,
                                channel: discord.TextChannel,
                                offered_group: int,
                                requested_groups: Iterable[int]) -> discord.Embed:
    """Builds an embed for a group exchange request.

    The embed contains information about who wants to exchange groups, which groups he offers and requests and for what
    courses.

    Args:
        author (discord.User): The author of the embed (aka the user who wants to change groups).
        channel (discord.TextChannel): The channel that refers to the course that should be changed.
        offered_group (int): The group that the user offers.
        requested_groups (List[int]): The groups that the user would accept.

    Returns:
        (discord.Embed): The embed with the group exchange request.
    """
    return discord.Embed(title=_parse_course_from_channel_name(channel),
                         color=constants.EMBED_COLOR_GROUP_EXCHANGE) \
        .set_thumbnail(url=author.avatar_url) \
        .add_field(name="Biete:",
                   value="Gruppe {0}".format(offered_group)) \
        .add_field(name="Suche:",
                   value="Gruppen {0}".format(", ".join(map(lambda i: str(i), requested_groups)))) \
        .add_field(name="Eingereicht von:",
                   value="{0}\n{0.mention}".format(author),
                   inline=False)


def _parse_course_from_channel_name(channel: discord.TextChannel):
    """Parses the course name from a discord channel name

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
    last_semester = None
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
            last_semester = semester.attrib["id"]
            break
    str_teaching += "[Lehre vor {0}]({1}/person.html?id={2}&teaching=true)" \
        .format(last_semester, constants.URL_UFIND, staff_id)

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
    # embed.set_thumbnail(url=constants.URL_UFIND_LOGO)
    embed.set_footer(text="powered by u:find <> Zuletzt geändert")
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
