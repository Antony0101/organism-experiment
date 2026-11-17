"""Uniform spatial buckets for deterministic entity-radius searches."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite, sqrt
from typing import TYPE_CHECKING

from .ecs import Entity

if TYPE_CHECKING:
    from .components import Position


__all__ = ["SpatialHash"]


class SpatialHash:
    """Index entity bucket membership while the caller owns position values."""

    def __init__(self, cell_size=8.0):
        cell_size = float(cell_size)
        if not isfinite(cell_size) or cell_size <= 0:
            raise ValueError("cell_size must be finite and greater than zero.")
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], set[Entity]] = {}
        self._where: dict[Entity, tuple[int, int]] = {}

    def _cell(self, x, y) -> tuple[int, int]:
        return int(x // self.cell_size), int(y // self.cell_size)

    def insert(self, e: Entity, x, y) -> None:
        """Insert or relocate an entity, removing its previous membership."""
        cell = self._cell(x, y)
        if self._where.get(e) == cell:
            return
        self.remove(e)
        self._cells.setdefault(cell, set()).add(e)
        self._where[e] = cell

    def remove(self, e: Entity) -> None:
        """Discard an entity and remove its bucket if it becomes empty."""
        cell = self._where.pop(e, None)
        if cell is None:
            return
        bucket = self._cells[cell]
        bucket.discard(e)
        if not bucket:
            del self._cells[cell]

    def clear(self) -> None:
        self._cells.clear()
        self._where.clear()

    def sync(self, positions: Mapping[Entity, Position]) -> None:
        """Reconcile membership with a complete entity-to-Position mapping."""
        for entity, position in positions.items():
            self.insert(entity, position.x, position.y)
        # All supplied entities now exist in _where; extras have lost Position.
        if len(self._where) != len(positions):
            for entity in [e for e in self._where if e not in positions]:
                self.remove(entity)

    def query(self, x, y, radius, positions: Mapping[Entity, Position]) -> list[tuple[float, Entity]]:
        """Return (distance, entity) pairs inside an inclusive circular radius."""
        radius = float(radius)
        if not isfinite(radius) or radius < 0:
            raise ValueError("radius must be finite and non-negative.")
        cx0, cy0 = self._cell(x - radius, y - radius)
        cx1, cy1 = self._cell(x + radius, y + radius)
        radius_squared = radius * radius
        found = []
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                for entity in self._cells.get((cx, cy), ()):
                    position = positions.get(entity)
                    if position is None:
                        continue
                    distance_squared = (position.x - x) ** 2 + (position.y - y) ** 2
                    if distance_squared <= radius_squared:
                        found.append((sqrt(distance_squared), entity))
        found.sort()
        return found
