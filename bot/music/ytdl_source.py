"""Class which represents a YoutTube streaming source for the music player."""

import asyncio
from typing import List

import discord
import youtube_dl


ffmpeg_options = {
    'options': '-vn -loglevel quiet',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'extract_flat': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Bind to ipv4 since ipv6 addresses cause issues sometimes
}
youtube_dl.utils.bug_reports_message = lambda: ''  # Suppress noise about console usage from errors
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    """Class which stores data about a specific Youtube-Source."""

    def __init__(self, source, *, data, volume=0.1):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True) -> List[str]:
        """Method for the video URLs of the provided link.

        Args:
            url (str): The URL to the specified song or playlist.
            loop (bool): The event loop provided by the bot.
            stream (bool): Indicates if the information should be streamed instead of downloaded.
        """

        clean_url = url.split("&", 1)[0]
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(clean_url, download=not stream))

        if not data:
            raise discord.InvalidArgument("Invalid video URL.")

        if "entries" in data:
            return ["https://www.youtube.com/watch?v={0}".format(entry["url"]) for entry in data["entries"]]

        return [clean_url]

    @classmethod
    async def get_media(cls, url, *, loop=None, stream=True):
        """Method for extracting info of video provided by the URL.

        Args:
            url (str): The URL to the specified song.
            loop (bool): The event loop provided by the bot.
            stream (bool): Indicates if the information should be streamed instead of downloaded.
        """

        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if not data:
            raise discord.InvalidArgument("Invalid video URL.")

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
