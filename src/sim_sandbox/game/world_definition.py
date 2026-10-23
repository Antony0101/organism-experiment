"""Definitions and launch data for selectable simulation worlds."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..engine.world import World

MAX_SEED = 4_294_967_295
MAX_ENTITY_COUNT = 10_000


@dataclass(frozen=True, slots=True)
class WorldLaunchOptions:
    seed: int
    entity_count: int

    def __post_init__(self) -> None:
        if not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be between 0 and {MAX_SEED:,}")
        if not 0 <= self.entity_count <= MAX_ENTITY_COUNT:
            raise ValueError(f"entity_count must be between 0 and {MAX_ENTITY_COUNT:,}")


@dataclass(frozen=True, slots=True)
class WorldSession:
    world: World
    initial_camera_position: tuple[float, float]
    initial_zoom: float = 1.0

    def __post_init__(self) -> None:
        if self.initial_zoom <= 0.0:
            raise ValueError("initial_zoom must be positive")

    def close(self) -> None:
        self.world.close()

    @property
    def camera_position(self) -> tuple[float, float]:
        """Compatibility alias for presentation callers."""
        return self.initial_camera_position

    @property
    def camera_zoom(self) -> float:
        """Compatibility alias for presentation callers."""
        return self.initial_zoom


WorldFactory = Callable[[WorldLaunchOptions], WorldSession]


@dataclass(frozen=True, slots=True)
class WorldDefinition:
    id: str
    name: str
    description: str
    menu_order: int
    default_seed: int
    default_population: int
    factory: WorldFactory

    def default_options(self) -> WorldLaunchOptions:
        return WorldLaunchOptions(self.default_seed, self.default_population)

    @property
    def order(self) -> int:
        """Compatibility alias for the original implementation name."""
        return self.menu_order

    @property
    def default_entity_count(self) -> int:
        """Expose the launch-option name alongside the metadata name."""
        return self.default_population

    def create(self, options: WorldLaunchOptions | None = None) -> WorldSession:
        launch_options = self.default_options() if options is None else options
        session = self.factory(launch_options)
        if not isinstance(session, WorldSession):
            raise TypeError(f"world factory {self.id!r} did not return WorldSession")
        return session
