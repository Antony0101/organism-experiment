"""World state, entity ownership, and fixed-tick lifecycle handling."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Iterator
from typing import Any

from .entity import Entity
from .spatial import SpatialHash


class World:
    def __init__(
        self,
        seed: int,
        terrain: Any,
        spatial_cell_size: float = 64.0,
        *,
        population_limit: int = 10_000,
    ) -> None:
        if terrain is None:
            raise ValueError("engine World requires a terrain instance")
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.terrain = terrain
        self.spatial = SpatialHash(spatial_cell_size)
        self.tick_index = 0
        self._next_entity_id = 1
        self._entities: dict[int, Entity] = {}
        self._pending_spawns: list[Entity] = []
        self._pending_removals: set[int] = set()
        self._updating = False
        self._closing = False
        self._closed = False
        self.population_limit = int(population_limit)
        if self.population_limit <= 0:
            raise ValueError("population_limit must be positive")
        self._entity_factory: Callable[[str, float, float], Entity] | None = None

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def entities(self) -> tuple[Entity, ...]:
        return tuple(self._entities.values())

    @property
    def is_closed(self) -> bool:
        return self._closed

    def __iter__(self) -> Iterator[Entity]:
        return iter(self._entities.values())

    def get(self, entity_id: int) -> Entity | None:
        return self._entities.get(entity_id)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("world is closed")

    def spawn(self, entity: Entity) -> int:
        self._ensure_open()
        if not isinstance(entity, Entity):
            raise TypeError("world can only spawn Entity instances")
        if len(self._entities) + len(self._pending_spawns) >= self.population_limit:
            raise RuntimeError(
                f"world population limit of {self.population_limit:,} has been reached"
            )
        entity_id = self._next_entity_id
        entity._bind_id(entity_id)
        self._next_entity_id += 1
        self._pending_spawns.append(entity)
        return entity_id

    def configure_entity_factory(
        self, factory: Callable[[str, float, float], Entity]
    ) -> None:
        """Install the trusted project factory used by behavior-driven spawning."""
        self._ensure_open()
        if not callable(factory):
            raise TypeError("entity factory must be callable")
        self._entity_factory = factory

    def spawn_project(self, project_id: str, x: float, y: float) -> int:
        self._ensure_open()
        if self._entity_factory is None:
            raise RuntimeError(
                "this world has no entity project registry configured for spawning"
            )
        return self.spawn(self._entity_factory(project_id, float(x), float(y)))

    def remove(self, entity_id: int) -> bool:
        self._ensure_open()
        exists = entity_id in self._entities or any(
            entity.entity_id == entity_id for entity in self._pending_spawns
        )
        if exists:
            self._pending_removals.add(entity_id)
        return exists

    def flush(self) -> None:
        self._ensure_open()
        if self._updating:
            raise RuntimeError("cannot flush lifecycle changes during an update")
        self._apply_pending()

    def _apply_pending(self) -> None:
        removals = self._pending_removals
        spawns = self._pending_spawns
        self._pending_removals = set()
        self._pending_spawns = []
        for entity_id in sorted(removals):
            entity = self._entities.pop(entity_id, None)
            if entity is not None:
                self.spatial.remove(entity_id)
                entity.delete(self)
        for entity in spawns:
            if entity.entity_id in removals:
                continue
            self._entities[entity.entity_id] = entity
            entity.previous_x = entity.x
            entity.previous_y = entity.y
            entity.init(self)
            self.spatial.insert(entity.entity_id, entity.x, entity.y)

    def step(self, dt: float) -> None:
        self._ensure_open()
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.flush()
        self._updating = True
        completed = False
        try:
            pending_removals = self._pending_removals
            for entity_id, entity in self._entities.items():
                if pending_removals and entity_id in pending_removals:
                    continue
                entity.previous_x = entity.x
                entity.previous_y = entity.y
                entity.update(self, dt)
            self.spatial.sync(self._entities.items())
            completed = True
        finally:
            self._updating = False
        if completed:
            self._apply_pending()
            self.tick_index += 1

    def query_rect(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        *,
        required_tags: tuple[str, ...] | frozenset[str] = (),
        project_id: str | None = None,
        exclude_id: int | None = None,
    ) -> list[Entity]:
        required = frozenset(required_tags)
        result = [
            self._entities[entity_id]
            for entity_id in self.spatial.query_rect(left, top, right, bottom)
            if entity_id in self._entities
            and entity_id not in self._pending_removals
            and entity_id != exclude_id
            and required.issubset(self._entities[entity_id].tags)
            and (
                project_id is None
                or getattr(self._entities[entity_id], "project_id", None) == project_id
            )
        ]
        result.sort(key=lambda entity: entity.entity_id)
        return result

    def query_radius(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        required_tags: tuple[str, ...] | frozenset[str] = (),
        project_id: str | None = None,
        exclude_id: int | None = None,
    ) -> list[Entity]:
        required = frozenset(required_tags)
        result = [
            self._entities[entity_id]
            for entity_id in self.spatial.query_radius(x, y, radius)
            if entity_id in self._entities
            and entity_id not in self._pending_removals
            and entity_id != exclude_id
            and required.issubset(self._entities[entity_id].tags)
            and (
                project_id is None
                or getattr(self._entities[entity_id], "project_id", None) == project_id
            )
        ]
        result.sort(key=lambda entity: entity.entity_id)
        return result

    def nearest_entity(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        required_tags: tuple[str, ...] | frozenset[str] = (),
        project_id: str | None = None,
        exclude_id: int | None = None,
    ) -> Entity | None:
        candidates = self.query_radius(
            x,
            y,
            radius,
            required_tags=required_tags,
            project_id=project_id,
            exclude_id=exclude_id,
        )
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda entity: (
                (entity.x - x) ** 2 + (entity.y - y) ** 2,
                entity.entity_id,
            ),
        )

    def state_digest(self) -> str:
        digest = hashlib.sha256()
        digest.update(str((self.seed, self.tick_index)).encode("ascii"))
        digest.update(self.terrain.state_bytes())
        for entity_id, entity in self._entities.items():
            state = (entity_id, type(entity).__qualname__, entity.state_values())
            digest.update(repr(state).encode("utf-8"))
        return digest.hexdigest()

    def close(self) -> None:
        """Delete active entities and make this world unusable."""
        if self._closed or self._closing:
            return
        if self._updating:
            raise RuntimeError("cannot close a world during an update")
        self._closing = True
        first_error: BaseException | None = None
        try:
            self._pending_spawns.clear()
            self._pending_removals.clear()
            for entity_id in sorted(self._entities):
                entity = self._entities[entity_id]
                self.spatial.remove(entity_id)
                try:
                    entity.delete(self)
                except BaseException as exc:
                    if first_error is None:
                        first_error = exc
        finally:
            # Hooks may queue lifecycle work. Closing intentionally discards it.
            self._entities.clear()
            self._pending_spawns.clear()
            self._pending_removals.clear()
            self.spatial.clear()
            self._closing = False
            self._closed = True
            self._entity_factory = None
        if first_error is not None:
            raise first_error

