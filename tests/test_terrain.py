from __future__ import annotations

import math
import random

from sim_sandbox.terrain import MOVEMENT_COST, TerrainMap, TerrainType


def test_generation_is_seeded_and_cached() -> None:
    first = TerrainMap(42, width=32, height=24, tile_size=10)
    second = TerrainMap(42, width=32, height=24, tile_size=10)
    different = TerrainMap(43, width=32, height=24, tile_size=10)

    assert first.state_bytes() == second.state_bytes()
    assert list(first.elevation) == list(second.elevation)
    assert first.state_bytes() != different.state_bytes()
    assert len(first.moisture) == 32 * 24


def test_coordinate_bounds_and_costs() -> None:
    terrain = TerrainMap(5, width=8, height=6, tile_size=16)
    assert terrain.world_to_tile(15.99, 16.0) == (0, 1)
    assert terrain.tile_type(-1, 0) == TerrainType.ROCK
    assert terrain.tile_type(8, 0) == TerrainType.ROCK
    assert not terrain.is_passable(-0.1, 0)
    assert math.isinf(MOVEMENT_COST[TerrainType.WATER])
    assert math.isinf(MOVEMENT_COST[TerrainType.ROCK])
    assert MOVEMENT_COST[TerrainType.GRASS] == 1.0
    assert MOVEMENT_COST[TerrainType.SAND] > 1.0
    assert MOVEMENT_COST[TerrainType.FOREST] > MOVEMENT_COST[TerrainType.SAND]


def test_random_positions_are_passable_and_repeatable() -> None:
    terrain = TerrainMap(9, width=16, height=16, tile_size=8)
    first_rng = random.Random(100)
    second_rng = random.Random(100)
    first = [terrain.random_passable_position(first_rng) for _ in range(20)]
    second = [terrain.random_passable_position(second_rng) for _ in range(20)]
    assert first == second
    assert all(terrain.is_passable(x, y) for x, y in first)

