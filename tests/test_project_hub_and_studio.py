from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from sim_sandbox.game.behavior_projects.registry import BehaviorProjectStore
from sim_sandbox.game.entity_projects.registry import EntityProjectStore
from sim_sandbox.game.quick_sandbox import (
    QuickSandboxOptions,
    SandboxPopulation,
    create_quick_sandbox,
)
from sim_sandbox.presentation.app import AppMode, SimulationApp, build_parser
from sim_sandbox.presentation.screens.behavior_editor import BehaviorEditorScreen


def test_cli_exposes_hub_studios_sandbox_and_lists() -> None:
    args = build_parser().parse_args(
        ["--behavior-editor", "--terrain", "compact", "--list-behaviors"]
    )
    assert args.behavior_editor
    assert args.terrain == "compact"
    assert args.list_behaviors
    assert build_parser().parse_args(["--entity-editor"]).entity_editor
    assert build_parser().parse_args(["--sandbox", "dot"]).sandbox == "dot"
    assert build_parser().parse_args(["--list-entities"]).list_entities


def test_project_hub_studio_and_quick_sandbox_flow() -> None:
    app = SimulationApp(start_in_hub=True, start_in_menu=False, window_size=(800, 600))
    assert app.mode is AppMode.PROJECT_HUB
    assert app.hub_screen is not None

    app._show_behavior_editor("wander")
    assert app.mode is AppMode.BEHAVIOR_EDITOR
    assert app.behavior_editor_screen is not None
    assert app.behavior_editor_screen.current.definition.id == "wander"

    app._show_project_hub()
    app._show_quick_sandbox(terrain="compact")
    assert app.mode is AppMode.QUICK_SANDBOX
    assert app.quick_sandbox_screen is not None

    app._start_quick_sandbox(QuickSandboxOptions("compact", 7, ()))
    assert app.mode is AppMode.GAMEPLAY
    assert app.world.entity_count == 0
    world = app.world
    app._open_pause_menu()
    app._apply_pause_action("main_hub")
    assert app.mode is AppMode.PROJECT_HUB
    assert world.is_closed
    app.shutdown()


def test_behavior_studio_edits_custom_project_and_draws(tmp_path: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1000, 700))
    root = tmp_path / "content" / "behaviors"
    BehaviorProjectStore(root).create_default("custom_motion", "Custom Motion")
    screen = BehaviorEditorScreen((1000, 700), root, "custom_motion")
    screen.name_entry.set_text("Custom Motion Updated")
    screen.dirty = True
    assert screen.save()
    assert BehaviorProjectStore(root).load("custom_motion").definition.name == "Custom Motion Updated"
    surface = pygame.Surface((1000, 700))
    screen.draw(surface)
    screen._set_tab("parameters")
    screen.draw(surface)
    screen._set_tab("preview")
    screen.draw(surface)
    screen.close()
    pygame.quit()


def test_quick_sandbox_loads_saved_entity_projects(tmp_path: Path) -> None:
    content = tmp_path / "content"
    EntityProjectStore(content / "entities").create_default("sandbox_dot", "Sandbox Dot")
    session = create_quick_sandbox(
        QuickSandboxOptions(
            "compact", 4, (SandboxPopulation("sandbox_dot", 3),)
        ),
        content,
    )
    assert session.world.entity_count == 3
    assert all(getattr(item, "project_id", None) == "sandbox_dot" for item in session.world)
    session.close()
