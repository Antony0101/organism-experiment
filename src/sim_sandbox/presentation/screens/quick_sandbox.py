"""Friendly launcher for ad-hoc entity mixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from ...game.entity_projects.registry import EntityProjectStore
from ...game.quick_sandbox import (
    TERRAIN_PRESETS,
    QuickSandboxOptions,
    SandboxPopulation,
)
from ...game.world_definition import MAX_ENTITY_COUNT, MAX_SEED


@dataclass(frozen=True, slots=True)
class QuickSandboxAction:
    kind: str
    options: QuickSandboxOptions | None = None


class QuickSandboxScreen:
    def __init__(
        self,
        content_root: Path | str = Path("content/entities"),
        *,
        initial_entity_id: str | None = None,
        initial_terrain: str = "standard",
    ) -> None:
        self.store = EntityProjectStore(content_root)
        self.catalog = self.store.scan()
        self.entity_ids = [project.definition.id for project in self.catalog.projects]
        self.selected_entity = (
            self.entity_ids.index(initial_entity_id)
            if initial_entity_id in self.entity_ids
            else 0
        )
        self.terrain = initial_terrain if initial_terrain in TERRAIN_PRESETS else "standard"
        self.seed_text = "1"
        self.count_text = "10"
        self.focus = "seed"
        self.rows: list[SandboxPopulation] = []
        self.selected_row = -1
        self.status = "Choose an entity, enter a count, and add up to eight rows. Empty worlds are allowed."
        self.status_error = False
        self.title_font = pygame.font.Font(None, 50)
        self.heading_font = pygame.font.Font(None, 31)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)

    def _layout(self, size: tuple[int, int]) -> dict[str, pygame.Rect]:
        width, height = size
        left = max(30, width // 2 - 500)
        return {
            "back": pygame.Rect(left, 30, 100, 40),
            "seed": pygame.Rect(left, 128, 230, 40),
            "compact": pygame.Rect(left + 260, 128, 125, 40),
            "standard": pygame.Rect(left + 395, 128, 125, 40),
            "large": pygame.Rect(left + 530, 128, 125, 40),
            "entities": pygame.Rect(left, 220, 430, max(180, height - 350)),
            "count": pygame.Rect(left + 450, 220, 150, 40),
            "add": pygame.Rect(left + 450, 272, 150, 42),
            "rows": pygame.Rect(left + 620, 220, 370, max(180, height - 350)),
            "remove": pygame.Rect(left + 620, height - 115, 150, 40),
            "start": pygame.Rect(left + 790, height - 115, 200, 46),
        }

    def _entity_row_rects(self, rect: pygame.Rect) -> list[pygame.Rect]:
        return [pygame.Rect(rect.x + 8, rect.y + 8 + i * 36, rect.width - 16, 32) for i in range(min(len(self.entity_ids), max(1, (rect.height - 16) // 36)))]

    def _population_rects(self, rect: pygame.Rect) -> list[pygame.Rect]:
        return [pygame.Rect(rect.x + 8, rect.y + 8 + i * 36, rect.width - 16, 32) for i in range(len(self.rows))]

    def validation(self) -> tuple[QuickSandboxOptions | None, str | None]:
        try:
            seed = int(self.seed_text)
        except ValueError:
            return None, "Seed must be a whole number."
        if not 0 <= seed <= MAX_SEED:
            return None, f"Seed must be 0..{MAX_SEED:,}."
        try:
            return QuickSandboxOptions(self.terrain, seed, tuple(self.rows)), None
        except ValueError as exc:
            return None, str(exc)

    def _edit(self, event: pygame.event.Event) -> None:
        if self.focus not in ("seed", "count"):
            return
        value = self.seed_text if self.focus == "seed" else self.count_text
        if event.key == pygame.K_BACKSPACE:
            value = value[:-1]
        elif event.key == pygame.K_DELETE:
            value = ""
        elif getattr(event, "unicode", "").isdigit() and len(value) < 10:
            value += event.unicode
        if self.focus == "seed":
            self.seed_text = value
        else:
            self.count_text = value

    def _add(self) -> None:
        try:
            if not self.entity_ids:
                raise ValueError("Create an entity project in Entity Studio first.")
            if len(self.rows) >= 8:
                raise ValueError("Only eight population rows are supported.")
            count = int(self.count_text)
            row = SandboxPopulation(self.entity_ids[self.selected_entity], count)
            if sum(item.count for item in self.rows) + count > MAX_ENTITY_COUNT:
                raise ValueError(f"Total population cannot exceed {MAX_ENTITY_COUNT:,}.")
            self.rows.append(row)
            self.selected_row = len(self.rows) - 1
            self.status = f"Added {count:,} × {row.entity_id}."
            self.status_error = False
        except Exception as exc:
            self.status, self.status_error = str(exc), True

    def handle_event(self, event: pygame.event.Event, size: tuple[int, int]) -> QuickSandboxAction | None:
        rects = self._layout(size)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return QuickSandboxAction("back")
            if event.key == pygame.K_TAB:
                self.focus = "count" if self.focus == "seed" else "seed"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.focus == "count":
                    self._add()
                else:
                    options, error = self.validation()
                    if options:
                        return QuickSandboxAction("start", options)
                    self.status, self.status_error = error or "Invalid options", True
            elif event.key == pygame.K_UP and self.entity_ids:
                self.selected_entity = (self.selected_entity - 1) % len(self.entity_ids)
            elif event.key == pygame.K_DOWN and self.entity_ids:
                self.selected_entity = (self.selected_entity + 1) % len(self.entity_ids)
            else:
                self._edit(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if rects["back"].collidepoint(event.pos):
                return QuickSandboxAction("back")
            for terrain in TERRAIN_PRESETS:
                if rects[terrain].collidepoint(event.pos):
                    self.terrain = terrain
                    return None
            if rects["seed"].collidepoint(event.pos):
                self.focus = "seed"
            elif rects["count"].collidepoint(event.pos):
                self.focus = "count"
            elif rects["add"].collidepoint(event.pos):
                self._add()
            elif rects["remove"].collidepoint(event.pos) and self.selected_row >= 0:
                self.rows.pop(self.selected_row)
                self.selected_row = min(self.selected_row, len(self.rows) - 1)
            elif rects["start"].collidepoint(event.pos):
                options, error = self.validation()
                if options:
                    return QuickSandboxAction("start", options)
                self.status, self.status_error = error or "Invalid options", True
            else:
                for index, row in enumerate(self._entity_row_rects(rects["entities"])):
                    if row.collidepoint(event.pos):
                        self.selected_entity = index
                        break
                for index, row in enumerate(self._population_rects(rects["rows"])):
                    if row.collidepoint(event.pos):
                        self.selected_row = index
                        break
        return None

    def draw(self, surface: pygame.Surface, mouse: tuple[int, int]) -> None:
        surface.fill((17, 21, 27))
        rects = self._layout(surface.get_size())
        surface.blit(self.title_font.render("Quick Sandbox", True, (242, 246, 250)), (rects["back"].right + 25, 31))
        self._draw_button(surface, rects["back"], "Main Hub", mouse)
        surface.blit(self.font.render("Seed", True, (196, 207, 218)), (rects["seed"].x, rects["seed"].y - 27))
        self._draw_entry(surface, rects["seed"], self.seed_text, self.focus == "seed")
        for terrain in TERRAIN_PRESETS:
            self._draw_button(surface, rects[terrain], terrain.title(), mouse, terrain == self.terrain)
        entities = rects["entities"]
        rows = rects["rows"]
        for panel in (entities, rows):
            pygame.draw.rect(surface, (24, 29, 37), panel, border_radius=7)
            pygame.draw.rect(surface, (67, 80, 94), panel, 1, border_radius=7)
        surface.blit(self.heading_font.render("Entity projects", True, (231, 236, 241)), (entities.x, entities.y - 36))
        surface.blit(self.heading_font.render("Population mix", True, (231, 236, 241)), (rows.x, rows.y - 36))
        for index, (entity_id, row) in enumerate(zip(self.entity_ids, self._entity_row_rects(entities))):
            if index == self.selected_entity:
                pygame.draw.rect(surface, (46, 74, 94), row, border_radius=4)
            surface.blit(self.font.render(entity_id, True, (224, 231, 237)), (row.x + 8, row.y + 6))
        if not self.entity_ids:
            surface.blit(self.small_font.render("No entity projects yet.", True, (231, 180, 92)), (entities.x + 12, entities.y + 14))
        surface.blit(self.font.render("Count", True, (196, 207, 218)), (rects["count"].x, rects["count"].y - 27))
        self._draw_entry(surface, rects["count"], self.count_text, self.focus == "count")
        self._draw_button(surface, rects["add"], "Add Row", mouse)
        for index, (population, row) in enumerate(zip(self.rows, self._population_rects(rows))):
            if index == self.selected_row:
                pygame.draw.rect(surface, (46, 74, 94), row, border_radius=4)
            surface.blit(self.font.render(f"{population.entity_id}  ×  {population.count:,}", True, (224, 231, 237)), (row.x + 8, row.y + 6))
        self._draw_button(surface, rects["remove"], "Remove Row", mouse)
        self._draw_button(surface, rects["start"], "Start Sandbox", mouse, self.validation()[0] is not None)
        status_color = (239, 104, 104) if self.status_error else (145, 190, 164)
        surface.blit(self.small_font.render(self.status, True, status_color), (rects["seed"].x, surface.get_height() - 32))

    def _draw_entry(self, surface: pygame.Surface, rect: pygame.Rect, text: str, focused: bool) -> None:
        pygame.draw.rect(surface, (24, 29, 37), rect, border_radius=6)
        pygame.draw.rect(surface, (112, 197, 231) if focused else (82, 95, 109), rect, 2 if focused else 1, border_radius=6)
        surface.blit(self.font.render(text, True, (238, 242, 246)), (rect.x + 10, rect.y + 9))

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str, mouse: tuple[int, int], selected: bool = False) -> None:
        fill = (48, 126, 88) if selected else ((49, 69, 87) if rect.collidepoint(mouse) else (37, 47, 58))
        pygame.draw.rect(surface, fill, rect, border_radius=6)
        pygame.draw.rect(surface, (106, 135, 158), rect, 1, border_radius=6)
        rendered = self.font.render(label, True, (242, 246, 249))
        surface.blit(rendered, rendered.get_rect(center=rect.center))


__all__ = ["QuickSandboxAction", "QuickSandboxScreen"]
