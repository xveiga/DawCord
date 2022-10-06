# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import sys
import logging
from .reastream.source import ReaStreamAudioSource

_log = logging.getLogger(__name__)


class DawCord(commands.Bot):
    def __init__(
        self,
        channelid=None,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="default",
        resample_quality="HQ",
        gain=1,
        playback_slack=2,
        max_buffer_frames=8,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._channelid = channelid
        self._ipaddr = ipaddr
        self._port = port
        self._identifier = identifier
        self._resample_quality = resample_quality
        self._gain = gain
        self._playback_slack = playback_slack
        self._max_buffer_frames = max_buffer_frames
        self.voiceclient = None

    async def on_ready(self):
        _log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        try:
            # Get channel ID
            self.channel = self.get_channel(self._channelid)
            if not self.channel:
                _log.error(
                    f"Channel {self._channelid} could not be found or does not exist",
                    file=sys.stderr,
                )
                await self.close()
                return

            # Connect to voicechannel
            self.voiceclient = await self.channel.connect()
            _log.info(f"Connected to {self._channelid}")

            # Set bot as "deaf", not receiving audio/listening to other users
            await self.channel.guild.change_voice_state(
                channel=self.channel, self_mute=False, self_deaf=True
            )

            # Configure audio source from ReaStream
            self.audiosource = ReaStreamAudioSource(
                ipaddr=self._ipaddr,
                port=self._port,
                identifier=self._identifier,
                resample_quality=self._resample_quality,
                gain=self._gain,
                playback_slack=self._playback_slack,
                max_buffer_frames=self._max_buffer_frames,
            )

            # Start audio transmission
            self.voiceclient.play(self.audiosource)
            _log.info("ReaStream sink is alive")

        except PermissionError as e:
            _log.error(
                f"Could not bind to UDP socket {self._ipaddr}:{self._port}.\n"
                f"Make sure no other program is bound to that port or check your firewall settings.\n{str(e)}",
                file=sys.stderr,
            )
            await self.close()
        except Exception as e:
            _log.error(str(e), file=sys.stderr)
            await self.close()

    async def on_voice_state_update(self, member, before, after):
        # Stop bot if kicked/disconnected from voice channel
        if member.id == self.user.id and after.channel is None:
            await self.close()

    async def close(self):
        _log.info("Disconnecting...")
        if self.voiceclient:
            # Disconnect voice
            await self.voiceclient.disconnect()
            # Set status as offline before disconnecting, avoids disconnected status delay
            await self.change_presence(status=discord.Status.offline)
        # Stop bot
        await super().close()

    async def on_command_error(self, ctx, error):
        # Stop bot on exception
        await self.close()
