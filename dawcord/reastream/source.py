# -*- coding: utf-8 -*-

import discord
import socket
import time
import asyncio
from .packet import ReaStreamPacket, ReaStreamAudioPacket, MAX_PACKET_LEN
from .converter import s32_to_s16le, mono_to_stereo_16le

TARGET_FRAME_SIZE = 3840  # See read() method for details


class ReaStreamAudioSource(discord.AudioSource):
    def __init__(
        self, ipaddr="127.0.0.1", port=58710, identifier="default", timeout=2.0
    ):
        # Receive data via UDP socket
        self.reasock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to address and port
        self.reasock.bind((ipaddr, port))
        self.reasock.settimeout(timeout)
        self._identifier = identifier
        self._start_time = time.time()
        self._buffer = bytearray()

    def read(self):
        # Discord.py expects 20ms worth of 48kHz 16-bit (2 byte) stereo (2) PCM (0.02*48000*2*2 = 3840 bytes)
        # ReaStream may send packets of variable size depending on the DAW's buffer size configuration and latency.
        # It's therefore necessary to buffer the frames to provide a constant output to discord.py's opus encoder.
        #
        # Ideally, a custom encoder implementation with rate/speed control would help to keep latency to a minimum
        # and prevent time "acceleration" glitches when the DAW cannot keep up or ReaStream stops/resumes transmitting.

        # Buffer until target size
        while len(self._buffer) < TARGET_FRAME_SIZE:
            # Note that the bit depth and channel conversions are done on the _receive() method.
            frames = self._receive()
            # From here onwards it's always a 16-bit stereo signal
            self._buffer += frames

        # Return only the target number of frames
        return_frames = self._buffer[:TARGET_FRAME_SIZE]

        # The remaining frames are stored to be concatenated on the next function call
        self._buffer = self._buffer[TARGET_FRAME_SIZE:]

        return bytes(return_frames)

    def _receive(self):
        try:
            data, addr = self.reasock.recvfrom(MAX_PACKET_LEN)
            packet = ReaStreamPacket.parse_packet(data)

            # Check if we have a valid packet
            if not packet:
                return bytes()

            # Check its an audio packet, not midi
            if not isinstance(packet, ReaStreamAudioPacket):
                return bytes()

            # Check packet identifier is the same we want to receive
            if packet.identifier != self._identifier:
                return bytes()

            # Check sample rate is 48000 Hz, as required by discord.py's opus encoder
            if packet.sample_rate != 48000:
                raise NotImplementedError(
                    "Sample rate interpolation not implemented, must always be set to 48000Hz on your DAW"
                )

            # Convert 32 bit float PCM multichannel audio to stereo 16 bit little endian.
            if packet.channel_count == 1:
                # If number of channels is 1, we need to convert to stereo by doubling samples
                frames, clip = s32_to_s16le(packet.frames)
                frames = mono_to_stereo_16le(frames)
            elif packet.channel_count == 2:
                # For stereo signal we need to interleave samples, as ReaStream packet samples are not interleaved.
                frames, clip = s32_to_s16le(packet.interleaved_frames)
            else:
                # Number of channels > 2 is not supported, fallback to first channel only and double it.
                # The frames for the first channels are at position 0 until length divided by number of channels
                frames, clip = s32_to_s16le(
                    packet.frames[: len(packet.frames) // packet.channel_count]
                )
                frames = mono_to_stereo_16le(frames)

            # Print a warning if the conversion had to clip the signal
            if clip:
                print(f"[{time.time() - self._start_time:.4f}s] Signal clipping")

            return frames
        except TimeoutError as e:
            return bytes()

    def is_opus(self):
        return False

    def cleanup(self):
        self.reasock.close()
