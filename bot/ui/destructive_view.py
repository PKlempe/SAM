"""This module contains a subclass of the UI element View"""
import discord


class DestructiveView(discord.ui.View):
    """Class which represents a View that deletes the original message of which it is part of after it times out."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message: discord.Message | None = None

    async def on_timeout(self):
        """Callback method which gets called when the view's timeout elapses without being explicitly stopped.

        Disables all items inside the view and deletes the original message of which it is part of.
        """
        for item in self.children:
            item.disabled = True

        if self.message:
            await self.message.delete()
