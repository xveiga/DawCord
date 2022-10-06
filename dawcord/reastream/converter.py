# -*- coding: utf-8 -*-

import array
import struct
import math


def db_to_val(db):
    return pow(10, db / 20)


def val_to_db(val):
    return 20 * math.log10(val)


def float_set_gain(frames, gain):
    return [sample * gain for sample in frames]


def s32_interleave_samples(frame_chunk, channels):
    # Not tested for channel numbers > 2
    # For interleaved order, each frame contains a sample from each channel sequentially
    stride = len(frame_chunk) // channels
    interleaved_frames = bytearray()
    # Iterate over each float value
    for x in range(0, stride, 4):
        # For each channel,
        for ch in range(0, channels):
            # Jump a fixed stride to get next sample
            pos = stride * ch + x
            interleaved_frames += frame_chunk[pos : pos + 4]
    return interleaved_frames


def s32_to_float(frames):
    return [sample for sample in array.array("f", frames)]


def float_to_s16le(frames):
    # Converts python float to s16le (16 bit "CD quality" PCM)
    # with hard clipping if signal exceeds maximum values
    out_frames = bytearray()
    # clip = False
    clip = 0
    for sample in frames:
        reduced_sample = sample * 32767
        if reduced_sample > 32767 or reduced_sample < -32768:
            # clip = True
            clip = max(clip, sample)
        hard_clip_sample = int(min(max(reduced_sample, -32768), 32767))
        out_frames += struct.pack("<h", hard_clip_sample)
    return bytes(out_frames), clip


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
