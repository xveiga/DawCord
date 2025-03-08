# -*- coding: utf-8 -*-

import logging
from .packet import ReaStreamPacket, ReaStreamAudioPacket, MAX_PACKET_LEN
from ..source import UDPBaseAudioSource
from ...conversion.resampler import Resampler
from ...conversion.converter import (
    s32_interleave_samples,
    s32_to_float,
    float_to_s16le,
    mono_to_stereo_16le,
    val_to_db,
    float_set_gain,
)

_log = logging.getLogger(__name__)


class ReaStreamAudioSource(UDPBaseAudioSource):
    def __init__(
        self,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="default",
        timeout=2.0,
        resample_quality="VHQ",
        max_buffer_frames=4,
        playback_slack=1,
        gain=0,
    ):
        super().__init__(
            ipaddr=ipaddr,
            port=port,
            identifier=identifier,
            timeout=timeout,
            resample_quality=resample_quality,
            max_buffer_frames=max_buffer_frames,
            playback_slack=playback_slack,
            gain=gain,
        )

    def _receive(self):
        try:
            data, addr = self._udpsock.recvfrom(MAX_PACKET_LEN)
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
                self._on_format_change(
                    packet.sample_rate, packet.channels, Resampler.Format.INT16
                )

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
