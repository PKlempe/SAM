"""This module contains subclasses of some UI elements needed for the selection of university courses."""
import discord

from bot.persistence import DatabaseConnector


class CourseSelect(discord.ui.Select):
    """Class which represents a Select menu containing university courses."""

    def __init__(self, courses, db_connector: DatabaseConnector):
        super().__init__(placeholder='Wähle die gewünschte LV aus...', min_values=1, max_values=1, options=courses)
        self._db_connector = db_connector

    async def callback(self, interaction: discord.Interaction):
        """Callback method which gets called when a user selects one of the provided options in the Select menu.

        Adds or removes a so called course role from the user based on the their selection. Each select option contains
        the course ID of the corresponding university course based on which the correct role will be selected.

        Args:
            interaction (discord.Interaction): The interaction during which this callback was triggered.
        """
        role_id = self._db_connector.get_course_role(self.values[0])
        role = interaction.guild.get_role(role_id)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, atomic=True, reason='Selbstständig entfernt via SAM.')
            await interaction.response.edit_message(content=':white_check_mark: Kurs-Rolle erfolgreich entfernt.',
                                                    view=None)
        else:
            await interaction.user.add_roles(role, atomic=True, reason='Selbstständig zugewiesen via SAM.')
            await interaction.response.edit_message(content=':white_check_mark: Kurs-Rolle erfolgreich hinzugefügt.',
                                                    view=None)
