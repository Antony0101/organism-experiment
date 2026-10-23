from __future__ import annotations

from pathlib import Path

import pytest

from sim_sandbox.engine.entity import Entity
from sim_sandbox.engine.world import World
from sim_sandbox.game.behavior_projects import (
    BehaviorAttachment,
    BehaviorDefinition,
    BehaviorProject,
    BehaviorProjectRegistry,
    BehaviorProjectStore,
)
from sim_sandbox.game.entity_projects.model import (
    DEFAULT_BEHAVIOR_SOURCE,
    AppearanceDefinition,
    EntityProjectDefinition,
)
from sim_sandbox.game.entity_projects.runtime import EditableEntity, compile_behavior
from sim_sandbox.game.project_types import PropertyDefinition
from sim_sandbox.game.terrain import TerrainMap


def test_builtin_pack_has_24_valid_compilable_presets(tmp_path: Path) -> None:
    registry = BehaviorProjectRegistry(tmp_path / "behaviors")

    assert len(registry.catalog.projects) == 24
    assert len({item.definition.id for item in registry.catalog.projects}) == 24
    assert all(item.builtin for item in registry.catalog.projects)
    for project in registry.catalog.projects:
        registry.callbacks(project.definition.id)


def test_custom_projects_cannot_shadow_builtins(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        BehaviorProjectStore(tmp_path / "behaviors").create_default(
            "wander", "Shadow Wander"
        )


def test_schema_one_entity_loads_as_schema_two_without_attachments() -> None:
    source = """{
      "schema_version": 1,
      "id": "legacy_dot",
      "name": "Legacy Dot",
      "description": "",
      "collision_radius": 3,
      "properties": [],
      "appearance": {"kind": "circle", "size": [6, 6]},
      "preview": {"seed": 1, "instances": 1}
    }"""

    definition = EntityProjectDefinition.from_json(source)

    assert definition.schema_version == 2
    assert definition.tags == ()
    assert definition.behaviors == ()
    assert '"schema_version": 2' in definition.to_json()


def _ordered_runtime(tmp_path: Path) -> tuple[World, EditableEntity]:
    first = BehaviorDefinition("first", "First")
    second = BehaviorDefinition("second", "Second")
    source = '''def init(behavior, entity, world):
    entity.state["events"] += "first:init|" if behavior.behavior_id == "first" else "second:init|"

def update(behavior, entity, world, dt):
    entity.state["events"] += "first:update|" if behavior.behavior_id == "first" else "second:update|"

def delete(behavior, entity, world):
    entity.state["events"] += "first:delete|" if behavior.behavior_id == "first" else "second:delete|"
'''
    registry = BehaviorProjectRegistry(
        tmp_path / "behaviors",
        overrides=(
            BehaviorProject(first, source, None),
            BehaviorProject(second, source, None),
        ),
    )
    definition = EntityProjectDefinition(
        "ordered_host",
        "Ordered Host",
        properties=(PropertyDefinition("events", "str", "", True),),
        behaviors=(
            BehaviorAttachment("first", "first"),
            BehaviorAttachment("second", "second"),
        ),
        appearance=AppearanceDefinition(kind="circle", size=(8, 8)),
    )
    entity_source = '''def init(entity, world):
    entity.state["events"] += "custom:init|"

def update(entity, world, dt):
    entity.state["events"] += "custom:update|"

def delete(entity, world):
    entity.state["events"] += "custom:delete|"
'''
    terrain = TerrainMap(3, width=24, height=24, tile_size=8)
    world = World(3, terrain)
    x, y = terrain.random_passable_position(world.rng)
    entity = EditableEntity(
        definition,
        compile_behavior(entity_source),
        tmp_path,
        x,
        y,
        registry.instantiate_entity_behaviors(definition),
    )
    world.spawn(entity)
    world.flush()
    return world, entity


def test_attachments_run_top_down_and_cleanup_reverses_after_custom(tmp_path: Path) -> None:
    world, entity = _ordered_runtime(tmp_path)
    assert entity.state["events"] == "first:init|second:init|custom:init|"

    world.step(1 / 60)
    assert entity.state["events"].endswith("first:update|second:update|custom:update|")

    world.remove(entity.entity_id)
    world.flush()
    assert entity.state["events"].endswith("custom:delete|second:delete|first:delete|")


class TaggedEntity(Entity):
    def __init__(self, x: float, y: float, project_id: str, *tags: str) -> None:
        super().__init__(x, y, 2, tags=tags)
        self.project_id = project_id


def test_filtered_queries_and_ties_are_deterministic() -> None:
    terrain = TerrainMap(1, width=24, height=24, tile_size=8)
    world = World(1, terrain)
    a_id = world.spawn(TaggedEntity(40, 50, "food_dot", "food"))
    b_id = world.spawn(TaggedEntity(60, 50, "food_dot", "food"))
    world.spawn(TaggedEntity(50, 52, "threat_dot", "threat"))
    world.flush()

    nearest = world.nearest_entity(
        50, 50, 20, required_tags=("food",), project_id="food_dot"
    )
    assert nearest is not None
    assert nearest.entity_id == min(a_id, b_id)
    assert [item.entity_id for item in world.query_radius(50, 50, 20, required_tags=("food",))] == [a_id, b_id]
    assert world.query_radius(50, 50, 20, required_tags=("food",), exclude_id=a_id)[0].entity_id == b_id
    assert [
        item.entity_id
        for item in world.query_rect(
            35, 45, 65, 55, required_tags=("food",), project_id="food_dot"
        )
    ] == [a_id, b_id]
    world.close()


@pytest.mark.parametrize("behavior_id", [
    "constant_velocity", "wander", "seek_nearest", "flee_nearest",
    "orbit_nearest", "keep_in_bounds", "avoid_blocked_terrain",
    "terrain_speed_modifier", "maximum_lifetime", "age_counter", "health",
    "energy_metabolism", "hunger", "regeneration", "growth_over_time",
    "nearest_tag_sensor", "contact_damage", "eat_nearby", "reproduce",
    "periodic_spawner", "spin", "pulse_scale", "face_velocity",
    "property_color_map",
])
def test_each_builtin_runs_deterministically(tmp_path: Path, behavior_id: str) -> None:
    def run_once() -> str:
        registry = BehaviorProjectRegistry(tmp_path / "behaviors")
        behavior = registry.require(behavior_id).definition
        properties = list(behavior.required_properties)
        existing = {item.name for item in properties}
        if behavior_id == "regeneration" and "health" not in existing:
            properties.append(PropertyDefinition("health", "float", 20.0))
        if behavior_id == "property_color_map" and "energy" not in existing:
            properties.append(PropertyDefinition("energy", "float", 50.0))
        definition = EntityProjectDefinition(
            "host",
            "Host",
            properties=tuple(properties),
            tags=("organism", "food", "target", "threat"),
            behaviors=(BehaviorAttachment("test", behavior_id),),
            appearance=AppearanceDefinition(kind="circle", size=(10, 10)),
        )
        callbacks = compile_behavior(DEFAULT_BEHAVIOR_SOURCE)
        terrain = TerrainMap(19, width=32, height=32, tile_size=8)
        world = World(19, terrain, population_limit=100)

        def factory(project_id: str, x: float, y: float) -> EditableEntity:
            assert project_id == "host"
            return EditableEntity(
                definition,
                callbacks,
                tmp_path,
                x,
                y,
                registry.instantiate_entity_behaviors(definition),
            )

        world.configure_entity_factory(factory)
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(factory("host", x, y))
        world.flush()
        world.step(1 / 60)
        digest = world.state_digest()
        world.close()
        return digest

    assert run_once() == run_once()
