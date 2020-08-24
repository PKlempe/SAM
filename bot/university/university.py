"""Contains a Cog for all functionality regarding our University."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Union
from sqlite3 import IntegrityError

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
                                   f"versuche es dort noch einmal. ", delete_after=8)
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
                           delete_after=8)
        except IntegrityError:
            await ctx.send(f"Die Rolle \"**__{module_role}__**\" gehört bereits zu den verfügbaren Modul-Rollen.",
                           delete_after=8)

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
                       delete_after=8)

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
        .add_field(name=":red_circle: **Entfernte Module:**", value="- Keine", inline=True)\
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
