# -*- coding: utf-8 -*-

import soxr
import numpy as np
from enum import Enum


class Resampler:
    class Format(Enum):
        FLOAT32 = 0
        INT16 = 1

    def __init__(
        self,
        in_rate: int,
        out_rate: int,
        channels: int,
        quality: str = "HQ",
        format: Format = Format.FLOAT32,
    ):
        self._format = format
        if format == Resampler.Format.FLOAT32:
            dtype = "float32"
        elif format == Resampler.Format.INT16:
            dtype = "int16"

        if channels >= 2:
            soxr_channels = 2
            self._resample_func = self._resample_stereo
        else:
            soxr_channels = 1
            self._resample_func = self._resample

        self._resampler = soxr.ResampleStream(
            in_rate, out_rate, soxr_channels, dtype=dtype, quality=quality
        )

    def resample(self, frames):
        return self._resample_func(frames, self._format)

    def _resample(self, frames, format):
        if format == Resampler.Format.FLOAT32:
            dtype = np.float32
        elif format == Resampler.Format.INT16:
            dtype = np.int16

        src = np.asarray(frames).astype(dtype)
        return self._resampler.resample_chunk(src, last=False)

    def _resample_stereo(self, frames, format):
        if format == Resampler.Format.FLOAT32:
            dtype = np.float32
        elif format == Resampler.Format.INT16:
            dtype = np.int16

        src = np.asarray(frames).astype(dtype)
        src = np.vstack((src[::2], src[1::2])).T
        res = self._resampler.resample_chunk(src, last=False)
        return np.ravel(res, order="C").tolist()
