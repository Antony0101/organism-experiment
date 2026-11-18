"""Seeded noise, terrain painting and position sampling for procedural worlds."""

from math import isfinite
from operator import index

import numpy as np


__all__ = ["value_noise", "terrain_from_noise", "paint_blobs", "random_positions"]


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


def terrain_from_noise(world, bands, scale=40.0, octaves=4) -> np.ndarray:
    """Paint each cell with its first matching band, falling back to the last."""
    prepared = []
    for name, upper in bands:
        terrain_id = world.terrains.id_of(name)
        upper = float(upper)
        if not isfinite(upper):
            raise ValueError("Terrain band thresholds must be finite.")
        prepared.append((terrain_id, upper))
    if not prepared:
        raise ValueError("At least one terrain band is required.")

    noise = value_noise(world.rng, world.height, world.width, scale=scale, octaves=octaves)
    painted = np.full(noise.shape, prepared[-1][0], dtype=np.int16)
    remaining = np.ones(noise.shape, dtype=bool)
    for terrain_id, upper in prepared:
        selected = remaining & (noise <= upper)
        painted[selected] = terrain_id
        remaining[selected] = False
    world.terrains.ensure_layer().data[...] = painted
    world._paths_changed()
    return noise


def paint_blobs(world, terrain, count, radius=(5, 15)) -> None:
    """Overlay random ellipses, testing cell centers against each boundary."""
    terrain_id = world.terrains.id_of(terrain)
    count = index(count)
    if count < 0:
        raise ValueError("Blob count must be non-negative.")
    low, high = map(float, radius)
    if not isfinite(low) or not isfinite(high) or not 0 < low <= high:
        raise ValueError("Blob radius bounds must be finite and satisfy 0 < low <= high.")
    if count == 0 or world.width == 0 or world.height == 0:
        return

    layer = world.terrains.ensure_layer()
    ys, xs = np.ogrid[:world.height, :world.width]
    for _ in range(count):
        cx = world.rng.uniform(0, world.width)
        cy = world.rng.uniform(0, world.height)
        rx = world.rng.uniform(low, high)
        ry = world.rng.uniform(low, high)
        selected = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 <= 1
        layer.data[selected] = terrain_id
    world._paths_changed()


def random_positions(world, n, *, passable_only=True, area=None) -> list[tuple[float, float]]:
    """Sample float coordinates inside (x_min, y_min, x_max, y_max).

    Bounds are half-open and must lie inside the world. Rejection sampling
    shares one budget of 1000*max(n, 1) candidate pairs for the whole request.
    """
    n = index(n)
    if n < 0:
        raise ValueError("Position count must be non-negative.")
    if n == 0:
        return []
    x0, y0, x1, y1 = map(float, (0, 0, world.width, world.height) if area is None else area)
    if not all(isfinite(v) for v in (x0, y0, x1, y1)) or not (
        0 <= x0 < x1 <= world.width and 0 <= y0 < y1 <= world.height
    ):
        raise ValueError("Sampling area must be a finite, nonempty rectangle inside the world.")

    positions = []
    max_attempts = 1000 * max(n, 1)
    for _ in range(max_attempts):
        x = float(world.rng.uniform(x0, x1))
        y = float(world.rng.uniform(y0, y1))
        # Uniform sampling can round to an upper endpoint; do not query outside.
        if not (x0 <= x < x1 and y0 <= y < y1):
            continue
        if passable_only and not world.terrains.passable_at(x, y):
            continue
        positions.append((x, y))
        if len(positions) == n:
            return positions
    raise RuntimeError(
        f"Unable to sample {n} positions after {max_attempts} attempts (found {len(positions)})."
    )
