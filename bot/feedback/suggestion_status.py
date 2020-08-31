"""Module containing a single Enum class for suggestions."""

from enum import Enum


class SuggestionStatus(Enum):
    """An Enum class representing all the different statuses for suggestions."""
    UNDECIDED = 0
    APPROVED = 1
    DENIED = 2
    CONSIDERED = 3
    IMPLEMENTED = 4
