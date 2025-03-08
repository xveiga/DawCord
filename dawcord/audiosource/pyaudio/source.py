# -*- coding: utf-8 -*-

import logging
import pyaudiowpatch as pya
from threading import Lock, Event
from ..source import BaseAudioSource
from ...conversion.converter import (
    db_to_val,
    s16le_set_gain,
)

_log = logging.getLogger(__name__)


class PyAudioSource(BaseAudioSource):
    def __init__(
        self,
        device_name=None,
        timeout=2.0,
        max_buffer_frames=4,
        playback_slack=1,
        gain=0,
    ):
        self._pyaudio = pya.PyAudio()
        self._stream = None
        self._timeout = timeout
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
            rate=int(BaseAudioSource.TARGET_SAMPLE_RATE),
            frames_per_buffer=BaseAudioSource.TARGET_FRAME_SIZE,
            input=True,
            input_device_index=input_device_info["index"],
            stream_callback=self._receive,
        )

        _log.info(
            f"Listening on: ({input_device_info['index']}){input_device_info['name']}"
        )

    def _receive(self, frames, frame_count, time_info, status):
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
        if frame_count > 0:
            self._buffer_lock.acquire()
            self._buffer += s16le_set_gain(frames, self._gain)
            self._buffer_lock.release()

        # Release buffer and notify reading thread data if enough frames are stored
        if len(self._buffer) >= self._target_slack_frames:
            self._buffer_wait_event.set()

        return (frames, pya.paContinue)

    def cleanup(self):
        if self._stream is not None:
            self._stream.close()
