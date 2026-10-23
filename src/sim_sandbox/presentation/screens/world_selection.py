"""Startup screen for selecting and configuring a discovered world."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from ...game.world_definition import (
    MAX_ENTITY_COUNT,
    MAX_SEED,
    WorldDefinition,
    WorldLaunchOptions,
)
from ...game.worlds.discovery import WorldLoadError


@dataclass(frozen=True, slots=True)
class WorldSelectionAction:
    kind: str
    world_id: str | None = None
    options: WorldLaunchOptions | None = None


class WorldSelectionScreen:
    FIELDS = ("seed", "population", "start")

    def __init__(
        self,
        definitions: tuple[WorldDefinition, ...],
        errors: tuple[WorldLoadError, ...] = (),
        seed_override: int | None = None,
        entity_count_override: int | None = None,
    ) -> None:
        self.definitions = definitions
        self.errors = errors
        self.selected_index = 0
        self.focus = "seed"
        self.font = pygame.font.Font(None, 25)
        self.small_font = pygame.font.Font(None, 21)
        self.title_font = pygame.font.Font(None, 48)
        self.heading_font = pygame.font.Font(None, 31)
        if definitions:
            definition = definitions[0]
            self.seed_text = str(
                definition.default_seed if seed_override is None else seed_override
            )
            self.population_text = str(
                definition.default_entity_count
                if entity_count_override is None
                else entity_count_override
            )
        else:
            self.seed_text = ""
            self.population_text = ""

    @property
    def selected_definition(self) -> WorldDefinition | None:
        if not self.definitions:
            return None
        return self.definitions[self.selected_index]

    def _select(self, index: int) -> None:
        if not self.definitions:
            return
        self.selected_index = index % len(self.definitions)
        definition = self.definitions[self.selected_index]
        self.seed_text = str(definition.default_seed)
        self.population_text = str(definition.default_entity_count)

    def validation(self) -> tuple[WorldLaunchOptions | None, str | None]:
        if self.selected_definition is None:
            return None, "No valid worlds were discovered."
        try:
            seed = int(self.seed_text)
        except ValueError:
            return None, "Seed must be a whole number."
        try:
            population = int(self.population_text)
        except ValueError:
            return None, "Population must be a whole number."
        if not 0 <= seed <= MAX_SEED:
            return None, f"Seed must be between 0 and {MAX_SEED:,}."
        if not 0 <= population <= MAX_ENTITY_COUNT:
            return None, f"Population must be between 0 and {MAX_ENTITY_COUNT:,}."
        return WorldLaunchOptions(seed, population), None

    def card_rects(self, surface_size: tuple[int, int]) -> list[pygame.Rect]:
        width, _ = surface_size
        left = max(24, width // 2 - 440)
        card_width = min(560, max(260, width - left - 330))
        return [
            pygame.Rect(left, 110 + index * 105, card_width, 90)
            for index in range(len(self.definitions))
        ]

    def input_rects(self, surface_size: tuple[int, int]) -> dict[str, pygame.Rect]:
        width, height = surface_size
        panel_left = max(width // 2 + 170, width - 300)
        panel_left = min(panel_left, max(24, width - 276))
        top = min(150, max(92, height // 4))
        return {
            "seed": pygame.Rect(panel_left, top + 34, 250, 42),
            "population": pygame.Rect(panel_left, top + 124, 250, 42),
            "start": pygame.Rect(panel_left, top + 204, 250, 48),
            "editor": pygame.Rect(panel_left, top + 262, 250, 44),
        }

    def _launch_action(self) -> WorldSelectionAction | None:
        options, error = self.validation()
        definition = self.selected_definition
        if error is not None or options is None or definition is None:
            return None
        return WorldSelectionAction("start", definition.id, options)

    def _edit_focused(self, event: pygame.event.Event) -> None:
        if self.focus not in ("seed", "population"):
            return
        text = self.seed_text if self.focus == "seed" else self.population_text
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
        elif event.key == pygame.K_DELETE:
            text = ""
        elif (typed := getattr(event, "unicode", "")).isdigit() and len(text) < 10:
            text += typed
        if self.focus == "seed":
            self.seed_text = text
        else:
            self.population_text = text

    def handle_event(
        self, event: pygame.event.Event, surface_size: tuple[int, int]
    ) -> WorldSelectionAction | None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return WorldSelectionAction("back")
            if event.key == pygame.K_e and self.focus not in ("seed", "population"):
                return WorldSelectionAction("editor")
            if event.key == pygame.K_TAB:
                offset = -1 if event.mod & pygame.KMOD_SHIFT else 1
                self.focus = self.FIELDS[(self.FIELDS.index(self.focus) + offset) % len(self.FIELDS)]
            elif event.key == pygame.K_UP:
                self._select(self.selected_index - 1)
            elif event.key == pygame.K_DOWN:
                self._select(self.selected_index + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._launch_action()
            else:
                self._edit_focused(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self.card_rects(surface_size)):
                if rect.collidepoint(event.pos):
                    self._select(index)
                    return None
            for field, rect in self.input_rects(surface_size).items():
                if rect.collidepoint(event.pos):
                    self.focus = field
                    if field == "start":
                        return self._launch_action()
                    if field == "editor":
                        return WorldSelectionAction("editor")
                    return None
        return None

    def draw(self, surface: pygame.Surface, mouse_position: tuple[int, int]) -> None:
        surface.fill((17, 21, 27))
        width, height = surface.get_size()
        title = self.title_font.render("Choose a world", True, (241, 244, 248))
        surface.blit(title, (max(24, width // 2 - 440), 38))

        for index, (definition, rect) in enumerate(
            zip(self.definitions, self.card_rects(surface.get_size()), strict=True)
        ):
            selected = index == self.selected_index
            hovered = rect.collidepoint(mouse_position)
            fill = (47, 69, 86) if selected else ((39, 47, 59) if hovered else (30, 36, 45))
            border = (101, 190, 225) if selected else (83, 96, 111)
            pygame.draw.rect(surface, fill, rect, border_radius=9)
            pygame.draw.rect(surface, border, rect, width=2 if selected else 1, border_radius=9)
            surface.blit(self.heading_font.render(definition.name, True, (243, 246, 249)), (rect.x + 15, rect.y + 10))
            description = self.small_font.render(definition.description, True, (185, 196, 207))
            surface.blit(description, (rect.x + 15, rect.y + 43))
            defaults = self.small_font.render(
                f"ID: {definition.id}   Defaults: seed {definition.default_seed}, {definition.default_entity_count:,} entities",
                True,
                (143, 159, 175),
            )
            surface.blit(defaults, (rect.x + 15, rect.y + 65))

        rects = self.input_rects(surface.get_size())
        label_color = (203, 212, 221)
        surface.blit(self.font.render("Seed", True, label_color), (rects["seed"].x, rects["seed"].y - 27))
        surface.blit(
            self.font.render("Population", True, label_color),
            (rects["population"].x, rects["population"].y - 27),
        )
        for field, value in (("seed", self.seed_text), ("population", self.population_text)):
            rect = rects[field]
            pygame.draw.rect(surface, (24, 29, 37), rect, border_radius=6)
            color = (112, 197, 231) if self.focus == field else (94, 106, 120)
            pygame.draw.rect(surface, color, rect, width=2 if self.focus == field else 1, border_radius=6)
            rendered = self.font.render(value, True, (239, 242, 246))
            surface.blit(rendered, (rect.x + 10, rect.y + 10))

        options, validation_error = self.validation()
        start_rect = rects["start"]
        enabled = options is not None
        hovered = start_rect.collidepoint(mouse_position)
        if enabled:
            fill = (48, 135, 89) if not hovered else (57, 158, 104)
        else:
            fill = (59, 62, 67)
        pygame.draw.rect(surface, fill, start_rect, border_radius=7)
        rendered = self.heading_font.render("Start", True, (247, 249, 251) if enabled else (150, 154, 159))
        surface.blit(rendered, rendered.get_rect(center=start_rect.center))
        if self.focus == "start":
            pygame.draw.rect(surface, (112, 197, 231), start_rect, width=2, border_radius=7)

        editor_rect = rects["editor"]
        editor_fill = (47, 67, 91) if not editor_rect.collidepoint(mouse_position) else (58, 83, 112)
        pygame.draw.rect(surface, editor_fill, editor_rect, border_radius=7)
        pygame.draw.rect(surface, (112, 143, 174), editor_rect, width=1, border_radius=7)
        editor_text = self.font.render("Entity Editor", True, (242, 246, 250))
        surface.blit(editor_text, editor_text.get_rect(center=editor_rect.center))

        message_y = editor_rect.bottom + 8
        if validation_error:
            surface.blit(self.small_font.render(validation_error, True, (239, 112, 112)), (start_rect.x, message_y))
        elif self.errors:
            text = f"{len(self.errors)} world package(s) could not be loaded."
            surface.blit(self.small_font.render(text, True, (231, 180, 92)), (start_rect.x, message_y))

        hint = self.small_font.render(
            "Mouse or Up/Down: select   Tab: fields   Enter: start   Entity Editor: create content",
            True,
            (139, 152, 166),
        )
        surface.blit(hint, (max(24, width // 2 - hint.get_width() // 2), height - 35))


__all__ = ["WorldSelectionAction", "WorldSelectionScreen"]
