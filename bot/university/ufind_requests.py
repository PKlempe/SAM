"""Module containing functions for requesting data from the u:find API."""
import xml.etree.ElementTree as ET
from discord import SelectOption

from bot import constants, singletons


async def get_course_options(search_term: str) -> list[SelectOption]:
    """A function which returns a list of SelectOptions representing university courses.

    Sends a GET request to the API of the service called `u:find` which is run by the University of Vienna. Based on the
    hard-coded search filters below, the response should consist of a XML file containing information about university
    courses matching the given search term. For each result a SelectOption will be created which can then be used for
    Discord's Select Menus.

    Args:
        search_term (str): The search term which should be used to query the available courses.
    """
    # URL Encoding - https://ufind.univie.ac.at/de/help.html
    search_filters = "%20spl5%20%2Bcy%20ctype%3AVU%2CVO%2CSE%2CLP%20c%3A25"
    query_url = f"{constants.URL_UFIND_API}/courses/?query={search_term}{search_filters}"
    course_options = []

    async with singletons.HTTP_SESSION.get(query_url) as response:
        response.raise_for_status()
        course_data = await response.text(encoding='utf-8')
        xml_courses = ET.fromstring(course_data)

    courses = xml_courses.findall("course")
    seen_course_ids = set()

    for course in courses:
        course_id = course.get("id")

        if course_id in seen_course_ids:
            continue

        seen_course_ids.add(course_id)

        course_name = course.find("longname").text
        course_type = course.find("type").text
        course_ects = course.find("ects").text
        option_description = f"{course_type} [{course_ects} ECTS]"

        lecturers = course.find("./groups/group/lecturers").findall("lecturer")

        for lecturer in lecturers:
            firstname = lecturer.find("firstname").text
            lastname = lecturer.find("lastname").text
            option_description += f" | {firstname} {lastname}"

        option_description = option_description if len(option_description) <= 100 else f"{option_description[:97]}..."
        select_option = SelectOption(label=course_name, value=course_id, description=option_description)
        course_options.append(select_option)

    return course_options
