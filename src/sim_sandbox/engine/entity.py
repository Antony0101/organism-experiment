"""Entity lifecycle contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .camera import Camera2D
    from .world import World


class Entity:
    """Base class for spatial entities managed by a :class:`World`."""

    __slots__ = ("_entity_id", "x", "y", "previous_x", "previous_y", "radius", "tags")

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        radius: float = 0.0,
        *,
        tags: tuple[str, ...] | frozenset[str] = (),
    ) -> None:
        self._entity_id: int | None = None
        self.x = float(x)
        self.y = float(y)
        self.previous_x = float(x)
        self.previous_y = float(y)
        self.radius = max(0.0, float(radius))
        self.tags = frozenset(tags)

    @property
    def entity_id(self) -> int:
        if self._entity_id is None:
            raise RuntimeError("entity has not been spawned")
        return self._entity_id

    def _bind_id(self, entity_id: int) -> None:
        if self._entity_id is not None:
            raise RuntimeError("entity is already bound to a world")
        self._entity_id = entity_id

    def init(self, world: World) -> None:
        """Initialize immediately before this entity becomes active."""

    def update(self, world: World, dt: float) -> None:
        """Advance by one fixed simulation tick."""

    def draw(self, surface: Any, camera: Camera2D, alpha: float) -> None:
        """Draw without mutating simulation state."""

    def delete(self, world: World) -> None:
        """Release resources immediately before removal."""

    def state_values(self) -> tuple[object, ...]:
        return (
            self.x,
            self.y,
            self.previous_x,
            self.previous_y,
            self.radius,
            tuple(sorted(self.tags)),
        )

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Type", type(self).__name__),
            ("ID", str(self.entity_id)),
            ("Position", f"{self.x:.2f}, {self.y:.2f}"),
            ("Radius", f"{self.radius:.2f}"),
            ("Tags", ", ".join(sorted(self.tags)) or "none"),
        )

