from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from sim_sandbox.app import SimulationApp
from sim_sandbox.rendering import WorldRenderer


def test_headless_app_starts_renders_and_stops() -> None:
    app = SimulationApp(seed=7, entity_count=12, window_size=(320, 240))
    app.run(max_frames=3)
    assert app.world.tick_index >= 1
    assert app.world.entity_count == 12


def test_on_screen_controls_pause_step_and_do_not_spawn() -> None:
    app = SimulationApp(seed=8, entity_count=5, window_size=(480, 320))
    starting_count = app.world.entity_count
    controls = app.renderer.control_rects(app.surface.get_size())

    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=controls[WorldRenderer.STEP_ACTION].center,
        )
    )
    app._handle_events()

    assert app.simulation_clock.paused
    assert app.simulation_clock.consume_steps(0.0) == 1
    assert app.world.entity_count == starting_count

    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=controls[WorldRenderer.PAUSE_ACTION].center,
        )
    )
    app._handle_events()

    assert not app.simulation_clock.paused
    assert app.world.entity_count == starting_count
    pygame.quit()


def test_entity_selection_and_camera_follow() -> None:
    app = SimulationApp(seed=9, entity_count=8, window_size=(640, 480))
    entity = app.world.entities[0]
    entity_position = app.camera.world_to_screen(entity.x, entity.y)

    assert app._select_at_cursor((round(entity_position[0]), round(entity_position[1])))
    assert app.selected_entity_id == entity.entity_id
    assert app.follow_selected

    app.camera.pan(300.0, 200.0)
    distance_before = (entity.x - app.camera.x) ** 2 + (entity.y - app.camera.y) ** 2
    selected = app._follow_selected_entity(0.1)
    distance_after = (entity.x - app.camera.x) ** 2 + (entity.y - app.camera.y) ** 2

    assert selected is entity
    assert distance_after < distance_before
    app.run(max_frames=1)


def test_left_click_on_empty_terrain_does_not_spawn() -> None:
    app = SimulationApp(seed=10, entity_count=0, window_size=(480, 320))
    starting_count = app.world.entity_count

    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=(app.surface.get_width() // 2, app.surface.get_height() // 2),
        )
    )
    app._handle_events()

    assert app.world.entity_count == starting_count == 0
    assert app.selected_entity_id is None
    pygame.quit()


def test_on_screen_camera_control_moves_without_spawning() -> None:
    app = SimulationApp(seed=11, entity_count=0, window_size=(480, 320))
    controls = app.renderer.control_rects(app.surface.get_size())
    start_x = app.camera.x

    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=controls[WorldRenderer.CAMERA_RIGHT_ACTION].center,
        )
    )
    app._handle_events()

    assert app.camera.x > start_x
    assert app._held_camera_action == WorldRenderer.CAMERA_RIGHT_ACTION
    assert app.world.entity_count == 0

    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
    app._handle_events()
    assert app._held_camera_action is None
    pygame.quit()

