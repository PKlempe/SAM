from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from typing import Optional, Tuple


def get_pretty_string_duration(delta_seconds: int) -> str:
    weeks, remainder = divmod(delta_seconds, 604800)
    days, remainder = divmod(remainder, 86400)
    hours, remainder = divmod(remainder, 3600)
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


def get_future_timestamp(duration) -> Tuple[datetime, str]:
    delta_seconds = timeparse(duration)

    if not delta_seconds or delta_seconds < 1:
        raise ValueError("Invalid duration.")

    pretty_duration = get_pretty_string_duration(delta_seconds)
    timestamp = datetime.now() + timedelta(seconds=delta_seconds)

    return timestamp, pretty_duration
