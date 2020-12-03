"""Contains a Cog for all music funcionality."""

import asyncio
from urllib.parse import urlparse

import discord
from discord.ext import commands

from bot import constants as const
from bot.music.ytdl_source import YTDLSource
from bot.logger import command_log, log


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

    # A special method that registers as a commands.check() for every command and subcommand in this cog.
    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)  # Only owners of the bot can use the commands defined in this Cog.

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
        log.info("%s has started playback for the URL \"%s\".", ctx.author, url)

        media_list = await YTDLSource.from_url(url, loop=self.bot.loop)

        if len(self.song_queue) == const.LIMIT_SONG_QUEUE:
            self.song_queue = self.song_queue[len(media_list):]

        for song_url in media_list:
            self.song_queue.append(song_url)  # Use list.append() because it's thread safe.

        if not ctx.voice_client.is_playing():
            while True:
                for song_url in self.song_queue:
                    source = await YTDLSource.get_media(song_url, loop=self.bot.loop)
                    await _stream_media(ctx.voice_client, self.bot.loop, source)

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
            log.info("The loop mode of the music player has been changed by %s.", ctx.author)
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

            log.info("%s stopped the playback", ctx.author)

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


async def _stream_media(voice_client: discord.VoiceClient, loop: asyncio.BaseEventLoop, source: YTDLSource):
    """Method which starts the streaming and playback of the provided URL.

    Args:
        voice_client (discord.VoiceClient): The voice client used by the bot.
        source (YTDLSource): Audio source which contains the audio stream.
    """

    future = loop.create_future() if loop else asyncio.get_event_loop().create_future()
    voice_client.play(source, after=lambda e: log.error("Player error: %s", e) if e else future.set_result(None))

    try:
        # 1 extra second to give the bot a chance to end the playback gracefully.
        await asyncio.wait_for(future, timeout=source.data["duration"] + 1)
    except asyncio.TimeoutError:
        log.error("Player error: Timeout for song playback has been reached.")


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
