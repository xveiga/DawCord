# -*- coding: utf-8 -*-

import array
import struct


def s32_to_s16le(frames):
    # Converts s32 (32-bit float) to s16le (16 bit "CD quality" PCM)
    # with hard clipping if signal exceeds maximum values
    out_frames = bytearray()
    clip = False
    for sample in array.array("f", frames):
        reduced_sample = sample * 32767
        if reduced_sample > 32767 or reduced_sample < -32768:
            clip = True
        hard_clip_sample = int(min(max(reduced_sample, -32768), 32767))
        out_frames += struct.pack("<h", hard_clip_sample)
    return bytes(out_frames), clip


def mono_to_stereo_16le(frames):
    # Converts s16le mono to interleaved stereo by doubling each sample
    out_frames = bytearray()
    for sample in array.array("h", frames):
        out_frames += struct.pack("<hh", sample, sample)
    return bytes(out_frames)


def silence_16le(count):
    # Returns silent 16-bit audio frames
    return bytes(struct.pack("<h", 0) * count)
