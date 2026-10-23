"""Factory for project-driven worlds configured from the Project Hub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..engine.world import World
from .behavior_projects.registry import BehaviorProjectRegistry
from .entity_projects.registry import EntityProjectRegistry
from .terrain import TerrainMap
from .world_definition import MAX_ENTITY_COUNT, MAX_SEED, WorldSession

TERRAIN_PRESETS: dict[str, tuple[int, int]] = {
    "compact": (64, 64),
    "standard": (128, 128),
    "large": (256, 256),
}


@dataclass(frozen=True, slots=True)
class SandboxPopulation:
    entity_id: str
    count: int

    def __post_init__(self) -> None:
        if not self.entity_id:
            raise ValueError("entity project ID cannot be empty")
        if not 1 <= self.count <= MAX_ENTITY_COUNT:
            raise ValueError(f"population count must be 1..{MAX_ENTITY_COUNT}")


@dataclass(frozen=True, slots=True)
class QuickSandboxOptions:
    terrain: str = "standard"
    seed: int = 1
    populations: tuple[SandboxPopulation, ...] = ()

    def __post_init__(self) -> None:
        if self.terrain not in TERRAIN_PRESETS:
            raise ValueError(f"unknown terrain preset {self.terrain!r}")
        if not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be 0..{MAX_SEED}")
        if len(self.populations) > 8:
            raise ValueError("quick sandbox supports at most eight population rows")
        if sum(item.count for item in self.populations) > MAX_ENTITY_COUNT:
            raise ValueError(f"total population cannot exceed {MAX_ENTITY_COUNT}")


def create_quick_sandbox(
    options: QuickSandboxOptions,
    content_root: Path | str = Path("content"),
) -> WorldSession:
    content_root = Path(content_root)
    behavior_registry = BehaviorProjectRegistry(content_root / "behaviors")
    entity_registry = EntityProjectRegistry(content_root / "entities", behavior_registry)
    width, height = TERRAIN_PRESETS[options.terrain]
    terrain = TerrainMap(options.seed, width=width, height=height, tile_size=16)
    world = World(options.seed, terrain)
    entity_registry.configure_world(world)
    for row in options.populations:
        entity_registry.require(row.entity_id)
        for _ in range(row.count):
            x, y = terrain.random_passable_position(world.rng)
            world.spawn(entity_registry.create(row.entity_id, x, y))
    world.flush()
    zoom = min(1.0, 900 / terrain.pixel_width, 600 / terrain.pixel_height)
    return WorldSession(
        world,
        (terrain.pixel_width / 2, terrain.pixel_height / 2),
        max(0.25, zoom),
    )


__all__ = [
    "TERRAIN_PRESETS",
    "QuickSandboxOptions",
    "SandboxPopulation",
    "create_quick_sandbox",
]
