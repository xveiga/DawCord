# -*- coding: utf-8 -*-

import discord
import logging
import socket
from threading import Thread, Lock, Event
from math import gcd, floor

from ..conversion.resampler import Resampler
from ..conversion.converter import (
    silence_16le,
    db_to_val,
)

_log = logging.getLogger(__name__)


class BaseAudioSource(discord.AudioSource):
    # See read() method for details
    TARGET_SAMPLE_RATE = 48000
    # Number of samples = Time delay * sample rate * 2 (stereo) * 2 bytes (16-bit PCM)
    TARGET_FRAME_SIZE = floor(
        discord.player.AudioPlayer.DELAY * TARGET_SAMPLE_RATE * 2 * 2
    )

    def read(self):
        # Discord.py expects 20ms worth of 48kHz 16-bit (2 byte) stereo (2) PCM (0.02*48000*2*2 = 3840 bytes)
        # VoiceMeeter may send packets of variable size depending on the buffer size configuration and latency.
        # It's therefore necessary to buffer the frames to provide a constant output to discord.py's opus encoder.

        # If not enough frames are available
        if len(self._buffer) < BaseAudioSource.TARGET_FRAME_SIZE:
            # Wait for buffer to fill up again
            if not self._buffer_wait_event.wait(timeout=self._timeout):
                # If timeout exceeded, insert silence
                if not self._buffer_empty:
                    _log.info(
                        f"Buffer empty ({len(self._buffer)}/{BaseAudioSource.TARGET_FRAME_SIZE}), inserting silence"
                    )
                    self._buffer_empty = True
                # Clear buffer to prevent clicks by concatenating old data when the stream is resumed
                self._buffer = bytearray()
                return bytes(silence_16le(BaseAudioSource.TARGET_FRAME_SIZE >> 1))

        # When enough frames are available, reset buffer empty message flag and return audio frames
        self._buffer_empty = False
        self._buffer_lock.acquire()
        # Return only the target number of frames
        return_frames = self._buffer[: BaseAudioSource.TARGET_FRAME_SIZE]
        # The remaining frames are stored to be concatenated on the next function call
        self._buffer = self._buffer[BaseAudioSource.TARGET_FRAME_SIZE :]
        self._buffer_lock.release()

        # Reset buffer wait flag
        self._buffer_wait_event.clear()
        # _log.info(f"Play position: {len(self._buffer)/TARGET_FRAME_SIZE:.2f}")
        return bytes(return_frames)

    def is_opus(self):
        return False


class UDPBaseAudioSource(BaseAudioSource):
    def __init__(
        self,
        ipaddr="127.0.0.1",
        port=4422,
        identifier="",
        timeout=2.0,
        resample_quality="VHQ",
        max_buffer_frames=4,
        playback_slack=1,
        gain=0,
    ):
        # Receive data via UDP socket
        self._udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to address and port
        self._udpsock.bind((ipaddr, port))
        self._udpsock.settimeout(timeout)
        self._timeout = timeout
        self._identifier = identifier
        self._resample_quality = resample_quality
        self._gain = db_to_val(gain)
        self._max_buffer_frames = int(max_buffer_frames)
        self._playback_slack = int(playback_slack)
        self._target_slack_frames = int(
            BaseAudioSource.TARGET_FRAME_SIZE * self._playback_slack
        )
        self._buffer = bytearray()
        self._buffer_lock = Lock()
        self._buffer_wait_event = Event()
        self._buffer_empty = False
        self._channel_count = 0
        self._sample_rate = 0
        self._resampler = None
        self._resample_min_buffer = 0
        self._receive_thread_run = True
        self._receive_thread = Thread(target=self._receive_thread_func)
        self._receive_thread.start()

    def _on_format_change(self, sample_rate, channel_count, format):
        _log.info(
            f"Audio format update: {self._sample_rate}Hz {self._channel_count}ch -> {sample_rate}Hz {channel_count}ch"
        )
        self._sample_rate = sample_rate
        self._channel_count = channel_count

        if self._sample_rate != BaseAudioSource.TARGET_SAMPLE_RATE:
            self._resampler = Resampler(
                self._sample_rate,
                BaseAudioSource.TARGET_SAMPLE_RATE,
                self._channel_count,
                quality=self._resample_quality,
                format=format,
            )
            self._resample_min_buffer = gcd(
                self._sample_rate, BaseAudioSource.TARGET_SAMPLE_RATE
            )
        else:
            self._resampler = None
            self._resample_min_buffer = 0

    def _receive_thread_func(self):
        while self._receive_thread_run:
            # If number of frames exceeds limit, clear buffer to refill it with fresh frames.
            # This is not ideal as it introduces clicking, but is camouflaged well enough
            # with discord's opus encoding and keeps latency in check
            max_size = self._max_buffer_frames * BaseAudioSource.TARGET_FRAME_SIZE
            if len(self._buffer) > max_size:
                _log.info(f"Buffer overrun ({len(self._buffer)}/{max_size}), clearing")
                self._buffer_lock.acquire()
                # Remove all but latest frame
                self._buffer = self._buffer[-BaseAudioSource.TARGET_FRAME_SIZE :]
                self._buffer_lock.release()

            # Append frames to buffer
            frames = self._receive()
            if frames:
                # Do resampling, bit-depth and channel conversion.
                frames = self._process_frames(frames, self._channel_count)
                # From here onwards it's always a 16-bit stereo signal
                self._buffer_lock.acquire()
                self._buffer += frames
                self._buffer_lock.release()

            # Release buffer and notify reading thread data if enough frames are stored
            if len(self._buffer) >= self._target_slack_frames:
                self._buffer_wait_event.set()

    def cleanup(self):
        self._receive_thread_run = False
        self._receive_thread.join()
        self._udpsock.close()
