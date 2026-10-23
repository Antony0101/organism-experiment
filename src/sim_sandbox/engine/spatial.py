"""A deterministic uniform-grid spatial index."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


class SpatialHash:
    def __init__(self, cell_size: float = 64.0) -> None:
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.cell_size = float(cell_size)
        self._cells: dict[tuple[int, int], set[int]] = {}
        self._positions: dict[int, tuple[float, float]] = {}
        self._entity_cells: dict[int, tuple[int, int]] = {}

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return (math.floor(x / self.cell_size), math.floor(y / self.cell_size))

    def insert(self, entity_id: int, x: float, y: float) -> None:
        if entity_id in self._positions:
            raise ValueError(f"entity {entity_id} is already indexed")
        position = (float(x), float(y))
        self._positions[entity_id] = position
        cell = self._cell(*position)
        self._entity_cells[entity_id] = cell
        self._cells.setdefault(cell, set()).add(entity_id)

    def update(self, entity_id: int, x: float, y: float) -> None:
        old = self._positions.get(entity_id)
        if old is None:
            self.insert(entity_id, x, y)
            return
        position = (float(x), float(y))
        old_cell = self._entity_cells[entity_id]
        new_cell = self._cell(*position)
        self._positions[entity_id] = position
        if old_cell == new_cell:
            return
        bucket = self._cells[old_cell]
        bucket.remove(entity_id)
        if not bucket:
            del self._cells[old_cell]
        self._entity_cells[entity_id] = new_cell
        self._cells.setdefault(new_cell, set()).add(entity_id)

    def sync(self, entities: Iterable[tuple[int, Any]]) -> None:
        positions = self._positions
        entity_cells = self._entity_cells
        cells = self._cells
        cell_size = self.cell_size
        floor = math.floor
        for entity_id, entity in entities:
            x = entity.x
            y = entity.y
            positions[entity_id] = (x, y)
            old_cell = entity_cells.get(entity_id)
            if old_cell is None:
                new_cell = (floor(x / cell_size), floor(y / cell_size))
                entity_cells[entity_id] = new_cell
                cells.setdefault(new_cell, set()).add(entity_id)
                continue
            left = old_cell[0] * cell_size
            top = old_cell[1] * cell_size
            if left <= x < left + cell_size and top <= y < top + cell_size:
                continue
            new_cell = (floor(x / cell_size), floor(y / cell_size))
            bucket = cells[old_cell]
            bucket.remove(entity_id)
            if not bucket:
                del cells[old_cell]
            entity_cells[entity_id] = new_cell
            cells.setdefault(new_cell, set()).add(entity_id)

    def remove(self, entity_id: int) -> None:
        position = self._positions.pop(entity_id, None)
        if position is None:
            return
        cell = self._entity_cells.pop(entity_id)
        bucket = self._cells[cell]
        bucket.remove(entity_id)
        if not bucket:
            del self._cells[cell]

    def query_rect(self, left: float, top: float, right: float, bottom: float) -> list[int]:
        if right < left or bottom < top:
            return []
        min_cell = self._cell(left, top)
        max_cell = self._cell(right, bottom)
        found: list[int] = []
        for cy in range(min_cell[1], max_cell[1] + 1):
            for cx in range(min_cell[0], max_cell[0] + 1):
                for entity_id in self._cells.get((cx, cy), ()):
                    x, y = self._positions[entity_id]
                    if left <= x <= right and top <= y <= bottom:
                        found.append(entity_id)
        found.sort()
        return found

    def query_radius(self, x: float, y: float, radius: float) -> list[int]:
        if radius < 0:
            raise ValueError("radius cannot be negative")
        radius_sq = radius * radius
        candidates = self.query_rect(x - radius, y - radius, x + radius, y + radius)
        return [
            entity_id
            for entity_id in candidates
            if (self._positions[entity_id][0] - x) ** 2
            + (self._positions[entity_id][1] - y) ** 2
            <= radius_sq
        ]

    def clear(self) -> None:
        self._cells.clear()
        self._positions.clear()
        self._entity_cells.clear()

    def __len__(self) -> int:
        return len(self._positions)

    @property
    def ids(self) -> Iterable[int]:
        return self._positions.keys()

