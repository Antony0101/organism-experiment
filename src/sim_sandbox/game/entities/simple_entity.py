"""Minimal entity implementation intended to be copied as a starting point."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...engine.entity import Entity

if TYPE_CHECKING:
    from ...engine.camera import Camera2D
    from ...engine.world import World


class SimpleEntity(Entity):
    """A stationary circle that tracks how long it has been alive.

    Copy this module and rename the class when starting a new entity type. The
    entity is fully functional as written, but built-in worlds do not spawn it
    automatically.
    """

    __slots__ = ("age", "color")

    def __init__(
        self,
        x: float,
        y: float,
        color: tuple[int, int, int] = (255, 210, 70),
    ) -> None:
        # Entity owns x, y, previous_x, previous_y, radius, and entity_id.
        super().__init__(x, y, radius=5.0)
        self.age = 0.0
        self.color = color

    def init(self, world: World) -> None:
        """Run once when the world activates this entity."""
        # Initialize behavior here. Use world.rng for deterministic randomness.

    def update(self, world: World, dt: float) -> None:
        """Run once per fixed simulation tick."""
        self.age += dt

        # Add behavior here. For example, movement should change self.x/self.y.
        # Test a destination with world.terrain.is_passable(x, y) before moving.
        # Remove this entity with world.remove(self.entity_id) when appropriate.

    def draw(self, surface: Any, camera: Camera2D, alpha: float) -> None:
        """Draw the entity without changing simulation state."""
        import pygame

        # Interpolation keeps motion smooth when rendering between fixed ticks.
        render_x = self.previous_x + (self.x - self.previous_x) * alpha
        render_y = self.previous_y + (self.y - self.previous_y) * alpha
        screen_x, screen_y = camera.world_to_screen(render_x, render_y)
        screen_radius = max(1, round(self.radius * camera.zoom))
        pygame.draw.circle(
            surface,
            self.color,
            (round(screen_x), round(screen_y)),
            screen_radius,
        )

    def delete(self, world: World) -> None:
        """Run once immediately before removal or world shutdown."""
        # Release entity-owned resources here when a future entity needs them.

    def state_values(self) -> tuple[object, ...]:
        """Include custom simulation state in deterministic world hashes."""
        return super().state_values() + (self.age, self.color)

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        """Add custom values to the selected-entity inspector."""
        return super().inspection_fields() + (
            ("Age", f"{self.age:.2f} s"),
            ("Color", str(self.color)),
        )
