from __future__ import annotations

import pytest

from sim_sandbox.engine.world import World
from sim_sandbox.game.entities import SimpleEntity
from sim_sandbox.game.terrain import TerrainMap


def test_simple_entity_is_a_functional_starter_template() -> None:
    terrain = TerrainMap(4, width=12, height=12, tile_size=8)
    world = World(4, terrain)
    x, y = terrain.random_passable_position(world.rng)
    entity = SimpleEntity(x, y)

    entity_id = world.spawn(entity)
    world.step(1.0 / 60.0)

    assert world.get(entity_id) is entity
    assert entity.age == pytest.approx(1.0 / 60.0)
    assert ("Age", "0.02 s") in entity.inspection_fields()
    assert entity.state_values()[-2:] == (entity.age, entity.color)
    world.close()
