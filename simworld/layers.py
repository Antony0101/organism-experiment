"""Typed grid storage and metadata for world layers and fields."""

from __future__ import annotations

from math import floor

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

    def total(self) -> float:
        """Return the sum over every grid and cell dimension."""
        return float(self.data.sum())

    def mean(self) -> float:
        """Return the mean over every grid and cell dimension."""
        return float(self.data.mean())

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
