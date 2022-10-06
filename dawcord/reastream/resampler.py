# -*- coding: utf-8 -*-

import soxr
import numpy as np


class Resampler:
    def __init__(self, in_rate, out_rate, channels, quality="HQ"):
        self._resampler = soxr.ResampleStream(
            in_rate, out_rate, channels, dtype="float32", quality=quality
        )
        self._resample_func = (
            self._resample_stereo if (channels == 2) else self._resample
        )

    def resample(self, frames):
        return self._resample_func(frames)

    def _resample(self, frames):
        src = np.asarray(frames).astype(np.float32)
        return self._resampler.resample_chunk(src, last=False)

    def _resample_stereo(self, frames):
        src = np.asarray(frames).astype(np.float32)
        src = np.vstack((src[::2], src[1::2])).T
        res = self._resampler.resample_chunk(src, last=False)
        return np.ravel(res, order="C").tolist()
