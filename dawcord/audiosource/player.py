# -*- coding: utf-8 -*-
import time
import logging

from typing import (
    Any,
    Callable,
    Optional,
)

import discord.opus as opus
from discord.player import AudioSource
from discord.enums import SpeakingState
from discord.player import AudioPlayer
from discord.errors import ClientException

_log = logging.getLogger(__name__)


# Taken from discord.player.AudioPlayer with the loop delay removed
# Allows the source to control the audio playback flow for live sources
# whose pacing can skew, without imposing an arbitrary packet delay.
class NonBlockingAudioPlayer(AudioPlayer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _do_run(self) -> None:
        self.loops = 0
        self._start = time.perf_counter()

        # getattr lookup speed ups
        client = self.client
        play_audio = client.send_audio_packet
        self._speak(SpeakingState.voice)

        while not self._end.is_set():
            # are we paused?
            if not self._resumed.is_set():
                self.send_silence()
                # wait until we aren't
                self._resumed.wait()
                continue

            data = self.source.read()

            if not data:
                self.stop()
                break

            # are we disconnected from voice?
            if not client.is_connected():
                _log.debug("Not connected, waiting for %ss...", client.timeout)
                # wait until we are connected, but not forever
                connected = client.wait_until_connected(client.timeout)
                if self._end.is_set() or not connected:
                    _log.debug("Aborting playback")
                    return
                _log.debug("Reconnected, resuming playback")
                self._speak(SpeakingState.voice)
                # reset our internal data
                self.loops = 0
                self._start = time.perf_counter()

            play_audio(data, encode=not self.source.is_opus())
            self.loops += 1
            # Remove delay
            # next_time = self._start + self.DELAY * self.loops
            # delay = max(0, self.DELAY + (next_time - time.perf_counter()))
            # time.sleep(delay)

        if client.is_connected():
            self.send_silence()


# Taken from discord.voice_client.VoiceClient with the AudioSource class replaced by
# a custom NonBlockingAudio player (see below)
def non_blocking_play(
    self,
    source: AudioSource,
    *,
    after: Optional[Callable[[Optional[Exception]], Any]] = None,
    application="audio",
    bitrate: int = 128,
    fec: bool = True,
    expected_packet_loss: float = 0.15,
    bandwidth="full",
    signal_type="auto",
) -> None:
    if not self.is_connected():
        raise ClientException("Not connected to voice.")

    if self.is_playing():
        raise ClientException("Already playing audio.")

    if not isinstance(source, AudioSource):
        raise TypeError(
            f"source must be an AudioSource not {source.__class__.__name__}"
        )

    if not source.is_opus():
        self.encoder = opus.Encoder(
            application=application,
            bitrate=bitrate,
            fec=fec,
            expected_packet_loss=expected_packet_loss,
            bandwidth=bandwidth,
            signal_type=signal_type,
        )

    self._player = NonBlockingAudioPlayer(source, self, after=after)
    self._player.start()
