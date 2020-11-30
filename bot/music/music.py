"""Contains a Cog for all music funcionality."""

import asyncio
from urllib.parse import urlparse
from typing import List

import discord
import youtube_dl
from discord.ext import commands

from bot import constants as const
from bot.logger import command_log, log

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
    'nocheckcertificate': True,
    'ignoreerrors': False,
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

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class MusicCog(commands.Cog):
    """Cog for music functions."""

    def __init__(self, bot):
        """Initializes the Cog.

        Args:
            bot (discord.ext.commands.Bot): The bot for which this cog should be enabled.
        """
        self.bot = bot
        self.song_queue = list()
        self.loop_mode = False

    @commands.group(name="music", invoke_without_command=True)
    @command_log
    async def music(self, ctx):
        """Command Handler for the `music` command.

        This command provides a collection of subcommands for controlling the integrated music player.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """

        await ctx.send_help(ctx.command)

    @music.command(name="play")
    @command_log
    async def play_music(self, ctx, *, url):
        """Starts the streaming of music provided by URLs or adds them to the song queue.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            url (str): The URL to the song or playlist.
        """
        _check_if_supported_url(url)
        media_list = await YTDLSource.from_url(url, loop=self.bot.loop)

        if len(self.song_queue) == const.LIMIT_SONG_QUEUE:
            self.song_queue = self.song_queue[len(media_list):]

        for song_url in media_list:
            self.song_queue.append(song_url)  # Use list.append() because it's thread safe.

        if not ctx.voice_client.is_playing():
            while True:
                for song_url in self.song_queue:
                    source = await YTDLSource.get_media(song_url, loop=self.bot.loop)
                    await _stream_media(ctx.voice_client, source)

                if not self.loop_mode:
                    break
        else:
            info_message = ("Die Songs wurden" if len(media_list) > 1 else "Der Song wurde") + \
                           " erfolgreich der Wiedergabeliste hinzugefügt."
            await ctx.send(info_message, delete_after=const.TIMEOUT_INFORMATION)

    @music.command(name="loop")
    @command_log
    async def loop_music(self, ctx):
        """Toggles the loop mode if the bot is currently playing songs."""

        if ctx.voice_client and ctx.voice_client.is_playing() and ctx.voice_client.channel == ctx.author.voice.channel:
            self.loop_mode = not self.loop_mode
            await ctx.send("Die aktuelle Wiedergabeliste läuft nun in Dauerschleife.",
                           delete_after=const.TIMEOUT_INFORMATION)

    @music.command(name="stop")
    @command_log
    async def stop_music(self, ctx):
        """Stops and disconnects the bot from the voice channel and resets all instance variables.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """

        if ctx.voice_client and ctx.voice_client.channel == ctx.author.voice.channel:
            await ctx.voice_client.disconnect()
            self.song_queue.clear()
            self.loop_mode = False

    @play_music.before_invoke
    async def ensure_voice(self, ctx):
        """Method which does some checks to ensure that playback is possible.

        If the bot currently is in no voice channel, he will connect to the one the member is currently in. If the
        member who has invoked the command isn't in a voice channel, or is currently not in the same voice channel as
        the bot, a temporary information message will be posted.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
        """
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("Für diesen Befehl musst du dich in einem Sprachkanal befinden.",
                               delete_after=const.TIMEOUT_INFORMATION)
                raise commands.CommandError("User not connected to a voice channel.")

        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send("Der Musik-Player ist bereits von jemanden in Verwendung. Um einen Song der Wiedergabeliste "
                           "hinzufügen zu können, musst du dich im selben Sprachkanal wie SAM befinden.",
                           delete_after=const.TIMEOUT_INFORMATION)
            raise commands.CommandError("User not in same voice channel as bot.")

    @play_music.error
    async def music_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error Handler for the `music` command.

        Handles specific exceptions which occur during the execution of this command. The global error handler will
        still be called for every error thrown.

        Args:
            ctx (discord.ext.commands.Context): The context in which the command was called.
            error (commands.CommandError): The error raised during the execution of the command.
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send("Derzeit werden leider nur YouTube-Links unterstützt.",
                           delete_after=const.TIMEOUT_INFORMATION)


async def _stream_media(voice_client: discord.VoiceClient, source: YTDLSource):
    """Method which starts the streaming and playback of the provided URL.

    Args:
        voice_client (discord.VoiceClient): The voice client used by the bot.
        source (YTDLSource): Audio source which contains the audio stream.
    """

    voice_client.play(source, after=lambda e: log.error("Player error: %s", e) if e else None)
    await asyncio.sleep(source.data["duration"])  # Wait until the song ends before continuation.


def _check_if_supported_url(url: str):
    """Method which raises an exception if the provided URL is not supported.

    Args:
        url (str): The provided URL.
    """

    platforms = ["youtube.com"]
    url_parsed = urlparse(url)
    domain = url_parsed.netloc[4:] if url_parsed.netloc.startswith("www.") else url_parsed.netloc

    if domain not in platforms:
        raise commands.BadArgument("Platform not supported.")


def setup(bot):
    """Enables the cog for the bot.

    Args:
        bot (Bot): The bot for which this cog should be enabled.
    """
    bot.add_cog(MusicCog(bot))
