# -*- coding: utf-8 -*-

import struct


class VBANPacket:
    # See https://vb-audio.com/Voicemeeter/VBANProtocol_Specifications.pdf for reference
    MAX_PACKET_LEN = 1464
    HEADER_SIZE = 28

    SUB_PROTOCOL_NAMES = {
        0x00: "audio",
        0x20: "serial",
        0x40: "txt",
        0x60: "service",
        0x80: "undefined_1",
        0xA0: "undefined_2",
        0xC0: "undefined_3",
        0xE0: "user",
    }

    @staticmethod
    def decode(data: bytes):
        return VBANPacketDecoder.decode(data)


class VBANAudioPacket(VBANPacket):
    def __init__(
        self,
        sample_rate: int,
        samples_per_frame: int,
        channels: int,
        bit_resolution: tuple,
        codec: str,
        identifier: str,
        seq_counter: int,
        frames: bytes,
    ):
        super().__init__()
        self._sample_rate = sample_rate
        self._samples_per_frame = samples_per_frame
        self._channels = channels
        self._bit_resolution = bit_resolution
        self._codec = codec
        self._identifier = identifier
        self._frame_counter = seq_counter
        self._frames = frames

    SAMPLE_RATES = {
        0: 6000,
        1: 12000,
        2: 24000,
        3: 48000,
        4: 96000,
        5: 192000,
        6: 384000,
        7: 8000,
        8: 16000,
        9: 32000,
        10: 64000,
        11: 128000,
        12: 256000,
        13: 512000,
        14: 11025,
        15: 22050,
        16: 44100,
        17: 88200,
        18: 176400,
        19: 352800,
        20: 705600,
    }

    FORMATS = {
        0: ("B", "byte8"),
        1: ("h", "int16"),
        2: ("4s", "int24"),
        3: ("i", "int32"),
        4: ("f", "float32"),
        5: ("d", "float64"),
        6: ("2s", "12bits"),
        7: ("2s", "10bits"),
    }

    CODECS = {
        0x0: "PCM",
        0x1: "VB-AUDIO AOIP CODEC",
        0x2: "VB-AUDIO VOIP CODEC",
        0x3: "UNDEFINED_1",
        0x4: "UNDEFINED_2",
        0x5: "UNDEFINED_3",
        0x6: "UNDEFINED_4",
        0x7: "UNDEFINED_5",
        0x8: "UNDEFINED_6",
        0x9: "UNDEFINED_7",
        0xA: "UNDEFINED_8",
        0xB: "UNDEFINED_9",
        0xC: "UNDEFINED_10",
        0xD: "UNDEFINED_11",
        0xE: "UNDEFINED_12",
        0xF: "USER",
    }

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def samples_per_frame(self):
        return self._samples_per_frame

    @property
    def channels(self):
        return self._channels

    @property
    def bit_resolution_struct_type(self):
        return self._bit_resolution[0]

    @property
    def bit_resolution(self):
        return self._bit_resolution[1]

    @property
    def codec(self):
        return self._codec

    @property
    def identifier(self):
        return self._identifier

    @property
    def seq_counter(self):
        return self._frame_counter

    @property
    def frames(self):
        return self._frames

    @staticmethod
    def decode(data: bytes):
        # Parse header
        # Sub protocol bits are skipped as they are checked on VBANPacket decoding
        packet_header = struct.unpack(
            "<BBBB16sI", data[4 : VBANAudioPacket.HEADER_SIZE]
        )
        format_sr, format_nbs, format_nbc, format_bit, stream_name, seq_counter = (
            packet_header
        )

        # Sample Rate is given by an index (0 to 31) given in the 5 first bits. Bits 6 to 7 must be ZERO.
        sample_rate = VBANAudioPacket.SAMPLE_RATES.get(format_sr & 0x1F, None)
        if sample_rate is None:
            raise ValueError("Unknown sample rate")

        bit_resolution = VBANAudioPacket.FORMATS.get(format_bit & 0x7, None)
        if bit_resolution is None:
            raise ValueError(f"Unknown sample bit resolution: {format_bit & 0x7:#x}")

        codec = VBANAudioPacket.CODECS.get(format_bit >> 3 & 0xF)
        if codec is None:
            raise ValueError(f"Unknown codec id: {format_bit:#x}")

        packet = VBANAudioPacket(
            sample_rate=sample_rate,
            samples_per_frame=format_nbs,
            channels=format_nbc + 1,
            bit_resolution=bit_resolution,
            codec=codec,
            identifier=stream_name.decode("ascii").replace("\00", "").rstrip(),
            seq_counter=seq_counter,
            frames=data[VBANAudioPacket.HEADER_SIZE :],
        )

        return packet


class VBANSerialPacket:
    @staticmethod
    def decode(data: bytes):
        raise NotImplementedError("Serial packet decoding not implemented")


class VBANTxtPacket:
    @staticmethod
    def decode(data: bytes):
        raise NotImplementedError("Text packet decoding not implemented")


class VBANServicePacket:
    @staticmethod
    def decode(data: bytes):
        raise NotImplementedError("Service packet decoding not implemented")


class VBANPacketDecoder:
    # UDP packet receive buffer size
    MAX_PACKET_LEN = 2048

    SUB_PROTOCOL_CLASSES = {
        0x00: VBANAudioPacket,
        0x20: VBANSerialPacket,
        0x40: VBANTxtPacket,
        0x60: VBANServicePacket,
    }

    @staticmethod
    def decode(data: bytes):
        # Check header presence
        if len(data) < 28:
            raise ValueError("Header not found")

        # Check packet magic number
        magic_bytes = struct.unpack("<4s", data[0:4])
        if magic_bytes[0] != b"VBAN":
            raise ValueError("Magic number not found in VBAN packet")

        # Parse sub protocol format specifier in header
        format_sr = struct.unpack("<B", data[4:5])

        # Bits 5 to 7 of format_sr field are used as sub protocol selector
        sub_id = (format_sr[0] >> 5) & 0x7
        sub_protocol = VBANPacketDecoder.SUB_PROTOCOL_CLASSES.get(sub_id, None)
        if sub_protocol is None:
            sub_protocol_name = VBANPacket.SUB_PROTOCOL_NAMES.get(sub_id, None)
            raise ValueError(
                "Unsupported sub format protocol ID: " + "unknown"
                if sub_protocol_name is None
                else sub_protocol_name
            )

        return sub_protocol.decode(data)
