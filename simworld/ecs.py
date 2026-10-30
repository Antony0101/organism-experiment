"""Entity ids and generation-aware slot allocation."""

from .errors import StaleEntityError


Entity = int
INDEX_BITS = 32
INDEX_MASK = (1 << INDEX_BITS) - 1

__all__ = [
    "Entity", "INDEX_BITS", "INDEX_MASK", "entity_index", "entity_generation",
    "EntityAllocator",
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
