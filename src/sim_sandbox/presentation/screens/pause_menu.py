"""Pause overlay shown above a gameplay screen."""

from __future__ import annotations

import pygame


class PauseMenuScreen:
    ACTIONS = ("resume", "restart", "main_hub", "quit")
    LABELS = {
        "resume": "Resume",
        "restart": "Restart",
        "main_hub": "Main Hub",
        "quit": "Quit",
    }

    def __init__(self) -> None:
        self.selected_index = 0
        self.title_font = pygame.font.Font(None, 52)
        self.font = pygame.font.Font(None, 30)

    def button_rects(self, surface_size: tuple[int, int]) -> dict[str, pygame.Rect]:
        width, height = surface_size
        button_width = min(310, width - 48)
        left = width // 2 - button_width // 2
        top = height // 2 - 95
        return {
            action: pygame.Rect(left, top + index * 57, button_width, 45)
            for index, action in enumerate(self.ACTIONS)
        }

    def handle_event(
        self, event: pygame.event.Event, surface_size: tuple[int, int]
    ) -> str | None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "resume"
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.ACTIONS)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.ACTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.ACTIONS[self.selected_index]
        elif event.type == pygame.MOUSEMOTION:
            for index, rect in enumerate(self.button_rects(surface_size).values()):
                if rect.collidepoint(event.pos):
                    self.selected_index = index
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for action, rect in self.button_rects(surface_size).items():
                if rect.collidepoint(event.pos):
                    return action
        return None

    def draw(self, surface: pygame.Surface, mouse_position: tuple[int, int]) -> None:
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((5, 7, 10, 190))
        surface.blit(veil, (0, 0))
        title = self.title_font.render("Paused", True, (246, 248, 250))
        surface.blit(title, title.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 145)))
        for index, (action, rect) in enumerate(self.button_rects(surface.get_size()).items()):
            hovered = rect.collidepoint(mouse_position)
            selected = index == self.selected_index
            fill = (63, 101, 125) if selected or hovered else (39, 47, 58)
            pygame.draw.rect(surface, fill, rect, border_radius=7)
            pygame.draw.rect(surface, (132, 154, 172), rect, width=1, border_radius=7)
            rendered = self.font.render(self.LABELS[action], True, (242, 245, 248))
            surface.blit(rendered, rendered.get_rect(center=rect.center))


__all__ = ["PauseMenuScreen"]
