from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pygame_gui

from sim_sandbox.game.entity_projects.registry import EntityProjectStore
from sim_sandbox.game.worlds.discovery import discover_worlds
from sim_sandbox.presentation.app import AppMode, SimulationApp, build_parser
from sim_sandbox.presentation.screens.entity_editor import EntityEditorScreen
from sim_sandbox.presentation.screens.world_selection import WorldSelectionScreen


def test_world_selection_exposes_entity_editor_action() -> None:
    pygame.init()
    pygame.display.set_mode((900, 600))
    screen = WorldSelectionScreen(discover_worlds().definitions)
    editor_rect = screen.input_rects((900, 600))["editor"]
    action = screen.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=editor_rect.center),
        (900, 600),
    )
    assert action is not None
    assert action.kind == "editor"
    pygame.quit()


def test_editor_loads_edits_saves_and_draws(tmp_path: Path) -> None:
    pygame.init()
    surface = pygame.display.set_mode((1100, 720))
    store = EntityProjectStore(tmp_path / "entities")
    project = store.create_default("editor_dot", "Editor Dot")
    screen = EntityEditorScreen(surface.get_size(), store.root)
    screen._load_project(project)
    screen.name_entry.set_text("Edited Dot")
    screen.code_editor.set_text(
        "def update(entity, world, dt):\n    entity.visual.rotation_degrees += 30 * dt\n"
    )

    assert screen.save()
    screen.update(0.016)
    screen.draw(surface)
    reloaded = store.load("editor_dot")
    assert reloaded.definition.name == "Edited Dot"
    assert "rotation_degrees" in reloaded.behavior_source
    screen.close()
    pygame.quit()


def test_empty_editor_has_clear_first_project_state(tmp_path: Path) -> None:
    pygame.init()
    surface = pygame.display.set_mode((1100, 720))
    screen = EntityEditorScreen(surface.get_size(), tmp_path / "entities")

    assert screen.current is None
    assert screen.empty_new_button.visible
    assert not screen.preview_tab_button.is_enabled
    assert not screen.name_entry.visible
    assert "Create your first entity" in screen.status_message
    screen.draw(surface)

    screen.close()
    pygame.quit()


def test_opening_preview_applies_and_renders_a_snapshot(tmp_path: Path) -> None:
    pygame.init()
    surface = pygame.display.set_mode((1100, 720))
    store = EntityProjectStore(tmp_path / "entities")
    store.create_default("preview_dot", "Preview Dot")
    screen = EntityEditorScreen(surface.get_size(), store.root)

    screen._handle_gui_event(
        pygame.event.Event(
            pygame_gui.UI_BUTTON_PRESSED,
            ui_element=screen.preview_tab_button,
        )
    )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and screen.preview.status.snapshot is None:
        screen.update(0.016)
        time.sleep(0.01)

    assert screen.active_tab == "preview"
    assert screen.preview.status.loaded
    assert screen.preview.status.snapshot is not None
    assert len(screen.preview.status.snapshot["entities"]) == 1
    screen.draw(surface)

    screen.close()
    pygame.quit()


def test_cli_and_app_can_open_editor() -> None:
    assert build_parser().parse_args(["--editor"]).editor
    app = SimulationApp(open_editor=True, window_size=(800, 600))
    assert app.mode is AppMode.ENTITY_EDITOR
    assert app.editor_screen is not None
    app.shutdown()
