"""Seeded numeric building blocks for procedural world generation."""

from math import isfinite
from operator import index

import numpy as np


__all__ = ["value_noise"]


def value_noise(rng, height, width, scale=32.0, octaves=4, persistence=0.5) -> np.ndarray:
    """Blend bilinear random lattices and normalize the result into [0, 1].

    Scale is the first lattice's spacing in cells, with a minimum of one.
    Each octave halves that spacing and multiplies amplitude by persistence.
    Empty outputs consume no randomness; constant outputs normalize to zero.
    """
    height, width, octaves = index(height), index(width), index(octaves)
    if height < 0 or width < 0:
        raise ValueError("height and width must be non-negative integers.")
    if octaves < 1:
        raise ValueError("octaves must be a positive integer.")
    scale, persistence = float(scale), float(persistence)
    if not isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and greater than zero.")
    if not isfinite(persistence) or persistence < 0:
        raise ValueError("persistence must be finite and non-negative.")

    noise = np.zeros((height, width), dtype=float)
    if noise.size == 0:
        return noise

    spacing, amplitude = max(1.0, scale), 1.0
    for _ in range(octaves):
        xs = np.arange(width, dtype=float) / spacing
        ys = np.arange(height, dtype=float) / spacing
        x0, y0 = xs.astype(np.intp), ys.astype(np.intp)
        tx, ty = xs - x0, (ys - y0)[:, None]
        grid = rng.random((int(y0[-1]) + 2, int(x0[-1]) + 2))
        top = grid[y0[:, None], x0] * (1 - tx) + grid[y0[:, None], x0 + 1] * tx
        bottom = grid[y0[:, None] + 1, x0] * (1 - tx) + grid[y0[:, None] + 1, x0 + 1] * tx
        interpolated = top * (1 - ty) + bottom * ty
        if persistence > 1:
            # Scale the accumulated sum instead of growing weights to infinity.
            # Final min/max normalization cancels this common positive factor.
            noise /= persistence
            noise += interpolated
        else:
            noise += amplitude * interpolated
            amplitude *= persistence
        spacing = max(1.0, spacing * 0.5)

    noise -= noise.min()
    span = noise.max()
    if span > 0:
        noise /= span
    return noise
