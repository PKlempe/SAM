"""This module contains subclasses of some UI elements needed for the selection of university courses."""
import discord
from typing import List

from bot import constants
from bot.logger import log
from bot.persistence import DatabaseConnector


class CourseSelect(discord.ui.Select):
    """Class which represents a Select menu containing university courses."""

    def __init__(self, courses, db_connector: DatabaseConnector):
        super().__init__(placeholder='Wähle die gewünschte LV aus...', min_values=1, max_values=len(courses),
                         options=courses)
        self._db_connector = db_connector

    async def callback(self, interaction: discord.Interaction):
        """Callback method which gets called when a user selects one of the provided options in the Select menu.

        Adds or removes a so-called course role from the user based on their selection. Each select option contains
        the course ID of the corresponding university course based on which the correct role will be selected.

        Args:
            interaction (discord.Interaction): The interaction during which this callback was triggered.
        """
        self.view.stop()
        missing_courses = []

        for course_id in self.values:
            role_id = self._db_connector.get_course_role(course_id)

            if not role_id:
                missing_courses.append(course_id)
                continue

            role = interaction.guild.get_role(role_id)

            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, atomic=True, reason='Selbstständig entfernt via SAM.')
            else:
                await interaction.user.add_roles(role, atomic=True, reason='Selbstständig zugewiesen via SAM.')

        have_roles_changed = len(missing_courses) < len(self.values)
        if have_roles_changed:
            log.info("Course roles of the member %s have been changed.", interaction.user)

        if not missing_courses:
            str_response = ':white_check_mark: **Deine Kurs-Rollen wurden erfolgreich angepasst.**'
        else:
            relevant_options = [o for o in self.options if o.value in missing_courses]
            embed_info = _build_missing_course_embed(interaction.user, relevant_options)

            bot_channel = interaction.guild.get_channel(int(constants.CHANNEL_ID_BOT))
            await bot_channel.send(embed=embed_info)

            if have_roles_changed:
                str_response = ':warning: **Deine Kurs-Rollen wurden angepasst, jedoch gab es anscheinend Probleme:**'
            else:
                str_response = ':sos: **Deine Kurs-Rollen konnten leider nicht angepasst werden:**'

            str_response += '```Es wurde für mindestens einen der von dir ausgewählten Kurse noch kein Textkanal ' \
                            'und/oder Rolle erstellt.```\nIch habe die Moderatoren über dieses Problem informiert ' \
                            'und sie werden sich schnellstmöglich darum kümmern. Bitte versuche es später noch einmal.'

        await interaction.response.edit_message(view=None, content=str_response)
        response = await interaction.original_response()
        await response.delete(delay=constants.TIMEOUT_INFORMATION)


def _build_missing_course_embed(author: discord.Member, course_options: List[discord.SelectOption]) -> discord.Embed:
    """Method which builds the embed which is sent to the configured bot channel if a course channel doesn't exist.

    Args:
        author (discord.Member): The user who tried to unlock course channels.
        course_options (List[discord.SelectOption]): The list of SelectOptions representing the courses for which
                                                     channels are missing.

    Returns:
        discord.Embed: The embed representing the information for the moderators that a course channel is missing.
    """
    description = f"User {author.mention} versuchte soeben sich folgende Kurse freizuschalten, für die es noch " \
                  f"keinen Kanal und/oder keine Rolle am Server zu geben scheint:"

    embed = discord.Embed(title="Fehlende Kurskanäle!", color=constants.EMBED_COLOR_MODERATION, description=description,
                          timestamp=discord.utils.utcnow())
    embed.set_author(name=str(author), icon_url=author.display_avatar)

    for option in course_options:
        embed.add_field(name=option.label, value=option.value, inline=True)

    return embed
