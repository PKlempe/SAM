"""Module containing a single Enum class for selection emojis."""

from enum import Enum


class SelectionEmoji(Enum):
    """An Enum class representing all the different emojis used for selection embeds.

    These are all number emojis ranging from 1 to 10.
    """
    ONE = "\U00000031\U0000FE0F\U000020E3"
    TWO = "\U00000032\U0000FE0F\U000020E3"
    THREE = "\U00000033\U0000FE0F\U000020E3"
    FOUR = "\U00000034\U0000FE0F\U000020E3"
    FIVE = "\U00000035\U0000FE0F\U000020E3"
    SIX = "\U00000036\U0000FE0F\U000020E3"
    SEVEN = "\U00000037\U0000FE0F\U000020E3"
    EIGHT = "\U00000038\U0000FE0F\U000020E3"
    NINE = "\U00000039\U0000FE0F\U000020E3"
    TEN = "\U0001F51F"

    @classmethod
    def to_list(cls):
        """Method returning a list containing all elements of this Enum class."""
        return list(map(lambda emoji: emoji.value, cls))
