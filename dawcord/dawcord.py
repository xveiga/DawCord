# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import sys
import logging
from .audiosource.reastream.source import ReaStreamAudioSource
from .audiosource.pyaudio.source import PyAudioSource

_log = logging.getLogger(__name__)


class DawCord(commands.Bot):
    def __init__(
        self,
        channelid=None,
        config=None,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="default",
        resample_quality="HQ",
        opus_application="audio",
        opus_bitrate=128,
        opus_fec=True,
        opus_expected_packet_loss=0.15,
        opus_bandwidth="full",
        opus_signal_type="music",
        gain=1,
        playback_slack=2,
        max_buffer_frames=8,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._channelid = channelid
        self._config = config
        self._ipaddr = ipaddr
        self._port = port
        self._identifier = identifier
        self._resample_quality = resample_quality
        self._opus_application = opus_application
        self._opus_bitrate = opus_bitrate
        self._opus_fec = opus_fec
        self._opus_expected_packet_loss = opus_expected_packet_loss
        self._opus_bandwidth = opus_bandwidth
        self._opus_signal_type = opus_signal_type
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
                )
                await self.close()
                return

            # Check config is valid
            if self._config is None:
                _log.error(
                    f"Configuration could not be read or does not exist",
                )
                await self.close()
                return

            # Setup audio source from configuration file
            try:
                if self._config["source"] == "reastream":
                    source_config = self._config["source.reastream"]
                    self.audiosource = ReaStreamAudioSource(
                        ipaddr=source_config["ip"],
                        port=source_config["port"],
                        identifier=source_config["identifier"],
                        resample_quality=source_config["resample_quality"],
                        gain=source_config["gain"],
                        playback_slack=source_config["playback_slack_frames"],
                        max_buffer_frames=source_config["max_buffer_frames"],
                    )
                elif self._config["source"] == "pyaudio":
                    source_config = self._config["source.pyaudio"]
                    self.audiosource = PyAudioSource(
                        device_name=source_config["device_name"],
                        gain=source_config["gain"],
                        playback_slack=source_config["playback_slack_frames"],
                        max_buffer_frames=source_config["max_buffer_frames"],
                    )
            except KeyError as e:
                _log.error(
                    "Could not find configuration key: " + e.messsage
                    if hasattr(e, "message")
                    else str(e)
                )

            # Connect to voicechannel
            self.voiceclient = await self.channel.connect()
            _log.info(f"Connected to {self._channelid}")

            # Set bot as "deaf", not receiving audio/listening to other users
            await self.channel.guild.change_voice_state(
                channel=self.channel, self_mute=False, self_deaf=True
            )

            # Start audio transmission
            try:
                encoder_config = self._config["encoder"]
                self.voiceclient.play(
                    self.audiosource,
                    application=encoder_config["application"],
                    bitrate=encoder_config["bitrate"],
                    fec=encoder_config["fec"],
                    expected_packet_loss=encoder_config["expected_packet_loss"],
                    bandwidth=encoder_config["bandwidth"],
                    signal_type=encoder_config["signal_type"],
                )
                _log.info("Audio sink is alive")
            except KeyError as e:
                _log.error(
                    "Could not find configuration key: " + e.messsage
                    if hasattr(e, "message")
                    else str(e)
                )

        except PermissionError as e:
            # TODO: Rewrite error messsage depending on source class
            _log.error(
                f"Could not bind to UDP socket {self._ipaddr}:{self._port}.\n"
                f"Make sure no other program is bound to that port or check your firewall settings.\n{str(e)}",
            )
            await self.close()
        except Exception as e:
            _log.error(str(e))
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
