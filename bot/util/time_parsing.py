"""Module containing functions regarding time parsing."""

from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse


def get_pretty_string_duration(duration: str) -> str:
    """Converts a duration into a pretty string representation.

    Args:
        duration (str): The provided time duration in some human-readable form. (e.g. 2w 1h 8m)

    Returns:
        str: The provided duration in an easily readable form.
    """
    seconds = timeparse(duration)

    if not seconds or seconds < 1:
        raise ValueError("Invalid duration.")

    weeks, remainder = divmod(seconds, 60 * 60 * 24 * 7)
    days, remainder = divmod(remainder, 60 * 60 * 24)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)

    time_units = []
    if weeks > 0:
        time_units.append(f"{weeks} Wochen" if weeks > 1 else "1 Woche")
    if days > 0:
        time_units.append(f"{days} Tage" if days > 1 else "1 Tag")
    if hours > 0:
        time_units.append(f"{hours} Stunden" if hours > 1 else "1 Stunde")
    if minutes > 0:
        time_units.append(f"{minutes} Minuten" if minutes > 1 else "1 Minute")

    return ", ".join(time_units)


def get_future_timestamp(duration: str) -> datetime:
    """Creates a timestamp representing the moment after the specified duration has passed.

    Args:
        duration (str): The provided time duration in some human-readable form. (e.g. 2w 1h 8m)

    Returns:
        datetime: A timestamp representing the moment in the future after the duration has passed.
    """
    delta_seconds = timeparse(duration)

    if not delta_seconds or delta_seconds < 1:
        raise ValueError("Invalid duration.")

    timestamp = datetime.now() + timedelta(seconds=delta_seconds)
    return timestamp
