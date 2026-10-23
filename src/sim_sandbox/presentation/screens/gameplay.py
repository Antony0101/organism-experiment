"""Gameplay screen: simulation controls, camera input, selection, and drawing."""

from __future__ import annotations

import math
import time
import traceback
from dataclasses import dataclass

import pygame

from ...engine.camera import Camera2D
from ...engine.clock import FixedStepClock
from ...engine.entity import Entity
from ...game.world_definition import WorldSession
from ..rendering import WorldRenderer


@dataclass(frozen=True, slots=True)
class GameplayAction:
    kind: str


class GameplayScreen:
    """Own the live session and all Pygame behavior for playing it."""

    def __init__(self, session: WorldSession, surface_size: tuple[int, int]) -> None:
        self.session = session
        self.world = session.world
        self.camera = Camera2D(
            session.camera_position[0],
            session.camera_position[1],
            surface_size[0],
            surface_size[1],
            zoom=session.camera_zoom,
            world_width=self.world.terrain.pixel_width,
            world_height=self.world.terrain.pixel_height,
        )
        self.camera.clamp()
        self.renderer = WorldRenderer(self.world)
        self.simulation_clock = FixedStepClock()
        self.selected_entity_id: int | None = None
        self.follow_selected = False
        self.held_camera_action: str | None = None
        self.update_ms = 0.0
        self.render_ms = 0.0
        self.runtime_error: str | None = None
        self.runtime_traceback: str | None = None

    def close(self) -> None:
        self.session.close()

    def resize(self, width: int, height: int) -> None:
        self.camera.resize(width, height)

    def select_at_cursor(self, screen_position: tuple[int, int]) -> bool:
        x, y = self.camera.screen_to_world(*screen_position)
        candidates = self.world.query_radius(x, y, 12.0 / self.camera.zoom)
        if not candidates:
            return False
        nearest = min(
            candidates, key=lambda entity: (entity.x - x) ** 2 + (entity.y - y) ** 2
        )
        self.selected_entity_id = nearest.entity_id
        self.follow_selected = True
        return True

    def remove_at_cursor(self, screen_position: tuple[int, int]) -> None:
        x, y = self.camera.screen_to_world(*screen_position)
        candidates = self.world.query_radius(x, y, 12.0 / self.camera.zoom)
        if not candidates:
            return
        nearest = min(
            candidates, key=lambda entity: (entity.x - x) ** 2 + (entity.y - y) ** 2
        )
        self.world.remove(nearest.entity_id)
        self.world.flush()
        if nearest.entity_id == self.selected_entity_id:
            self.selected_entity_id = None
            self.follow_selected = False

    def _activate_control(self, action: str) -> None:
        if action == WorldRenderer.PAUSE_ACTION:
            self.simulation_clock.toggle_pause()
        elif action == WorldRenderer.STEP_ACTION:
            if not self.simulation_clock.paused:
                self.simulation_clock.toggle_pause()
            self.simulation_clock.request_step()

    def _nudge_camera(self, action: str, distance: float) -> None:
        directions = {
            WorldRenderer.CAMERA_UP_ACTION: (0.0, -1.0),
            WorldRenderer.CAMERA_DOWN_ACTION: (0.0, 1.0),
            WorldRenderer.CAMERA_LEFT_ACTION: (-1.0, 0.0),
            WorldRenderer.CAMERA_RIGHT_ACTION: (1.0, 0.0),
        }
        direction = directions.get(action)
        if direction is None:
            return
        self.follow_selected = False
        self.camera.pan(direction[0] * distance, direction[1] * distance)

    def handle_event(
        self, event: pygame.event.Event, surface_size: tuple[int, int]
    ) -> GameplayAction | None:
        if self.runtime_error is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return GameplayAction("restart")
                if event.key in (pygame.K_ESCAPE, pygame.K_h):
                    return GameplayAction("main_hub")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                buttons = self.error_button_rects(surface_size)
                if buttons["restart"].collidepoint(event.pos):
                    return GameplayAction("restart")
                if buttons["main_hub"].collidepoint(event.pos):
                    return GameplayAction("main_hub")
            return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.simulation_clock.toggle_pause()
            elif event.key == pygame.K_PERIOD:
                self.simulation_clock.request_step()
            elif event.key == pygame.K_f and self.selected_entity_id is not None:
                self.follow_selected = not self.follow_selected
            elif event.key == pygame.K_c:
                self.selected_entity_id = None
                self.follow_selected = False
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                speed_index = event.key - pygame.K_1
                self.simulation_clock.set_speed(FixedStepClock.SPEEDS[speed_index])
            elif event.key == pygame.K_r:
                return GameplayAction("restart")
            elif event.key == pygame.K_n:
                return GameplayAction("new_seed")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                action = self.renderer.control_at(event.pos, surface_size)
                if action is not None:
                    if action in WorldRenderer.CAMERA_ACTIONS:
                        self.held_camera_action = action
                        self._nudge_camera(action, 35.0 / self.camera.zoom)
                    else:
                        self._activate_control(action)
                elif (
                    self.selected_entity_id is not None
                    and (selected := self.world.get(self.selected_entity_id)) is not None
                    and self.renderer.details_panel_at(
                        event.pos,
                        surface_size,
                        len(selected.inspection_fields()) + 2,
                    )
                ):
                    pass
                else:
                    self.select_at_cursor(event.pos)
            elif event.button == 3:
                self.remove_at_cursor(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.held_camera_action = None
        elif event.type == pygame.MOUSEMOTION and event.buttons[1]:
            self.follow_selected = False
            self.camera.pan(-event.rel[0] / self.camera.zoom, -event.rel[1] / self.camera.zoom)
        elif event.type == pygame.MOUSEWHEEL:
            factor = 1.15**event.y
            self.camera.zoom_at(factor, *pygame.mouse.get_pos())
        return None

    def _move_camera(self, real_dt: float) -> None:
        keys = pygame.key.get_pressed()
        x_axis = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(
            keys[pygame.K_a] or keys[pygame.K_LEFT]
        )
        y_axis = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(
            keys[pygame.K_w] or keys[pygame.K_UP]
        )
        if x_axis or y_axis:
            self.follow_selected = False
            pan_speed = 700.0 / self.camera.zoom
            self.camera.pan(x_axis * pan_speed * real_dt, y_axis * pan_speed * real_dt)
        if self.held_camera_action is not None:
            pan_speed = 700.0 / self.camera.zoom
            self._nudge_camera(self.held_camera_action, pan_speed * real_dt)

    def follow_selected_entity(self, real_dt: float) -> Entity | None:
        if self.selected_entity_id is None:
            return None
        entity = self.world.get(self.selected_entity_id)
        if entity is None:
            self.selected_entity_id = None
            self.follow_selected = False
            return None
        if self.follow_selected:
            alpha = self.simulation_clock.alpha
            target_x = entity.previous_x + (entity.x - entity.previous_x) * alpha
            target_y = entity.previous_y + (entity.y - entity.previous_y) * alpha
            smoothing = 1.0 - math.exp(-8.0 * min(real_dt, 0.25))
            self.camera.pan(
                (target_x - self.camera.x) * smoothing,
                (target_y - self.camera.y) * smoothing,
            )
        return entity

    @staticmethod
    def _smoothed(previous: float, current: float) -> float:
        return current if previous == 0.0 else previous * 0.9 + current * 0.1

    def update(self, real_dt: float) -> Entity | None:
        if self.runtime_error is not None:
            return self.follow_selected_entity(0.0)
        self._move_camera(real_dt)
        update_start = time.perf_counter()
        try:
            for _ in range(self.simulation_clock.consume_steps(real_dt)):
                self.world.step(self.simulation_clock.fixed_dt)
        except Exception as exc:
            self.runtime_error = f"{type(exc).__name__}: {exc}"
            self.runtime_traceback = traceback.format_exc()
            if not self.simulation_clock.paused:
                self.simulation_clock.toggle_pause()
        measured_update = (time.perf_counter() - update_start) * 1000.0
        self.update_ms = self._smoothed(self.update_ms, measured_update)
        return self.follow_selected_entity(real_dt)

    def draw(
        self,
        surface: pygame.Surface,
        fps: float,
        mouse_position: tuple[int, int],
        selected_entity: Entity | None = None,
    ) -> None:
        render_start = time.perf_counter()
        visible_count = self.renderer.draw(
            surface, self.world, self.camera, self.simulation_clock.alpha
        )
        measured_render = (time.perf_counter() - render_start) * 1000.0
        self.render_ms = self._smoothed(self.render_ms, measured_render)
        self.renderer.draw_hud(
            surface,
            self.world,
            self.simulation_clock,
            fps,
            self.update_ms,
            self.render_ms,
            visible_count,
        )
        self.renderer.draw_controls(surface, self.simulation_clock, mouse_position)
        if selected_entity is None and self.selected_entity_id is not None:
            selected_entity = self.world.get(self.selected_entity_id)
        if selected_entity is not None:
            self.renderer.draw_entity_inspector(
                surface,
                self.world,
                self.camera,
                selected_entity,
                self.simulation_clock.alpha,
                self.follow_selected,
            )
        if self.runtime_error is not None:
            self.draw_error_overlay(surface, mouse_position)

    @staticmethod
    def error_button_rects(surface_size: tuple[int, int]) -> dict[str, pygame.Rect]:
        width, height = surface_size
        return {
            "restart": pygame.Rect(width // 2 - 190, height // 2 + 76, 180, 44),
            "main_hub": pygame.Rect(width // 2 + 10, height // 2 + 76, 180, 44),
        }

    def draw_error_overlay(self, surface: pygame.Surface, mouse: tuple[int, int]) -> None:
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((7, 8, 12, 215))
        surface.blit(veil, (0, 0))
        title_font = pygame.font.Font(None, 46)
        font = pygame.font.Font(None, 24)
        title = title_font.render("Simulation callback failed", True, (247, 126, 126))
        surface.blit(title, title.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 80)))
        message = self.runtime_error or "Unknown error"
        if len(message) > 110:
            message = message[:107] + "..."
        rendered = font.render(message, True, (231, 235, 240))
        surface.blit(rendered, rendered.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 28)))
        hint = font.render("The simulation is paused. Restart the world or return to the hub.", True, (154, 169, 184))
        surface.blit(hint, hint.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 + 12)))
        for action, rect in self.error_button_rects(surface.get_size()).items():
            fill = (56, 90, 112) if rect.collidepoint(mouse) else (38, 48, 59)
            pygame.draw.rect(surface, fill, rect, border_radius=7)
            pygame.draw.rect(surface, (113, 142, 164), rect, 1, border_radius=7)
            label = "Restart" if action == "restart" else "Main Hub"
            text = font.render(label, True, (242, 246, 249))
            surface.blit(text, text.get_rect(center=rect.center))


__all__ = ["GameplayAction", "GameplayScreen"]
