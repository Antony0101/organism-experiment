from __future__ import annotations

from sim_sandbox import Camera2D, Entity, TerrainMap, World
from sim_sandbox.engine.camera import Camera2D as EngineCamera
from sim_sandbox.engine.entity import Entity as EngineEntity
from sim_sandbox.engine.world import World as EngineWorld
from sim_sandbox.game.entities import WanderingAgent
from sim_sandbox.game.terrain import TerrainMap as GameTerrainMap
from sim_sandbox.game.world_definition import WorldLaunchOptions
from sim_sandbox.game.worlds.discovery import discover_worlds


def test_compatibility_imports_resolve_to_moved_implementations() -> None:
    assert Camera2D is EngineCamera
    assert Entity is EngineEntity
    assert World is EngineWorld
    assert TerrainMap is GameTerrainMap


def test_builtin_worlds_are_ordered_and_have_declared_defaults() -> None:
    catalog = discover_worlds()

    assert [definition.id for definition in catalog.definitions] == [
        "wandering_plains",
        "empty_sandbox",
    ]
    assert catalog.require("wandering_plains").default_entity_count == 1_000
    assert catalog.require("empty_sandbox").default_entity_count == 0
    assert catalog.errors == ()


def test_builtin_factories_create_deterministic_sessions() -> None:
    catalog = discover_worlds()
    expected_sizes = {
        "wandering_plains": (256, 256),
        "empty_sandbox": (96, 96),
    }

    for definition in catalog.definitions:
        options = WorldLaunchOptions(seed=123, entity_count=4)
        first = definition.create(options)
        second = definition.create(options)
        try:
            assert (first.world.terrain.width, first.world.terrain.height) == expected_sizes[
                definition.id
            ]
            assert first.world.entity_count == 4
            assert all(isinstance(entity, WanderingAgent) for entity in first.world)
            assert first.camera_position == (
                first.world.terrain.pixel_width / 2,
                first.world.terrain.pixel_height / 2,
            )
            assert first.world.state_digest() == second.world.state_digest()
        finally:
            first.close()
            second.close()
