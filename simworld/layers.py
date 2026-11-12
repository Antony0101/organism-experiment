"""Typed grid storage and metadata for world layers and fields."""

from __future__ import annotations

from math import exp, floor, isfinite
from operator import index

import numpy as np

from .errors import OutOfBoundsError, SimWorldError, UnknownLayerError


__all__ = ["Layer", "LayerStore"]

_M = object()


class Layer:
    """Allocate a grid indexed by row, column and optional cell dimensions."""

    def __init__(
        self, name, width, height, dtype=float, default=0, *, shape=(),
        min=None, max=None, decay=0.0, diffusion=0.0, color=None,
        tooltip="", kind="layer", props=None,
    ):
        self.name = name
        self.width = width
        self.height = height
        self.dtype = np.dtype(dtype)
        self.default = default
        self.shape = tuple(shape)
        self.min = min
        self.max = max
        self.decay_rate = decay
        self.diffusion_rate = diffusion
        self.color = None if color is None else tuple(color)
        self.tooltip = tooltip
        self.kind = kind
        self.props = {} if props is None else dict(props)
        self.data = np.full((height, width) + self.shape, default, dtype=self.dtype)

    @property
    def is_float(self) -> bool:
        """Whether this layer stores real floating-point values."""
        return np.issubdtype(self.dtype, np.floating)

    def in_bounds(self, x, y) -> bool:
        """Whether a world position lies within this grid's half-open bounds."""
        return bool(0 <= x < self.width and 0 <= y < self.height)

    @staticmethod
    def _cell(x, y=None) -> tuple[int, int]:
        """Resolve separate coordinates, a pair or a position into cell indices."""
        if y is None:
            if hasattr(x, "x") and hasattr(x, "y"):
                x, y = x.x, x.y
            else:
                x, y = x
        return floor(x), floor(y)

    def _check_bounds(self, x, y) -> None:
        if not self.in_bounds(x, y):
            raise OutOfBoundsError(
                f"Layer {self.name!r} cell ({x}, {y}) is outside bounds "
                f"(width={self.width}, height={self.height})."
            )

    def get(self, x, y=None, *, default=_M):
        """Read the cell containing (x, y), or an explicit fallback outside it."""
        x, y = self._cell(x, y)
        if default is not _M and not self.in_bounds(x, y):
            return default
        self._check_bounds(x, y)
        return self.data[y, x] if self.shape else self.data.item(y, x)

    def set(self, x, y, value=_M) -> None:
        """Write a cell using world coordinates; clamp only bounded float layers."""
        if value is _M:
            value = y
            x, y = self._cell(x)
        else:
            x, y = self._cell(x, y)
        self._check_bounds(x, y)
        if self.is_float and (self.min is not None or self.max is not None):
            value = np.clip(value, self.min, self.max)
        self.data[y, x] = value

    def _arithmetic_cell(self, x, y, amount):
        """Normalize arithmetic arguments and reject non-scalar cells before mutation."""
        if amount is _M:
            amount = y
            x, y = self._cell(x)
        else:
            x, y = self._cell(x, y)
        self._check_bounds(x, y)
        if self.shape:
            raise SimWorldError(
                f"Cell arithmetic requires a scalar layer; {self.name!r} has shape {self.shape}."
            )
        return x, y, amount

    def add(self, x, y, amount=_M) -> float:
        """Add to a scalar cell and return its signed change after storage/clamping."""
        x, y, amount = self._arithmetic_cell(x, y, amount)
        before = self.data.item(y, x)
        self.set(x, y, before + amount)
        return float(self.data.item(y, x) - before)

    def take(self, x, y, amount=_M) -> float:
        """Remove up to amount above min (or zero), returning the actual removal."""
        x, y, amount = self._arithmetic_cell(x, y, amount)
        if amount < 0:
            raise SimWorldError(f"Cannot take a negative amount from layer {self.name!r}.")
        before = self.data.item(y, x)
        minimum = self.min if self.min is not None else 0
        removed = min(amount, max(0, before - minimum))
        if not self.is_float:
            # Discrete cells cannot remove fractions without exceeding the request.
            removed = floor(removed)
        self.data[y, x] = before - removed
        return float(before - self.data.item(y, x))

    def fill(self, value) -> None:
        """Fill all cells in place, then enforce any float-layer limits."""
        self.data[...] = value
        self.clamp()

    def clamp(self) -> None:
        """Clamp float-layer data in place when at least one bound is configured."""
        if self.is_float and (self.min is not None or self.max is not None):
            np.clip(self.data, self.min, self.max, out=self.data)

    def diffuse(self, rate, mask=None) -> None:
        """Exchange mass between adjacent float cells without crossing grid/mask edges."""
        if not self.is_float:
            raise SimWorldError(f"Diffusion requires a float layer; {self.name!r} stores {self.dtype}.")
        rate = float(rate)
        if not 0 <= rate <= 0.25:
            raise SimWorldError("Diffusion rate must be in [0, 0.25].")
        if mask is not None:
            mask = np.asarray(mask, dtype=bool)
            if mask.shape != (self.height, self.width):
                raise SimWorldError(
                    f"Diffusion mask must have shape {(self.height, self.width)}, got {mask.shape}."
                )
            mask = mask.reshape(mask.shape + (1,) * len(self.shape))
        if rate == 0:
            return
        a = self.data
        fx = (a[:, 1:] - a[:, :-1]) * rate
        fy = (a[1:, :] - a[:-1, :]) * rate
        if mask is not None:
            fx *= mask[:, 1:] & mask[:, :-1]
            fy *= mask[1:, :] & mask[:-1, :]
        a[:, :-1] += fx
        a[:, 1:] -= fx
        a[:-1, :] += fy
        a[1:, :] -= fy

    def decay(self, rate=None, dt=1.0) -> None:
        """Apply exponential decay to float data using the supplied or stored rate."""
        if not self.is_float:
            raise SimWorldError(f"Decay requires a float layer; {self.name!r} stores {self.dtype}.")
        rate = float(self.decay_rate if rate is None else rate)
        dt = float(dt)
        if not isfinite(rate) or rate < 0 or not isfinite(dt) or dt < 0:
            raise SimWorldError("Decay rate and dt must be finite and non-negative.")
        self.data *= exp(-rate * dt)

    def total(self) -> float:
        """Return the sum over every grid and cell dimension."""
        return float(self.data.sum())

    def mean(self) -> float:
        """Return the mean over every grid and cell dimension."""
        return float(self.data.mean())

    def sample(self, x, y):
        """Bilinearly sample cell-centered values, extending the nearest grid edge."""
        if self.width == 0 or self.height == 0:
            raise OutOfBoundsError(f"Cannot sample empty layer {self.name!r}.")
        x = min(max(float(x) - 0.5, 0.0), self.width - 1)
        y = min(max(float(y) - 0.5, 0.0), self.height - 1)
        x0, y0 = floor(x), floor(y)
        x1, y1 = min(x0 + 1, self.width - 1), min(y0 + 1, self.height - 1)
        tx, ty = x - x0, y - y0
        top = self.data[y0, x0] * (1 - tx) + self.data[y0, x1] * tx
        bottom = self.data[y1, x0] * (1 - tx) + self.data[y1, x1] * tx
        value = top * (1 - ty) + bottom * ty
        return value if self.shape else float(value)

    def gradient(self, x, y):
        """Return centered differences of samples one world unit to either side."""
        x, y = float(x), float(y)
        return (
            (self.sample(x + 1, y) - self.sample(x - 1, y)) / 2,
            (self.sample(x, y + 1) - self.sample(x, y - 1)) / 2,
        )

    def window(self, x, y, radius=1):
        """Return a clipped square cell view and its top-left world cell indices."""
        radius = index(radius)
        if radius < 0:
            raise SimWorldError("Window radius must be non-negative.")
        x, y = self._cell(x, y)
        x0 = min(self.width, max(0, x - radius))
        y0 = min(self.height, max(0, y - radius))
        x1 = min(self.width, max(0, x + radius + 1))
        y1 = min(self.height, max(0, y + radius + 1))
        return self.data[y0:y1, x0:x1], x0, y0

    def neighbours(self, x, y, diagonal=True):
        """Yield in-bounds (x, y, value) triples in row order, excluding the center."""
        x, y = self._cell(x, y)
        for ny in range(y - 1, y + 2):
            for nx in range(x - 1, x + 2):
                if nx == x and ny == y:
                    continue
                if not diagonal and nx != x and ny != y:
                    continue
                if self.in_bounds(nx, ny):
                    yield nx, ny, self.get(nx, ny)

    def __getitem__(self, key):
        """Use raw NumPy indexing in [y, x] order, without coordinate conversion."""
        return self.data[key]

    def __setitem__(self, key, value) -> None:
        """Assign with NumPy indexing, bypassing layer range limits."""
        self.data[key] = value


class LayerStore(dict[str, Layer]):
    """Keep layers in insertion order and explain missing named lookups."""

    def __missing__(self, key):
        raise UnknownLayerError(key, self.keys())
