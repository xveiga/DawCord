# -*- coding: utf-8 -*-

import discord
import logging
import pyaudiowpatch as pya
from threading import Lock, Event
from math import floor
from ...conversion.converter import (
    silence_16le,
    db_to_val,
)

# See read() method for details
TARGET_SAMPLE_RATE = 48000
# Number of samples = Time delay * sample rate * 2 (stereo) * 2 bytes (16-bit PCM)
TARGET_FRAME_SIZE = floor(discord.player.AudioPlayer.DELAY * TARGET_SAMPLE_RATE * 2 * 2)

_log = logging.getLogger(__name__)


class PyAudioSource(discord.AudioSource):

    def __init__(
        self,
        device_name=None,
        timeout=2.0,
        max_buffer_frames=8,
        playback_slack=2,
        gain=0,
    ):
        self._pyaudio = pya.PyAudio()
        self._stream = None
        self._timeout = timeout
        self._gain = db_to_val(gain)
        self._max_buffer_frames = int(max_buffer_frames)
        self._playback_slack = int(playback_slack)
        self._target_slack_frames = int(TARGET_FRAME_SIZE * self._playback_slack)
        self._buffer = bytearray()
        self._buffer_lock = Lock()
        self._buffer_wait_event = Event()
        self._buffer_waiting = True
        self._buffer_empty = False
        self._setup_device(device_name)

    def _setup_device(self, device_name):
        try:
            self._pyaudio.get_host_api_info_by_type(pya.paWASAPI)
        except OSError as e:
            _log.error("Looks like WASAPI is not available on the system. Exiting...")
            raise e

        input_device_info = None
        device_info_names = []
        for i in range(self._pyaudio.get_device_count()):
            device_info = self._pyaudio.get_device_info_by_index(i)
            device_info_name = device_info["name"]
            device_info_names.append(device_info_name)
            if device_info_name == device_name:
                input_device_info = device_info

        _log.info(f"Available audio devices: {device_info_names}")

        if input_device_info is None:
            raise Exception(f'Could not find audio device "{device_name}"')

        self._stream = self._pyaudio.open(
            format=pya.paInt16,
            channels=2,
            rate=int(TARGET_SAMPLE_RATE),
            frames_per_buffer=TARGET_FRAME_SIZE,
            input=True,
            input_device_index=input_device_info["index"],
            stream_callback=self._receive,
        )

        _log.info(
            f"Listening on: ({input_device_info['index']}){input_device_info['name']}"
        )

    def _receive(self, frames, frame_count, time_info, status):
        # Adquire buffer
        self._buffer_lock.acquire()

        # If number of frames exceeds limit, clear buffer to refill it with fresh frames.
        # This is not ideal as it introduces clicking, but is camouflaged well enough
        # with discord's opus encoding and keeps latency in check
        if len(self._buffer) > self._max_buffer_frames * TARGET_FRAME_SIZE:
            self._buffer.clear()

        # Append frames to buffer
        if frame_count > 0:
            self._buffer += frames

        # Release buffer and notify reading thread data if enough frames are stored
        self._buffer_lock.release()
        if len(self._buffer) >= self._target_slack_frames:
            self._buffer_waiting = False
            self._buffer_wait_event.set()

        return (frames, pya.paContinue)

    def read(self):
        # Discord.py expects 20ms worth of 48kHz 16-bit (2 byte) stereo (2) PCM (0.02*48000*2*2 = 3840 bytes)
        # ReaStream may send packets of variable size depending on the DAW's buffer size configuration and latency.
        # It's therefore necessary to buffer the frames to provide a constant output to discord.py's opus encoder.
        #
        # Ideally, a custom encoder implementation with rate/speed control would help to keep latency to a minimum
        # and prevent time "acceleration" glitches when the DAW cannot keep up or ReaStream stops/resumes transmitting.

        # If not enough frames are available
        if len(self._buffer) < TARGET_FRAME_SIZE or self._buffer_waiting:
            if not self._buffer_waiting:
                _log.info(
                    f"Buffer wait ({len(self._buffer)}/{self._target_slack_frames})"
                )
            # else:
            #     _log.info(
            #         f"Buffer underrun ({len(self._buffer)}/{TARGET_FRAME_SIZE})"
            #     )
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
        # print(f"Play position: {len(self._buffer)/len(return_frames):.2f}")
        return bytes(return_frames)

    def is_opus(self):
        return False

    def cleanup(self):
        if self._stream is not None:
            self._stream.close()
