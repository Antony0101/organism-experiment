from __future__ import annotations

import pytest

from sim_sandbox.camera import Camera2D
from sim_sandbox.clock import FixedStepClock


def test_fixed_clock_pause_step_and_speeds() -> None:
    clock = FixedStepClock(tick_rate=60)
    assert clock.consume_steps(1 / 60) == 1
    clock.toggle_pause()
    assert clock.alpha == 1.0
    assert clock.consume_steps(1.0) == 0
    clock.request_step()
    assert clock.consume_steps(0.0) == 1
    clock.set_speed(4.0)
    clock.toggle_pause()
    assert clock.consume_steps(1 / 60) == 4
    with pytest.raises(ValueError):
        clock.set_speed(3.0)


def test_camera_round_trip_zoom_and_bounds() -> None:
    camera = Camera2D(500, 500, 200, 100, world_width=1000, world_height=1000)
    screen = camera.world_to_screen(540, 470)
    assert camera.screen_to_world(*screen) == pytest.approx((540, 470))

    anchor_before = camera.screen_to_world(150, 25)
    camera.zoom_at(2.0, 150, 25)
    assert camera.screen_to_world(150, 25) == pytest.approx(anchor_before)

    camera.pan(-10_000, -10_000)
    left, top, _, _ = camera.visible_rect()
    assert left >= 0
    assert top >= 0

