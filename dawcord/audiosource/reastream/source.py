# -*- coding: utf-8 -*-

import discord
import socket
import logging
import threading
from threading import Lock, Event
from math import gcd, floor
from .packet import ReaStreamPacket, ReaStreamAudioPacket, MAX_PACKET_LEN
from ...conversion.converter import (
    s32_interleave_samples,
    s32_to_float,
    float_to_s16le,
    mono_to_stereo_16le,
    silence_16le,
    db_to_val,
    val_to_db,
    float_set_gain,
)
from ...conversion.resampler import Resampler

# See read() method for details
TARGET_SAMPLE_RATE = 48000
# Number of samples = Time delay * sample rate * 2 (stereo) * 2 bytes (16-bit PCM)
TARGET_FRAME_SIZE = floor(discord.player.AudioPlayer.DELAY * TARGET_SAMPLE_RATE * 2 * 2)

_log = logging.getLogger(__name__)


class ReaStreamAudioSource(discord.AudioSource):
    def __init__(
        self,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="default",
        timeout=2.0,
        resample_quality="HQ",
        max_buffer_frames=8,
        playback_slack=2,
        gain=0,
    ):
        # Receive data via UDP socket
        self._reasock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to address and port
        self._reasock.bind((ipaddr, port))
        self._reasock.settimeout(timeout)
        self._timeout = timeout
        self._identifier = identifier
        self._resample_quality = resample_quality
        self._gain = db_to_val(gain)
        self._max_buffer_frames = int(max_buffer_frames)
        self._playback_slack = int(playback_slack)
        self._target_slack_frames = int(TARGET_FRAME_SIZE * self._playback_slack)
        self._buffer = bytearray()
        self._buffer_lock = Lock()
        self._buffer_wait_event = Event()
        self._buffer_empty = False
        self._channel_count = 0
        self._sample_rate = 0
        self._resampler = None
        self._resample_min_buffer = 0
        self._receive_thread_run = True
        self._receive_thread = threading.Thread(target=self._receive_thread_func)
        self._receive_thread.start()

    def _on_format_change(self, sample_rate, channel_count):
        _log.info(
            f"Audio format update: {self._sample_rate}Hz {self._channel_count}ch -> {sample_rate}Hz {channel_count}ch"
        )
        self._sample_rate = sample_rate
        self._channel_count = channel_count

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

    def _receive(self):
        try:
            data, addr = self._reasock.recvfrom(MAX_PACKET_LEN)
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
                self._on_format_change(packet.sample_rate, packet.channel_count)

            return packet.frames

        except TimeoutError as e:
            return None

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
            _log.warning(f" Signal clipping! Peak: {val_to_db(clip):.3f} dB")

        return frames

    def _receive_thread_func(self):
        while self._receive_thread_run:
            # Adquire buffer
            self._buffer_lock.acquire()
            # If number of frames exceeds limit, clear buffer to refill it with fresh frames.
            # This is not ideal as it introduces clicking, but is camouflaged well enough
            # with discord's opus encoding and keeps latency in check
            max_size = self._max_buffer_frames * TARGET_FRAME_SIZE
            if len(self._buffer) > max_size:
                _log.info(f"Buffer overrun ({len(self._buffer)}/{max_size}), clearing")
                self._buffer_lock.acquire()
                self._buffer.clear()
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

    def read(self):
        # Discord.py expects 20ms worth of 48kHz 16-bit (2 byte) stereo (2) PCM (0.02*48000*2*2 = 3840 bytes)
        # ReaStream may send packets of variable size depending on the DAW's buffer size configuration and latency.
        # It's therefore necessary to buffer the frames to provide a constant output to discord.py's opus encoder.
        #
        # Ideally, a custom encoder implementation with rate/speed control would help to keep latency to a minimum
        # and prevent time "acceleration" glitches when the DAW cannot keep up or ReaStream stops/resumes transmitting.

        # If not enough frames are available
        if len(self._buffer) < TARGET_FRAME_SIZE:
            # Wait for buffer to fill up again
            if not self._buffer_wait_event.wait(timeout=self._timeout):
                # If timeout exceeded, insert silence
                if not self._buffer_empty:
                    _log.info(
                        f"Buffer empty ({len(self._buffer)}/{TARGET_FRAME_SIZE}), inserting silence"
                    )
                    self._buffer_empty = True
                # Clear buffer to prevent clicks by concatenating old data when the stream is resumed
                self._buffer = bytearray()
                return bytes(silence_16le(TARGET_FRAME_SIZE >> 1))

        # When enough frames are available, reset buffer empty message flag and return audio frames
        self._buffer_empty = False
        self._buffer_lock.acquire()
        # Return only the target number of frames
        return_frames = self._buffer[:TARGET_FRAME_SIZE]
        # The remaining frames are stored to be concatenated on the next function call
        self._buffer = self._buffer[TARGET_FRAME_SIZE:]
        self._buffer_lock.release()

        # Reset buffer wait flag
        self._buffer_wait_event.clear()
        # _log.info(f"Play position: {len(self._buffer)/TARGET_FRAME_SIZE:.2f}")
        return bytes(return_frames)

    def is_opus(self):
        return False

    def cleanup(self):
        self._receive_thread_run = False
        self._receive_thread.join()
        self._reasock.close()
