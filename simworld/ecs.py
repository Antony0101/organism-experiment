"""Entity ids, generation-aware allocation and deferred structural commands."""

from __future__ import annotations

import typing as t

from .errors import StaleEntityError

if t.TYPE_CHECKING:
    from .world import World


Entity = int
INDEX_BITS = 32
INDEX_MASK = (1 << INDEX_BITS) - 1

__all__ = [
    "Entity", "INDEX_BITS", "INDEX_MASK", "entity_index", "entity_generation",
    "EntityAllocator", "CommandBuffer",
]


def entity_index(e: Entity) -> int:
    """Extract the slot index from an entity id."""
    return e & INDEX_MASK


def entity_generation(e: Entity) -> int:
    """Extract the generation from an entity id."""
    return e >> INDEX_BITS


class EntityAllocator:
    """Reuse released slots while keeping earlier ids stale."""

    def __init__(self):
        self.generations: list[int] = []
        self.alive: list[bool] = []
        self.free: list[int] = []

    def alloc(self) -> Entity:
        if self.free:
            index = self.free.pop()
            self.alive[index] = True
        else:
            index = len(self.generations)
            self.generations.append(1)
            self.alive.append(True)
        return (self.generations[index] << INDEX_BITS) | index

    def release(self, e: Entity) -> None:
        self.check(e)
        index = entity_index(e)
        self.alive[index] = False
        self.generations[index] += 1
        self.free.append(index)

    def revive(self, e: Entity) -> None:
        """Undo the most recent release, restoring the original generation."""
        if not isinstance(e, int) or isinstance(e, bool) or e <= 0:
            raise StaleEntityError(f"{e!r} is not an entity id; expected a positive integer.")
        index, generation = entity_index(e), entity_generation(e)
        if (
            generation == 0
            or index >= len(self.generations)
            or self.alive[index]
            or self.generations[index] != generation + 1
            or not self.free
            or self.free[-1] != index
        ):
            raise StaleEntityError(f"Cannot revive entity {e}: release undo must follow LIFO order.")
        self.free.pop()
        self.generations[index] = generation
        self.alive[index] = True

    def rollback_alloc(self, e: Entity) -> None:
        """Undo allocation without incrementing its generation; callers must undo in LIFO order."""
        self.check(e)
        index = entity_index(e)
        if self.generations[index] == 1:
            if index != len(self.generations) - 1:
                raise StaleEntityError(f"Cannot roll back entity {e}: allocation undo must follow LIFO order.")
            self.generations.pop()
            self.alive.pop()
        else:
            self.alive[index] = False
            self.free.append(index)

    def is_alive(self, e) -> bool:
        if not isinstance(e, int) or isinstance(e, bool) or e <= 0:
            return False
        index = entity_index(e)
        return (
            index < len(self.generations)
            and self.alive[index]
            and entity_generation(e) == self.generations[index]
        )

    def check(self, e) -> None:
        if not isinstance(e, int) or isinstance(e, bool) or e <= 0:
            raise StaleEntityError(f"{e!r} is not an entity id; expected a positive integer.")
        index, generation = entity_index(e), entity_generation(e)
        if index >= len(self.generations):
            raise StaleEntityError(f"Entity {e} never existed: slot {index} was never allocated.")
        current = self.generations[index]
        if generation == 0 or generation > current:
            raise StaleEntityError(
                f"Entity {e} never existed: id has generation {generation}, "
                f"slot {index} is now at generation {current}."
            )
        if not self.alive[index] or generation != current:
            raise StaleEntityError(
                f"Entity {e} is stale: it was despawned "
                f"(id has generation {generation}, slot {index} is now at generation {current})."
            )

    def count_alive(self) -> int:
        return sum(self.alive)

    def to_dict(self) -> dict:
        """Copy allocator state, retaining the order of slots available for reuse."""
        return {
            "generations": self.generations[:],
            "alive": self.alive[:],
            "free": self.free[:],
        }

    @classmethod
    def from_dict(cls, data):
        """Restore allocator state from its serialized lists without sharing them."""
        allocator = cls()
        allocator.generations = list(data["generations"])
        allocator.alive = list(data["alive"])
        allocator.free = list(data["free"])
        return allocator


class CommandBuffer:
    """Queue world mutations, reserving spawned ids before attaching their data."""

    def __init__(self, world: World):
        self._world = world
        self._ops: list[tuple[str, tuple, dict]] = []

    def spawn(self, *components, name=None) -> Entity:
        """Reserve a live id now; validate and attach components at apply time."""
        entity = self._world._alloc.alloc()
        self._ops.append(("spawn", (entity, components, name), {}))
        return entity

    def spawn_prefab(self, prefab, *, entity_name=None, **overrides) -> Entity:
        """Build independent prefab components now, then queue their attachment."""
        components = self._world._prefab_components(prefab, overrides)
        return self.spawn(*components, name=entity_name)

    def despawn(self, e: Entity) -> None:
        self._ops.append(("despawn", (e,), {}))

    def add(self, e: Entity, *components) -> None:
        self._ops.append(("add", (e, components), {}))

    def remove(self, e: Entity, *components) -> None:
        self._ops.append(("remove", (e, components), {}))

    def defer(self, fn: t.Callable[[World], None]) -> None:
        """Queue a callback that receives the world when applied."""
        self._ops.append(("defer", (fn,), {}))

    def apply(self, world=None, max_rounds=100) -> int:
        """Apply queued operations in order, then drain work queued by callbacks."""
        world = self._world if world is None else world
        applied = rounds = 0
        while self._ops:
            rounds += 1
            if rounds > max_rounds:
                raise RuntimeError("Command buffer did not settle (commands keep queueing commands).")
            ops, self._ops = self._ops, []
            for op, args, _ in ops:
                if op == "spawn":
                    world._finish_spawn(*args)
                elif op == "despawn":
                    world.despawn(args[0])
                elif op == "add":
                    world.add(args[0], *args[1])
                elif op == "remove":
                    world.remove(args[0], *args[1])
                else:
                    args[0](world)
                applied += 1
        return applied
