"""Bounded 2D camera."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Camera2D:
    x: float
    y: float
    viewport_width: int = 1280
    viewport_height: int = 720
    zoom: float = 1.0
    min_zoom: float = 0.5
    max_zoom: float = 4.0
    world_width: float = 4096.0
    world_height: float = 4096.0

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return (
            (x - self.x) * self.zoom + self.viewport_width / 2,
            (y - self.y) * self.zoom + self.viewport_height / 2,
        )

    def screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.x + (x - self.viewport_width / 2) / self.zoom,
            self.y + (y - self.viewport_height / 2) / self.zoom,
        )

    def visible_rect(self, padding: float = 0.0) -> tuple[float, float, float, float]:
        half_width = self.viewport_width / (2.0 * self.zoom)
        half_height = self.viewport_height / (2.0 * self.zoom)
        return (
            self.x - half_width - padding,
            self.y - half_height - padding,
            self.x + half_width + padding,
            self.y + half_height + padding,
        )

    def resize(self, width: int, height: int) -> None:
        self.viewport_width = max(1, int(width))
        self.viewport_height = max(1, int(height))
        self.clamp()

    def pan(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        self.clamp()

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        before_x, before_y = self.screen_to_world(screen_x, screen_y)
        self.zoom = min(self.max_zoom, max(self.min_zoom, self.zoom * factor))
        after_x, after_y = self.screen_to_world(screen_x, screen_y)
        self.x += before_x - after_x
        self.y += before_y - after_y
        self.clamp()

    def clamp(self) -> None:
        half_width = self.viewport_width / (2.0 * self.zoom)
        half_height = self.viewport_height / (2.0 * self.zoom)
        if half_width * 2 >= self.world_width:
            self.x = self.world_width / 2
        else:
            self.x = min(self.world_width - half_width, max(half_width, self.x))
        if half_height * 2 >= self.world_height:
            self.y = self.world_height / 2
        else:
            self.y = min(self.world_height - half_height, max(half_height, self.y))

