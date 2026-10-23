"""Deterministic procedural tile terrain used by the bundled worlds."""

from __future__ import annotations

import math
import random
from array import array
from enum import IntEnum


class TerrainType(IntEnum):
    WATER = 0
    SAND = 1
    GRASS = 2
    FOREST = 3
    ROCK = 4


MOVEMENT_COST: dict[TerrainType, float] = {
    TerrainType.WATER: math.inf,
    TerrainType.SAND: 1.35,
    TerrainType.GRASS: 1.0,
    TerrainType.FOREST: 1.65,
    TerrainType.ROCK: math.inf,
}
_MOVEMENT_COST_BY_VALUE = tuple(MOVEMENT_COST[terrain] for terrain in TerrainType)


class TerrainMap:
    """A bounded tile map with cached elevation and moisture layers."""

    def __init__(
        self,
        seed: int,
        width: int = 256,
        height: int = 256,
        tile_size: int = 16,
    ) -> None:
        if width <= 0 or height <= 0 or tile_size <= 0:
            raise ValueError("terrain dimensions and tile size must be positive")
        self.seed = int(seed)
        self.width = int(width)
        self.height = int(height)
        self.tile_size = int(tile_size)
        self.pixel_width = self.width * self.tile_size
        self.pixel_height = self.height * self.tile_size
        self.elevation = array("f")
        self.moisture = array("f")
        self.tiles = bytearray(width * height)
        self._passable_indices: list[int] = []
        self._generate()

    @staticmethod
    def _fade(value: float) -> float:
        return value * value * (3.0 - 2.0 * value)

    @staticmethod
    def _hash_value(seed: int, x: int, y: int, layer: int) -> float:
        value = (
            (seed & 0xFFFFFFFF)
            ^ ((x * 0x9E3779B1) & 0xFFFFFFFF)
            ^ ((y * 0x85EBCA77) & 0xFFFFFFFF)
            ^ ((layer * 0xC2B2AE3D) & 0xFFFFFFFF)
        )
        value ^= value >> 16
        value = (value * 0x7FEB352D) & 0xFFFFFFFF
        value ^= value >> 15
        value = (value * 0x846CA68B) & 0xFFFFFFFF
        value ^= value >> 16
        return value / 0xFFFFFFFF

    def _value_noise(self, x: int, y: int, scale: int, layer: int) -> float:
        x0 = x // scale
        y0 = y // scale
        tx = self._fade((x % scale) / scale)
        ty = self._fade((y % scale) / scale)
        a = self._hash_value(self.seed, x0, y0, layer)
        b = self._hash_value(self.seed, x0 + 1, y0, layer)
        c = self._hash_value(self.seed, x0, y0 + 1, layer)
        d = self._hash_value(self.seed, x0 + 1, y0 + 1, layer)
        top = a + (b - a) * tx
        bottom = c + (d - c) * tx
        return top + (bottom - top) * ty

    def _fractal_noise(self, x: int, y: int, layer_offset: int) -> float:
        total = 0.0
        weight_total = 0.0
        for octave, (scale, weight) in enumerate(
            ((64, 0.48), (32, 0.28), (16, 0.16), (8, 0.08))
        ):
            total += self._value_noise(x, y, scale, layer_offset + octave) * weight
            weight_total += weight
        return total / weight_total

    def _generate(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                elevation = self._fractal_noise(x, y, 0)
                moisture = self._fractal_noise(x, y, 11)
                self.elevation.append(elevation)
                self.moisture.append(moisture)
                if elevation < 0.31:
                    terrain = TerrainType.WATER
                elif elevation < 0.38:
                    terrain = TerrainType.SAND
                elif elevation > 0.79:
                    terrain = TerrainType.ROCK
                elif moisture > 0.61:
                    terrain = TerrainType.FOREST
                else:
                    terrain = TerrainType.GRASS
                index = y * self.width + x
                self.tiles[index] = terrain
                if MOVEMENT_COST[terrain] != math.inf:
                    self._passable_indices.append(index)
        if not self._passable_indices:
            center = (self.height // 2) * self.width + self.width // 2
            self.tiles[center] = TerrainType.GRASS
            self._passable_indices.append(center)

    def in_tile_bounds(self, tile_x: int, tile_y: int) -> bool:
        return 0 <= tile_x < self.width and 0 <= tile_y < self.height

    def in_world_bounds(self, x: float, y: float) -> bool:
        return 0.0 <= x < self.pixel_width and 0.0 <= y < self.pixel_height

    def world_to_tile(self, x: float, y: float) -> tuple[int, int]:
        return (math.floor(x / self.tile_size), math.floor(y / self.tile_size))

    def tile_type(self, tile_x: int, tile_y: int) -> TerrainType:
        if not self.in_tile_bounds(tile_x, tile_y):
            return TerrainType.ROCK
        return TerrainType(self.tiles[tile_y * self.width + tile_x])

    def terrain_at(self, x: float, y: float) -> TerrainType:
        return self.tile_type(*self.world_to_tile(x, y))

    def movement_cost_at(self, x: float, y: float) -> float:
        if x < 0.0 or y < 0.0 or x >= self.pixel_width or y >= self.pixel_height:
            return math.inf
        tile_x = int(x) // self.tile_size
        tile_y = int(y) // self.tile_size
        return _MOVEMENT_COST_BY_VALUE[self.tiles[tile_y * self.width + tile_x]]

    def is_passable(self, x: float, y: float) -> bool:
        if x < 0.0 or y < 0.0 or x >= self.pixel_width or y >= self.pixel_height:
            return False
        tile_x = int(x) // self.tile_size
        tile_y = int(y) // self.tile_size
        return _MOVEMENT_COST_BY_VALUE[self.tiles[tile_y * self.width + tile_x]] != math.inf

    def random_passable_position(self, rng: random.Random) -> tuple[float, float]:
        index = self._passable_indices[rng.randrange(len(self._passable_indices))]
        tile_x = index % self.width
        tile_y = index // self.width
        inset = self.tile_size * 0.15
        usable = self.tile_size - 2.0 * inset
        return (
            tile_x * self.tile_size + inset + rng.random() * usable,
            tile_y * self.tile_size + inset + rng.random() * usable,
        )

    def state_bytes(self) -> bytes:
        return bytes(self.tiles)
