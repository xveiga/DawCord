# -*- coding: utf-8 -*-

import array
import asyncio
import discord
from discord.ext import commands
import json
import platform
import socket
import struct
import sys
import time

# UDP packet receive buffer size
MAX_PACKET_LEN = 2048


class ReaStreamPacket:
    @staticmethod
    def parse_packet(data: bytes):
        magic_bytes = struct.unpack("<4s", data[0:4])
        if magic_bytes[0] == b"MRSR":
            return ReaStreamAudioPacket.parse_packet(data)
        # Not implemented
        # elif magic_bytes[0] == b"mRSR":
        #     return ReaStreamMidiPacket.parse_packet(data)
        else:
            return None


class ReaStreamMidiPacket(ReaStreamPacket):
    def __init__(self, packet_len: int, identifier: str):
        super().__init__()
        self._packet_len = packet_len
        self._identifier = identifier
        raise NotImplementedError("MIDI packet reception not implemented")

    @property
    def length(self):
        return self._packet_len

    @property
    def identifier(self):
        return self._identifier

    @staticmethod
    def parse_packet(data: bytes):
        # Header format (little endian):
        # - Magic bytes 'mRSR'
        # - Packet size (unsigned int, 4 bytes)
        # - Identifier, ascii string (32 bytes)
        # - Msg type (unsigned int, 4 bytes)
        # - Size (unsigned int, 4 bytes, value 24)
        # - Sample frames since last event (unsigned int, 4 bytes)
        # - Flags (unsigned int, 4 bytes)
        # - Note length (unsigned int, 4 bytes)
        # - Note offset (int?, 4 bytes)
        # - Midi message (byte array)
        # - Zero Padding byte
        # - Pitch/detune
        # - Velocity (note off)
        # - Zero padding (2 bytes)
        raise NotImplementedError("MIDI packet reception not implemented")


class ReaStreamAudioPacket(ReaStreamPacket):
    def __init__(
        self,
        packet_len: int,
        identifier: str,
        channels: int,
        sample_rate: int,
        body_len: int,
        frames: bytes,
    ):
        super().__init__()
        self._packet_len = packet_len
        self._identifier = identifier
        self._channels = channels
        self._sample_rate = sample_rate
        self._body_len = body_len
        self._frames = frames

    @property
    def length(self):
        return self._packet_len

    @property
    def identifier(self):
        return self._identifier

    @property
    def channel_count(self):
        return self._channels

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def frame_list(self):
        return ReaStreamAudioPacket._raw_frames_to_list(
            self._frames, self._body_len, self._channels
        )

    @property
    def frames(self):
        return self._frames

    @property
    def interleaved_frames(self):
        # Not tested for channel numbers > 2
        # For interleaved order, each frame contains a sample from each channel sequentially
        # Calculate channel stride
        stride = self._body_len // self._channels
        interleaved_frames = bytearray()
        # Iterate over each float value
        for x in range(0, stride, 4):
            # For each channel,
            for ch in range(0, self._channels):
                # Jump a fixed stride to get next sample
                pos = stride * ch + x
                interleaved_frames += self._frames[pos : pos + 4]
        return interleaved_frames

    @staticmethod
    def _raw_frames_to_list(packet_body: bytes, packet_body_len: int, channels: int):
        signal = []
        for i in range(0, packet_body_len // sample_size):
            signal.append(
                struct.unpack(
                    f"<{channels}f",
                    packet_body[i * sample_size : (i + 1) * sample_size],
                )
            )
        return signal

    @staticmethod
    def parse_packet(data: bytes):
        # Header format (little endian):
        # - Magic bytes 'MRSR'
        # - Packet size (unsigned int, 4 bytes)
        # - Identifier, ascii string (32 bytes)
        # - Number of channels (unsigned byte)
        # - Sample rate (unsigned int, 4 bytes)
        # - Frames length in bytes (short, 2 bytes)
        # - Audio frames, IEEE754 32-bit float, NOT interleaved

        # Parse header
        packet_header = struct.unpack("<I32sBIH", data[4:47])
        packet_len, identifier, channels, sample_rate, body_len = packet_header
        packet_body_len = packet_len - 47

        # Check total length
        if len(data) != packet_len:
            return None

        # Check body length
        packet_body = data[47:]
        if len(packet_body) != body_len:
            return None

        # Check length is a multiple of sample size (float, 4 bytes)
        if packet_body_len % (4 * channels) != 0:
            return None

        # Parse identifier, remove unused "null" values from string
        str_identifier = identifier.decode("ascii").replace("\00", "").rstrip()

        return ReaStreamAudioPacket(
            packet_header[0], str_identifier, *packet_header[2:], packet_body
        )
