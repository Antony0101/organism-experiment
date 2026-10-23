from __future__ import annotations

from sim_sandbox.agents import WanderingAgent
from sim_sandbox.terrain import TerrainMap
from sim_sandbox.world import World


def make_agent_world(seed: int, count: int = 20) -> World:
    terrain = TerrainMap(seed, width=32, height=32, tile_size=10)
    world = World(seed, terrain)
    for _ in range(count):
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(WanderingAgent(x, y))
    world.flush()
    return world


def test_seeded_agents_produce_identical_state() -> None:
    first = make_agent_world(123)
    second = make_agent_world(123)
    for _ in range(180):
        first.step(1 / 60)
        second.step(1 / 60)
    assert first.state_digest() == second.state_digest()


def test_agents_remain_in_bounds_and_on_passable_terrain() -> None:
    world = make_agent_world(88, count=30)
    for _ in range(300):
        world.step(1 / 60)
    for entity in world:
        assert world.terrain.in_world_bounds(entity.x, entity.y)
        assert world.terrain.is_passable(entity.x, entity.y)


def test_world_spatial_index_tracks_agent_movement() -> None:
    world = make_agent_world(77, count=1)
    entity = world.entities[0]
    entity.x, entity.y = world.terrain.random_passable_position(world.rng)
    world.step(1 / 60)
    assert entity in world.query_radius(entity.x, entity.y, 0.001)

