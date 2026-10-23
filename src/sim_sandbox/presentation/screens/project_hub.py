"""Central launch screen for worlds, sandboxes, and content studios."""

from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass(frozen=True, slots=True)
class ProjectHubAction:
    kind: str


class ProjectHubScreen:
    ACTIONS = ("worlds", "sandbox", "entity_editor", "behavior_editor", "quit")
    CARDS = {
        "worlds": ("Play Worlds", "Choose a packaged scenario and launch its simulation."),
        "sandbox": ("Quick Sandbox", "Mix entity projects on procedural terrain without writing a world factory."),
        "entity_editor": ("Entity Studio", "Design entity appearance, state, scripts, and behavior stacks."),
        "behavior_editor": ("Behavior Studio", "Browse presets or author reusable configurable components."),
        "quit": ("Quit", "Close the sandbox."),
    }

    def __init__(self, recent: list[dict[str, str]] | None = None) -> None:
        self.selected_index = 0
        self.recent = recent or []
        self.title_font = pygame.font.Font(None, 58)
        self.heading_font = pygame.font.Font(None, 34)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)

    def card_rects(self, size: tuple[int, int]) -> dict[str, pygame.Rect]:
        width, height = size
        card_width = min(680, width - 80)
        left = width // 2 - card_width // 2
        top = max(115, height // 2 - 235)
        return {
            action: pygame.Rect(left, top + index * 88, card_width, 72)
            for index, action in enumerate(self.ACTIONS)
        }

    def handle_event(self, event: pygame.event.Event, size: tuple[int, int]) -> ProjectHubAction | None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return ProjectHubAction("quit")
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.ACTIONS)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.ACTIONS)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return ProjectHubAction(self.ACTIONS[self.selected_index])
        elif event.type == pygame.MOUSEMOTION:
            for index, rect in enumerate(self.card_rects(size).values()):
                if rect.collidepoint(event.pos):
                    self.selected_index = index
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for action, rect in self.card_rects(size).items():
                if rect.collidepoint(event.pos):
                    return ProjectHubAction(action)
        return None

    def draw(self, surface: pygame.Surface, mouse: tuple[int, int]) -> None:
        surface.fill((15, 19, 25))
        width, height = surface.get_size()
        title = self.title_font.render("Simulation Project Hub", True, (242, 246, 250))
        surface.blit(title, title.get_rect(center=(width // 2, 56)))
        subtitle = self.font.render(
            "Build reusable entities and behaviors, or launch a deterministic world.",
            True, (150, 166, 181),
        )
        surface.blit(subtitle, subtitle.get_rect(center=(width // 2, 91)))
        for index, (action, rect) in enumerate(self.card_rects(surface.get_size()).items()):
            selected = index == self.selected_index
            hovered = rect.collidepoint(mouse)
            fill = (43, 69, 88) if selected else ((35, 45, 56) if hovered else (26, 32, 40))
            border = (103, 191, 227) if selected else (65, 78, 92)
            pygame.draw.rect(surface, fill, rect, border_radius=9)
            pygame.draw.rect(surface, border, rect, width=2 if selected else 1, border_radius=9)
            name, description = self.CARDS[action]
            surface.blit(self.heading_font.render(name, True, (243, 246, 249)), (rect.x + 18, rect.y + 9))
            surface.blit(self.small_font.render(description, True, (175, 187, 199)), (rect.x + 20, rect.y + 43))
        if self.recent:
            recent = "Recent: " + "   ·   ".join(
                f"{item.get('kind', 'project')}: {item.get('id', '?')}" for item in self.recent[:3]
            )
            rendered = self.small_font.render(recent, True, (126, 142, 158))
            surface.blit(rendered, rendered.get_rect(center=(width // 2, height - 26)))


__all__ = ["ProjectHubAction", "ProjectHubScreen"]
