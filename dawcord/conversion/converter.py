# -*- coding: utf-8 -*-

import array
import struct
import math


def db_to_val(db: float):
    return pow(10, db / 20)


def val_to_db(val: float):
    return 20 * math.log10(val)


def float_set_gain(frames: list[float], gain: float):
    return [sample * gain for sample in frames]


def s16le_set_gain(frames: bytearray, gain: float):
    out_frames = bytearray()
    for sample in array.array("h", frames):
        hard_clip_sample = int(min(max(sample * gain, -32768), 32767))
        out_frames += struct.pack("<h", hard_clip_sample)
    return out_frames


def s32_interleave_samples(frame_chunk: bytearray, channels: int):
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


def s32_to_float(frames: bytearray):
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


def s32_to_s16le(frames: bytearray):
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


def s16le_to_int(frames: bytearray):
    # Converts s16le byte array (16 bit "CD quality" PCM)
    # to a python integer list
    return [sample for sample in array.array("h", frames)]


def int_to_s16le(frames):
    # Converts python 16-bit integer list
    # to s16le byte array (16 bit "CD quality" PCM)
    out_frames = bytearray()
    for sample in frames:
        out_frames += struct.pack("<h", sample)
    return bytes(out_frames)


def mono_to_stereo_16le(frames: bytearray):
    # Converts s16le mono to interleaved stereo by doubling each sample
    out_frames = bytearray()
    for sample in array.array("h", frames):
        out_frames += struct.pack("<hh", sample, sample)
    return bytes(out_frames)

def s16le_get_channels(frames: bytearray, channel_count: int, target_count: int = 2, offset: int = 0):
    # Selects the first target_channels of an interleaved s16le frame
    out_frames = bytearray()
    # Unpack frames into array
    frame_array = array.array("h", frames)

    # For each frame, which includes one sample of each channel
    for i in range(0, len(frame_array), channel_count):
            # For each channel in the wanted range
            # (from offset, target_count number of channels)
            for j in range(offset, offset + target_count):
                # Obtain wanted sample with offset
                sample = frame_array[i+j]
                # Pack result as s16le
                out_frames += struct.pack("<h", sample)
    return bytes(out_frames)

def silence_16le(count: int):
    # Returns silent 16-bit audio frames
    return bytes(struct.pack("<h", 0) * count)
