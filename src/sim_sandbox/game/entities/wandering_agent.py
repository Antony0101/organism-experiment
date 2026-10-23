"""Example terrain-aware wandering entity."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from ...engine.entity import Entity

if TYPE_CHECKING:
    from ...engine.camera import Camera2D
    from ...engine.world import World


class WanderingAgent(Entity):
    __slots__ = ("target_x", "target_y", "base_speed", "color")

    def __init__(self, x: float, y: float, base_speed: float = 44.0) -> None:
        super().__init__(x, y, radius=3.0)
        self.target_x = x
        self.target_y = y
        self.base_speed = float(base_speed)
        self.color = (245, 245, 245)

    def init(self, world: World) -> None:
        self.color = (
            world.rng.randrange(145, 256),
            world.rng.randrange(145, 256),
            world.rng.randrange(145, 256),
        )
        self._choose_target(world)

    def _choose_target(self, world: World) -> None:
        for _ in range(16):
            angle = world.rng.random() * math.tau
            distance = world.rng.uniform(48.0, 220.0)
            target_x = min(
                world.terrain.pixel_width - 0.001,
                max(0.0, self.x + math.cos(angle) * distance),
            )
            target_y = min(
                world.terrain.pixel_height - 0.001,
                max(0.0, self.y + math.sin(angle) * distance),
            )
            if world.terrain.is_passable(target_x, target_y):
                self.target_x = target_x
                self.target_y = target_y
                return
        self.target_x, self.target_y = world.terrain.random_passable_position(world.rng)

    def update(self, world: World, dt: float) -> None:
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.hypot(dx, dy)
        if distance < 5.0:
            self._choose_target(world)
            return
        cost = world.terrain.movement_cost_at(self.x, self.y)
        if not math.isfinite(cost):
            self.x, self.y = world.terrain.random_passable_position(world.rng)
            self._choose_target(world)
            return
        step = min(distance, self.base_speed * dt / cost)
        move_x = dx / distance * step
        move_y = dy / distance * step
        candidate_x = self.x + move_x
        candidate_y = self.y + move_y
        if world.terrain.is_passable(candidate_x, candidate_y):
            self.x = candidate_x
            self.y = candidate_y
            return
        if world.terrain.is_passable(candidate_x, self.y):
            self.x = candidate_x
        elif world.terrain.is_passable(self.x, candidate_y):
            self.y = candidate_y
        else:
            self._choose_target(world)

    def draw(self, surface: Any, camera: Camera2D, alpha: float) -> None:
        import pygame

        render_x = self.previous_x + (self.x - self.previous_x) * alpha
        render_y = self.previous_y + (self.y - self.previous_y) * alpha
        screen_x, screen_y = camera.world_to_screen(render_x, render_y)
        radius = max(1, round(self.radius * camera.zoom))
        pygame.draw.circle(surface, self.color, (round(screen_x), round(screen_y)), radius)

    def state_values(self) -> tuple[object, ...]:
        return super().state_values() + (
            self.target_x,
            self.target_y,
            self.base_speed,
            self.color,
        )

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        return super().inspection_fields() + (
            ("Target", f"{self.target_x:.2f}, {self.target_y:.2f}"),
            ("Base speed", f"{self.base_speed:.2f} px/s"),
            ("Color", str(self.color)),
        )
