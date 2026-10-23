"""Pygame renderers for terrain, entities, and diagnostics."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ..game.terrain import TerrainMap, TerrainType

if TYPE_CHECKING:
    from ..engine.camera import Camera2D
    from ..engine.clock import FixedStepClock
    from ..engine.entity import Entity
    from ..engine.world import World


TERRAIN_COLORS = {
    TerrainType.WATER: (39, 93, 151),
    TerrainType.SAND: (205, 186, 126),
    TerrainType.GRASS: (78, 137, 74),
    TerrainType.FOREST: (42, 92, 57),
    TerrainType.ROCK: (101, 104, 106),
}


class TerrainRenderer:
    """Cache terrain in chunks and only scale and blit visible chunks."""

    def __init__(self, terrain: TerrainMap, chunk_tiles: int = 32) -> None:
        self.terrain = terrain
        self.chunk_tiles = chunk_tiles
        self.chunk_pixels = chunk_tiles * terrain.tile_size
        self._native_chunks: dict[tuple[int, int], pygame.Surface] = {}
        self._scaled_chunks: dict[tuple[int, int], pygame.Surface] = {}
        self._scale_key: float | None = None
        self._build_native_chunks()

    def _build_native_chunks(self) -> None:
        columns = math.ceil(self.terrain.width / self.chunk_tiles)
        rows = math.ceil(self.terrain.height / self.chunk_tiles)
        size = self.terrain.tile_size
        for chunk_y in range(rows):
            for chunk_x in range(columns):
                tile_left = chunk_x * self.chunk_tiles
                tile_top = chunk_y * self.chunk_tiles
                tile_right = min(self.terrain.width, tile_left + self.chunk_tiles)
                tile_bottom = min(self.terrain.height, tile_top + self.chunk_tiles)
                surface = pygame.Surface(
                    ((tile_right - tile_left) * size, (tile_bottom - tile_top) * size)
                ).convert()
                for tile_y in range(tile_top, tile_bottom):
                    for tile_x in range(tile_left, tile_right):
                        terrain_type = self.terrain.tile_type(tile_x, tile_y)
                        local_rect = (
                            (tile_x - tile_left) * size,
                            (tile_y - tile_top) * size,
                            size,
                            size,
                        )
                        surface.fill(TERRAIN_COLORS[terrain_type], local_rect)
                self._native_chunks[(chunk_x, chunk_y)] = surface

    def draw(self, surface: pygame.Surface, camera: Camera2D) -> None:
        scale_key = round(camera.zoom, 4)
        if scale_key != self._scale_key:
            self._scale_key = scale_key
            self._scaled_chunks.clear()

        left, top, right, bottom = camera.visible_rect()
        min_chunk_x = max(0, math.floor(left / self.chunk_pixels))
        min_chunk_y = max(0, math.floor(top / self.chunk_pixels))
        max_chunk_x = min(
            math.ceil(self.terrain.pixel_width / self.chunk_pixels) - 1,
            math.floor(right / self.chunk_pixels),
        )
        max_chunk_y = min(
            math.ceil(self.terrain.pixel_height / self.chunk_pixels) - 1,
            math.floor(bottom / self.chunk_pixels),
        )
        for chunk_y in range(min_chunk_y, max_chunk_y + 1):
            for chunk_x in range(min_chunk_x, max_chunk_x + 1):
                key = (chunk_x, chunk_y)
                native = self._native_chunks[key]
                target_size = (
                    max(1, round(native.get_width() * camera.zoom)),
                    max(1, round(native.get_height() * camera.zoom)),
                )
                scaled = self._scaled_chunks.get(key)
                if scaled is None or scaled.get_size() != target_size:
                    scaled = pygame.transform.scale(native, target_size)
                    self._scaled_chunks[key] = scaled
                screen_x, screen_y = camera.world_to_screen(
                    chunk_x * self.chunk_pixels, chunk_y * self.chunk_pixels
                )
                surface.blit(scaled, (round(screen_x), round(screen_y)))


class WorldRenderer:
    PAUSE_ACTION = "toggle_pause"
    STEP_ACTION = "step"
    CAMERA_UP_ACTION = "camera_up"
    CAMERA_DOWN_ACTION = "camera_down"
    CAMERA_LEFT_ACTION = "camera_left"
    CAMERA_RIGHT_ACTION = "camera_right"
    CAMERA_ACTIONS = frozenset(
        (
            CAMERA_UP_ACTION,
            CAMERA_DOWN_ACTION,
            CAMERA_LEFT_ACTION,
            CAMERA_RIGHT_ACTION,
        )
    )

    def __init__(self, world: World) -> None:
        self.terrain = TerrainRenderer(world.terrain)
        self.font = pygame.font.Font(None, 24)
        self.control_font = pygame.font.Font(None, 28)

    @staticmethod
    def control_rects(surface_size: tuple[int, int]) -> dict[str, pygame.Rect]:
        surface_width, surface_height = surface_size
        margin = 12
        gap = 8
        height = 40
        pause_width = 112
        step_width = 76
        total_width = pause_width + gap + step_width
        left = max(margin, surface_width - margin - total_width)
        controls = {
            WorldRenderer.PAUSE_ACTION: pygame.Rect(left, margin, pause_width, height),
            WorldRenderer.STEP_ACTION: pygame.Rect(
                left + pause_width + gap, margin, step_width, height
            ),
        }
        direction_size = 42
        direction_gap = 4
        direction_left = margin
        direction_bottom = max(margin, surface_height - margin - direction_size)
        direction_middle = direction_left + direction_size + direction_gap
        direction_right = direction_middle + direction_size + direction_gap
        direction_top = max(margin, direction_bottom - direction_size - direction_gap)
        controls.update(
            {
                WorldRenderer.CAMERA_UP_ACTION: pygame.Rect(
                    direction_middle, direction_top, direction_size, direction_size
                ),
                WorldRenderer.CAMERA_LEFT_ACTION: pygame.Rect(
                    direction_left, direction_bottom, direction_size, direction_size
                ),
                WorldRenderer.CAMERA_DOWN_ACTION: pygame.Rect(
                    direction_middle, direction_bottom, direction_size, direction_size
                ),
                WorldRenderer.CAMERA_RIGHT_ACTION: pygame.Rect(
                    direction_right, direction_bottom, direction_size, direction_size
                ),
            }
        )
        return controls

    def control_at(
        self, position: tuple[int, int], surface_size: tuple[int, int]
    ) -> str | None:
        for action, rect in self.control_rects(surface_size).items():
            if rect.collidepoint(position):
                return action
        return None

    @staticmethod
    def details_rect(surface_size: tuple[int, int], field_count: int) -> pygame.Rect:
        surface_width, surface_height = surface_size
        margin = 12
        width = min(320, max(180, surface_width - margin * 2))
        height = max(1, min(surface_height - 76, 70 + field_count * 23))
        return pygame.Rect(max(margin, surface_width - width - margin), 64, width, height)

    def details_panel_at(
        self,
        position: tuple[int, int],
        surface_size: tuple[int, int],
        field_count: int,
    ) -> bool:
        return self.details_rect(surface_size, field_count).collidepoint(position)

    def draw(
        self,
        surface: pygame.Surface,
        world: World,
        camera: Camera2D,
        alpha: float,
    ) -> int:
        surface.fill((15, 18, 22))
        self.terrain.draw(surface, camera)
        left, top, right, bottom = camera.visible_rect(padding=8.0)
        visible = world.query_rect(left, top, right, bottom)
        for entity in visible:
            entity.draw(surface, camera, alpha)
        return len(visible)

    def draw_hud(
        self,
        surface: pygame.Surface,
        world: World,
        clock: FixedStepClock,
        fps: float,
        update_ms: float,
        render_ms: float,
        visible_count: int,
    ) -> None:
        state = "PAUSED" if clock.paused else "RUNNING"
        lines = (
            f"Seed {world.seed}   Tick {world.tick_index}   {state}   {clock.speed:g}x",
            f"Entities {world.entity_count:,} ({visible_count:,} visible)   FPS {fps:5.1f}",
            f"Update {update_ms:6.2f} ms   Render {render_ms:6.2f} ms",
        )
        width = max(self.font.size(line)[0] for line in lines) + 20
        panel = pygame.Surface((width, 72), pygame.SRCALPHA)
        panel.fill((8, 10, 13, 190))
        for index, line in enumerate(lines):
            panel.blit(self.font.render(line, True, (238, 241, 244)), (10, 6 + index * 21))
        surface.blit(panel, (10, 10))

    def draw_controls(
        self,
        surface: pygame.Surface,
        clock: FixedStepClock,
        mouse_position: tuple[int, int],
    ) -> None:
        labels = {
            self.PAUSE_ACTION: "Resume" if clock.paused else "Pause",
            self.STEP_ACTION: "Step",
            self.CAMERA_UP_ACTION: "^",
            self.CAMERA_DOWN_ACTION: "v",
            self.CAMERA_LEFT_ACTION: "<",
            self.CAMERA_RIGHT_ACTION: ">",
        }
        for action, rect in self.control_rects(surface.get_size()).items():
            hovered = rect.collidepoint(mouse_position)
            if action == self.PAUSE_ACTION and clock.paused:
                fill = (54, 132, 91) if not hovered else (66, 153, 107)
            else:
                fill = (52, 65, 81) if not hovered else (69, 85, 104)
            pygame.draw.rect(surface, fill, rect, border_radius=7)
            pygame.draw.rect(surface, (182, 194, 207), rect, width=1, border_radius=7)
            rendered = self.control_font.render(labels[action], True, (245, 247, 250))
            surface.blit(rendered, rendered.get_rect(center=rect.center))

    def draw_entity_inspector(
        self,
        surface: pygame.Surface,
        world: World,
        camera: Camera2D,
        entity: Entity,
        alpha: float,
        following: bool,
    ) -> None:
        render_x = entity.previous_x + (entity.x - entity.previous_x) * alpha
        render_y = entity.previous_y + (entity.y - entity.previous_y) * alpha
        screen_x, screen_y = camera.world_to_screen(render_x, render_y)
        highlight_radius = max(8, round((entity.radius + 4.0) * camera.zoom))
        pygame.draw.circle(
            surface,
            (255, 226, 92),
            (round(screen_x), round(screen_y)),
            highlight_radius,
            width=2,
        )
        pygame.draw.line(
            surface,
            (255, 226, 92),
            (round(screen_x) - highlight_radius - 4, round(screen_y)),
            (round(screen_x) + highlight_radius + 4, round(screen_y)),
            width=1,
        )

        fields = entity.inspection_fields() + (
            ("Terrain", world.terrain.terrain_at(entity.x, entity.y).name.title()),
            ("Camera", "Following" if following else "Free"),
        )
        panel_rect = self.details_rect(surface.get_size(), len(fields))
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((8, 10, 13, 220))
        pygame.draw.rect(panel, (126, 139, 153), panel.get_rect(), width=1, border_radius=7)

        title = self.control_font.render("Selected entity", True, (255, 226, 92))
        panel.blit(title, (12, 9))
        for index, (label, value) in enumerate(fields):
            line = self.font.render(f"{label}: {value}", True, (232, 237, 242))
            panel.blit(line, (12, 40 + index * 23))
        hint = self.font.render("F: follow   C: clear selection", True, (166, 178, 190))
        panel.blit(hint, (12, panel.get_height() - 25))
        surface.blit(panel, panel_rect)
