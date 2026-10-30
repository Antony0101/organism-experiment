"""World construction and shared runtime state."""

import dataclasses as dc

import numpy as np
import pytest

import simworld
from simworld.world import World, WorldSettings


def test_default_world_settings_and_initial_resources():
    world = World()
    assert dc.asdict(world.settings) == {
        "width": 64, "height": 64, "seed": 0, "dt": 1.0, "cell_size": 8.0,
        "energy_component": "Energy", "default_speed": 1.0,
        "shuffle_actions": True, "extra": {},
    }
    assert world.resources["settings"] is world.settings
    assert world.width == 64 and world.height == 64
    assert world.tick == 0 and world.time == 0.0 and world.dt == 1.0
    assert isinstance(world.rng, np.random.Generator)
    assert world.rng is world.resources["rng"]
    assert world._alloc.count_alive() == 0
    assert world._stores == {}


def test_world_accepts_explicit_and_additional_settings():
    world = World(12, 9, seed=42, dt=0.25, cell_size=4.0, extra={"label": "demo"},
                  energy_component="Fuel", default_speed=2.0, shuffle_actions=False)
    assert (world.width, world.height, world.dt) == (12, 9, 0.25)
    assert world.settings.seed == 42 and world.settings.cell_size == 4.0
    assert world.settings.extra == {"label": "demo"}
    assert world.settings.energy_component == "Fuel"
    assert world.settings.default_speed == 2.0
    assert world.settings.shuffle_actions is False


def test_unknown_world_settings_list_valid_options():
    with pytest.raises(TypeError) as caught:
        World(default_speeed=2)
    message = str(caught.value)
    assert "default_speeed" in message
    assert all(name in message for name in ("energy_component", "default_speed", "shuffle_actions"))


def test_world_random_generators_are_seeded_and_independent():
    first, second = World(seed=73), World(seed=73)
    expected = np.random.default_rng(73).random(8)
    np.testing.assert_array_equal(first.rng.random(8), expected)
    np.testing.assert_array_equal(second.rng.random(8), expected)
    assert first.rng is not second.rng
    first.rng.random(3)
    assert not np.array_equal(first.rng.random(8), second.rng.random(8))


def test_mutable_world_state_and_settings_defaults_are_independent():
    first, second = World(), World()
    first.settings.extra["label"] = "first"
    first.resources["custom"] = []
    first._alloc.alloc()
    first._stores["Second"] = {}
    first._stores["First"] = {}
    assert list(first._stores) == ["Second", "First"]
    assert second.settings.extra == {} and "custom" not in second.resources
    assert second._alloc.count_alive() == 0 and second._stores == {}
    settings_one, settings_two = WorldSettings(), WorldSettings()
    settings_one.extra["x"] = 1
    assert settings_two.extra == {}
    supplied = {"name": "original"}
    World(extra=supplied).settings.extra["name"] = "changed"
    assert supplied == {"name": "original"}


def test_clock_properties_read_current_resources():
    world = World()
    world.resources.update(dt=0.5, time=3.5, tick=7)
    assert (world.dt, world.time, world.tick) == (0.5, 3.5, 7)
    assert world.settings.dt == 1.0


def test_world_exports_and_unavailable_module_integration():
    assert simworld.World is World and simworld.WorldSettings is WorldSettings
    assert {"World", "WorldSettings"} <= set(simworld.__all__)
    with pytest.raises(NotImplementedError, match="module"):
        World(modules=("movement",))
