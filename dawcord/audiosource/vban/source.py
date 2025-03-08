# -*- coding: utf-8 -*-

import logging
from .packet import VBANPacket, VBANAudioPacket
from ..source import UDPBaseAudioSource
from ...conversion.resampler import Resampler
from ...conversion.converter import (
    s16le_set_gain,
    s16le_to_int,
    int_to_s16le,
    mono_to_stereo_16le,
    s16le_get_channels,
)

_log = logging.getLogger(__name__)


class VBANAudioSource(UDPBaseAudioSource):
    def __init__(
        self,
        ipaddr="127.0.0.1",
        port=58710,
        identifier="Stream1",
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
        self._format_warning_shown = False
        self._codec_warning_shown = False

    def _receive(self):
        try:
            data, addr = self._udpsock.recvfrom(VBANPacket.MAX_PACKET_LEN)

            # Attempt to decode packet
            try:
                packet = VBANPacket.decode(data)
            except NotImplementedError as e:
                _log.info(f"Received unsupported packet from {addr[0]}:{addr[1]}: {e}")
                return None
            except ValueError as e:
                _log.error(f"Error decoding VBAN packet from {addr[0]}:{addr[1]}: {e}")
                return None

            # Check its an audio packet
            if not isinstance(packet, VBANAudioPacket):
                return None

            # Check packet identifier is the same we want to receive
            if packet.identifier != self._identifier:
                # _log.warning(f"Receiving packet with wrong identifier")
                return None

            # Check format is supported
            if packet.bit_resolution != "int16":
                if not self._format_warning_shown:
                    _log.error(f"Unsupported sample format: {packet.bit_resolution}")
                    self._format_warning_shown = True
                return None
            else:
                self._format_warning_shown = False

            # Check codec is supported
            if packet.codec != "PCM":
                if not self._codec_warning_shown:
                    _log.error(f"Unsupported codec: {packet.codec}")
                    self._codec_warning_shown = True
                return None
            else:
                self._codec_warning_shown = False

            # Update sample rate and audio channel counters
            if (
                self._sample_rate != packet.sample_rate
                or self._channel_count != packet.channels
            ):
                self._on_format_change(
                    packet.sample_rate, packet.channels, Resampler.Format.INT16
                )

            return packet.frames

        except TimeoutError as e:
            return None

    def _process_frames(self, frames, channel_count):
        # Convert to 2 channel audio if another number of channels is received
        if channel_count == 1:
            # Resample if needed
            if self._resampler is not None:
                frames = int_to_s16le(self._resampler.resample(s16le_to_int(frames)))

            # Mono to stereo
            frames = mono_to_stereo_16le(frames)

            # Set gain
            s16le_set_gain(frames, self._gain)

            return frames
        elif channel_count == 2:
            # Resample if needed
            if self._resampler is not None:
                frames = int_to_s16le(self._resampler.resample(s16le_to_int(frames)))

            # Set gain
            s16le_set_gain(frames, self._gain)

            return frames
        else:
            # Number of channels > 2 is not supported, fallback to first 2 channels
            # Multichannel to first two channels
            frames = s16le_get_channels(frames, channel_count)

            # Resample if needed
            if self._resampler is not None:
                frames = int_to_s16le(self._resampler.resample(s16le_to_int(frames)))

            # Set gain
            s16le_set_gain(frames, self._gain)

            return frames
