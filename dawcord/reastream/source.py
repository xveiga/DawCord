# -*- coding: utf-8 -*-

import discord
import socket
import time
import asyncio
import logging
from math import gcd
from .packet import ReaStreamPacket, ReaStreamAudioPacket, MAX_PACKET_LEN
from .converter import (
    s32_interleave_samples,
    s32_to_float,
    float_to_s16le,
    mono_to_stereo_16le,
    db_to_val,
    val_to_db,
    float_set_gain,
)
from .resampler import Resampler

# See read() method for details
TARGET_FRAME_SIZE = 3840
TARGET_SAMPLE_RATE = 48000

_log = logging.getLogger(__name__)


class ReaStreamAudioSource(discord.AudioSource):
    def __init__(
        self,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="default",
        timeout=2.0,
        resample_quality="HQ",
        gain=0,
    ):
        # Receive data via UDP socket
        self.reasock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to address and port
        self.reasock.bind((ipaddr, port))
        self.reasock.settimeout(timeout)
        self._resample_quality = resample_quality
        self._identifier = identifier
        self._gain = db_to_val(gain)
        self._start_time = time.time()
        self._buffer = bytearray()
        self._channel_count = 0
        self._sample_rate = 0
        self._resampler = None
        self._resample_min_buffer = 0

    def read(self):
        # Discord.py expects 20ms worth of 48kHz 16-bit (2 byte) stereo (2) PCM (0.02*48000*2*2 = 3840 bytes)
        # ReaStream may send packets of variable size depending on the DAW's buffer size configuration and latency.
        # It's therefore necessary to buffer the frames to provide a constant output to discord.py's opus encoder.
        #
        # Ideally, a custom encoder implementation with rate/speed control would help to keep latency to a minimum
        # and prevent time "acceleration" glitches when the DAW cannot keep up or ReaStream stops/resumes transmitting.

        # Buffer until target size
        while len(self._buffer) < TARGET_FRAME_SIZE:
            # Receive packet
            frames = self._receive()
            if frames:
                # Do resampling, bit-depth and channel conversion.
                frames = self._process_frames(frames, self._channel_count)
                # From here onwards it's always a 16-bit stereo signal
                self._buffer += frames

        # Return only the target number of frames
        return_frames = self._buffer[:TARGET_FRAME_SIZE]

        # The remaining frames are stored to be concatenated on the next function call
        self._buffer = self._buffer[TARGET_FRAME_SIZE:]

        return bytes(return_frames)

    def _on_format_change(self):
        if self._sample_rate != TARGET_SAMPLE_RATE:
            self._resampler = Resampler(
                self._sample_rate,
                TARGET_SAMPLE_RATE,
                self._channel_count,
                quality=self._resample_quality,
            )
            self._resample_min_buffer = gcd(self._sample_rate, TARGET_SAMPLE_RATE)
        else:
            self._resampler = None
            self._resample_min_buffer = 0

    def _process_frames(self, frames, channel_count):
        # Convert float PCM multichannel audio to stereo 16 bit little endian.
        # Also resample audio if source and Discord default sample rates differ.
        if channel_count == 1:
            # If number of channels is 1, we need to convert to stereo by doubling samples.

            # Do resampling first if needed on the single channel.
            frames = s32_to_float(frames)

            if self._resampler is not None:
                frames = self._resampler.resample(frames)

            frames = float_set_gain(frames, self._gain)

            # Do float to 16 bit conversion
            frames, clip = float_to_s16le(frames)

            # Then duplicate frames for stereo
            frames = mono_to_stereo_16le(frames)

        elif channel_count == 2:
            # For stereo signal we need to interleave samples, as ReaStream packet samples are not interleaved.
            frames = s32_interleave_samples(frames, 2)
            frames = s32_to_float(frames)

            # Resample if needed
            if self._resampler is not None:
                frames = self._resampler.resample(frames)

            frames = float_set_gain(frames, self._gain)

            # Convert float to s16le
            frames, clip = float_to_s16le(frames)
        else:
            # Number of channels > 2 is not supported, fallback to first channel only and double it.
            # The frames for the first channels are at position 0 until length divided by number of channels
            frames, clip = s32_to_float(frames[: len(frames) // channel_count])

            # Resample if needed
            if self._resampler is not None:
                frames = self._resampler.resample(frames)

            # Set gain (may help prevent clipping)
            frames = float_set_gain(frames, self._gain)

            # Float to 16 bit conversion
            frames, clip = float_to_s16le(frames)

            # Duplicate frames for stereo
            frames = mono_to_stereo_16le(frames)

        # Print a warning if the conversion had to clip the signal
        if clip:
            _log.warning(f" Signal clipping: {val_to_db(clip)} dB")

        return frames

    def _receive(self):
        try:
            data, addr = self.reasock.recvfrom(MAX_PACKET_LEN)
            packet = ReaStreamPacket.parse_packet(data)

            # Check if we have a valid packet
            if not packet:
                return None

            # Check its an audio packet, not midi
            if not isinstance(packet, ReaStreamAudioPacket):
                return None

            # Check packet identifier is the same we want to receive
            if packet.identifier != self._identifier:
                return None

            # Update sample rate and audio channel counters
            if (
                self._sample_rate != packet.sample_rate
                or self._channel_count != packet.channel_count
            ):
                _log.info(
                    f"Audio format update: {self._sample_rate}Hz {self._channel_count}ch -> {packet.sample_rate}Hz {packet.channel_count}ch"
                )
                self._sample_rate = packet.sample_rate
                self._channel_count = packet.channel_count
                self._on_format_change()

            return packet.frames

        except TimeoutError as e:
            return None

    def is_opus(self):
        return False

    def cleanup(self):
        self.reasock.close()
