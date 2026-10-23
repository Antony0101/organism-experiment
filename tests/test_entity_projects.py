from __future__ import annotations

import base64
from pathlib import Path

import pygame
import pytest

from sim_sandbox.engine.camera import Camera2D
from sim_sandbox.engine.world import World
from sim_sandbox.game.entity_projects.model import (
    AppearanceDefinition,
    EntityProjectDefinition,
    EntityProjectValidationError,
    PropertyDefinition,
    validate_behavior_source,
)
from sim_sandbox.game.entity_projects.registry import (
    EntityProjectRegistry,
    EntityProjectStore,
)
from sim_sandbox.game.entity_projects.runtime import EditableEntity
from sim_sandbox.game.entity_projects.runtime import compile_behavior
from sim_sandbox.game.terrain import TerrainMap


MOVING_BEHAVIOR = """\
def init(entity, world):
    entity.state["started"] = True

def update(entity, world, dt):
    entity.x += entity.state["speed"] * dt

def delete(entity, world):
    pass
"""


def moving_definition() -> EntityProjectDefinition:
    return EntityProjectDefinition(
        id="moving_box",
        name="Moving Box",
        collision_radius=5.0,
        properties=(
            PropertyDefinition("speed", "float", 30.0),
            PropertyDefinition("started", "bool", False),
        ),
        appearance=AppearanceDefinition(
            kind="rectangle",
            size=(12.0, 8.0),
            fill_color=(20, 180, 240, 255),
            rotation_degrees=15.0,
            scale=(1.5, 1.0),
        ),
    )


def test_store_registry_and_runtime_entity(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    saved = store.save(moving_definition(), MOVING_BEHAVIOR)
    registry = EntityProjectRegistry(store.root)

    entity = registry.create("moving_box", 20.0, 30.0)
    assert isinstance(entity, EditableEntity)
    world = World(3, TerrainMap(3, width=16, height=16, tile_size=8))
    entity_id = world.spawn(entity)
    world.step(1.0 / 60.0)

    assert world.get(entity_id) is entity
    assert entity.state["started"] is True
    assert entity.x == pytest.approx(20.5)
    assert ("Speed", "30.0") in entity.inspection_fields()
    assert saved.definition == registry.require("moving_box").definition
    world.close()


def test_manifest_and_behavior_validation_reject_bad_input(tmp_path: Path) -> None:
    with pytest.raises(EntityProjectValidationError, match="schema_version"):
        EntityProjectDefinition.from_mapping(
            {"schema_version": 99, "id": "future", "name": "Future"}
        )

    with pytest.raises(EntityProjectValidationError, match="inside the project"):
        AppearanceDefinition.from_mapping(
            {"kind": "sprite", "sprite": "../outside.png"}, tmp_path
        )

    diagnostics = validate_behavior_source("def update(entity):\n    pass\n")
    assert diagnostics
    assert "exactly 3" in diagnostics[0].message

    diagnostics = validate_behavior_source("def update(:\n")
    assert diagnostics[0].line == 1

    decorated_signature_change = """\
def replace(function):
    return lambda entity: None

@replace
def update(entity, world, dt):
    pass
"""
    with pytest.raises(EntityProjectValidationError, match="exactly 3"):
        compile_behavior(decorated_signature_change)


def test_invalid_save_does_not_leave_a_project_directory(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    invalid = EntityProjectDefinition(id="Not A Slug", name="Invalid")

    with pytest.raises(EntityProjectValidationError, match="entity ID"):
        store.save(invalid, "")

    assert not store.root.exists()


def test_duplicate_archive_and_png_import_are_recoverable(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    store.save(moving_definition(), MOVING_BEHAVIOR)
    duplicate = store.duplicate("moving_box", "moving_box_copy", "Moving Box Copy")
    assert duplicate.definition.id == "moving_box_copy"
    assert (duplicate.directory / "entity.json").is_file()

    png = tmp_path / "icon.png"
    png.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+X8W9WQAAAABJRU5ErkJggg=="
        )
    )
    relative = store.import_sprite("moving_box", png)
    assert relative == "assets/icon.png"
    assert (store.project_directory("moving_box") / relative).is_file()

    archived = store.archive("moving_box_copy")
    assert archived.is_dir()
    assert archived.parent.name == ".trash"
    assert not store.project_directory("moving_box_copy").exists()


def test_shape_entity_draws_with_generic_renderer(tmp_path: Path) -> None:
    pygame.init()
    pygame.display.set_mode((160, 120))
    store = EntityProjectStore(tmp_path / "entities")
    store.save(moving_definition(), MOVING_BEHAVIOR)
    entity = EntityProjectRegistry(store.root).create("moving_box", 50, 50)
    world = World(1, TerrainMap(1, width=16, height=16, tile_size=8))
    world.spawn(entity)
    world.flush()
    surface = pygame.Surface((160, 120), pygame.SRCALPHA)
    camera = Camera2D(50, 50, 160, 120, world_width=128, world_height=128)

    entity.draw(surface, camera, 1.0)

    assert surface.get_bounding_rect().width > 0
    world.close()
    pygame.quit()


def test_sprite_entity_loads_tints_scales_and_draws(tmp_path: Path) -> None:
    pygame.init()
    pygame.display.set_mode((160, 120))
    store = EntityProjectStore(tmp_path / "entities")
    project = store.create_default("sprite_entity", "Sprite Entity")
    sprite = pygame.Surface((6, 4), pygame.SRCALPHA)
    sprite.fill((255, 255, 255, 255))
    sprite_path = project.directory / "assets" / "sprite.png"
    pygame.image.save(sprite, sprite_path)
    definition = EntityProjectDefinition(
        id="sprite_entity",
        name="Sprite Entity",
        appearance=AppearanceDefinition(
            kind="sprite",
            size=(6.0, 4.0),
            fill_color=(20, 180, 240, 255),
            rotation_degrees=20.0,
            scale=(2.0, 1.5),
            sprite="assets/sprite.png",
        ),
    )
    store.save(definition, project.behavior_source)
    entity = EntityProjectRegistry(store.root).create("sprite_entity", 50, 50)
    world = World(1, TerrainMap(1, width=16, height=16, tile_size=8))
    world.spawn(entity)
    world.flush()
    surface = pygame.Surface((160, 120), pygame.SRCALPHA)
    camera = Camera2D(50, 50, 160, 120, world_width=128, world_height=128)

    entity.draw(surface, camera, 1.0)

    assert surface.get_bounding_rect().width > 6
    assert entity.visual.color == (20, 180, 240, 255)
    world.close()
    pygame.quit()
