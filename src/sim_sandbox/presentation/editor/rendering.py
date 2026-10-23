"""Declarative rendering helpers for entity editor design and preview views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame

from ...engine.camera import Camera2D
from ...game.entity_projects.model import EntityProjectDefinition


class EntityAppearanceRenderer:
    def __init__(self) -> None:
        self._sprites: dict[Path, pygame.Surface] = {}

    def clear(self) -> None:
        self._sprites.clear()

    def _base_surface(
        self,
        definition: EntityProjectDefinition,
        project_directory: Path,
        color: tuple[int, int, int, int],
    ) -> pygame.Surface:
        appearance = definition.appearance
        if appearance.kind == "sprite":
            assert appearance.sprite is not None
            path = (project_directory / appearance.sprite).resolve()
            sprite = self._sprites.get(path)
            if sprite is None:
                sprite = pygame.image.load(str(path)).convert_alpha()
                self._sprites[path] = sprite
            result = sprite.copy()
            if color != (255, 255, 255, 255):
                tint = pygame.Surface(result.get_size(), pygame.SRCALPHA)
                tint.fill(color)
                result.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return result
        width = max(1, round(appearance.size[0]))
        height = max(1, round(appearance.size[1]))
        result = pygame.Surface((width, height), pygame.SRCALPHA)
        if appearance.kind == "circle":
            pygame.draw.ellipse(result, color, result.get_rect())
            if appearance.outline_width:
                pygame.draw.ellipse(
                    result,
                    appearance.outline_color,
                    result.get_rect(),
                    width=min(appearance.outline_width, max(1, min(width, height) // 2)),
                )
        else:
            pygame.draw.rect(result, color, result.get_rect())
            if appearance.outline_width:
                pygame.draw.rect(
                    result,
                    appearance.outline_color,
                    result.get_rect(),
                    width=min(appearance.outline_width, max(1, min(width, height) // 2)),
                )
        return result

    def draw_at(
        self,
        surface: pygame.Surface,
        definition: EntityProjectDefinition,
        project_directory: Path,
        center: tuple[float, float],
        *,
        color: tuple[int, int, int, int] | None = None,
        rotation_degrees: float | None = None,
        scale: tuple[float, float] | None = None,
        zoom: float = 1.0,
        visible: bool | None = None,
    ) -> None:
        appearance = definition.appearance
        if visible is None:
            visible = appearance.visible
        if not visible:
            return
        color = appearance.fill_color if color is None else color
        rotation_degrees = (
            appearance.rotation_degrees if rotation_degrees is None else rotation_degrees
        )
        scale = appearance.scale if scale is None else scale
        visual = self._base_surface(definition, project_directory, color)
        size = (
            max(1, round(visual.get_width() * scale[0] * zoom)),
            max(1, round(visual.get_height() * scale[1] * zoom)),
        )
        visual = pygame.transform.smoothscale(visual, size)
        if rotation_degrees:
            visual = pygame.transform.rotate(visual, -rotation_degrees)
        surface.blit(visual, visual.get_rect(center=(round(center[0]), round(center[1]))))

    def draw_snapshot(
        self,
        surface: pygame.Surface,
        definition: EntityProjectDefinition,
        project_directory: Path,
        camera: Camera2D,
        snapshot: dict[str, Any],
    ) -> None:
        visual = snapshot.get("visual", {})
        if not isinstance(visual, dict):
            return
        x = float(snapshot.get("x", 0.0))
        y = float(snapshot.get("y", 0.0))
        screen_position = camera.world_to_screen(x, y)
        raw_color = visual.get("color", definition.appearance.fill_color)
        color = tuple(int(channel) for channel in raw_color)
        raw_scale = visual.get("scale", definition.appearance.scale)
        scale = (float(raw_scale[0]), float(raw_scale[1]))
        self.draw_at(
            surface,
            definition,
            project_directory,
            screen_position,
            color=color,  # type: ignore[arg-type]
            rotation_degrees=float(
                visual.get("rotation_degrees", definition.appearance.rotation_degrees)
            ),
            scale=scale,
            zoom=camera.zoom,
            visible=bool(visual.get("visible", True)),
        )


__all__ = ["EntityAppearanceRenderer"]
