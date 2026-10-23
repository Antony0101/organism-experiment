from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from sim_sandbox.game.world_definition import MAX_ENTITY_COUNT, MAX_SEED, WorldLaunchOptions
from sim_sandbox.presentation.app import AppMode, SimulationApp
from sim_sandbox.presentation.screens.world_selection import WorldSelectionScreen
from sim_sandbox.game.worlds.discovery import discover_worlds


def test_selection_validation_and_world_defaults() -> None:
    pygame.init()
    pygame.display.set_mode((640, 480))
    catalog = discover_worlds()
    screen = WorldSelectionScreen(catalog.definitions, seed_override=44, entity_count_override=3)

    assert screen.seed_text == "44"
    assert screen.population_text == "3"
    assert screen.validation()[0] == WorldLaunchOptions(44, 3)

    screen.seed_text = str(MAX_SEED + 1)
    assert screen.validation()[0] is None
    screen.seed_text = "1"
    screen.population_text = str(MAX_ENTITY_COUNT + 1)
    assert screen.validation()[0] is None

    screen._select(1)
    assert screen.selected_definition is not None
    assert screen.selected_definition.id == "empty_sandbox"
    assert screen.seed_text == str(screen.selected_definition.default_seed)
    assert screen.population_text == "0"
    pygame.quit()


def test_menu_gameplay_pause_restart_and_return_to_menu() -> None:
    app = SimulationApp(window_size=(640, 480))
    assert app.mode is AppMode.WORLD_SELECTION
    assert app.selection_screen is not None

    app._start_world("empty_sandbox", WorldLaunchOptions(seed=9, entity_count=2))
    assert app.mode is AppMode.GAMEPLAY
    first_world = app.world
    assert first_world.entity_count == 2

    app._open_pause_menu()
    assert app.mode is AppMode.PAUSE_MENU
    assert app.simulation_clock.paused

    app._apply_pause_action("restart")
    assert app.mode is AppMode.GAMEPLAY
    assert first_world.is_closed
    assert app.world is not first_world
    assert app.launch_options == WorldLaunchOptions(9, 2)

    second_world = app.world
    app._open_pause_menu()
    app._apply_pause_action("world_selection")
    assert app.mode is AppMode.WORLD_SELECTION
    assert second_world.is_closed
    assert app.gameplay is None
    app.shutdown()


def test_escape_opens_pause_and_escape_resumes() -> None:
    app = SimulationApp(
        seed=5,
        entity_count=0,
        world_id="empty_sandbox",
        window_size=(480, 320),
    )
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    app._handle_events()
    assert app.mode is AppMode.PAUSE_MENU

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    app._handle_events()
    assert app.mode is AppMode.GAMEPLAY
    assert not app.simulation_clock.paused
    app.shutdown()
