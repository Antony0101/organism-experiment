"""World-owned grids, field metadata and terrain change notifications."""

import numpy as np
import pytest

from simworld import World
from simworld.errors import (
    ConfigError, DuplicateNameError, OutOfBoundsError, UnknownLayerError,
    UnknownTerrainError,
)
from simworld.layers import LayerStore
from simworld.terrain import TerrainRegistry


def test_world_owns_independent_empty_grid_services_without_allocating_terrain():
    first, second = World(4, 3), World(2, 1)
    assert isinstance(first.layers, LayerStore) and first.layers == {}
    assert isinstance(first.terrains, TerrainRegistry)
    assert first.terrains.layer is None
    first.define_terrain("ground", 1)
    first.define_layer("heat", default=2)
    assert first.terrains.layer is None
    assert second.layers == {} and second.terrains.names() == []
    assert second.terrains.ensure_layer().data.shape == (1, 2)
    with pytest.raises(UnknownLayerError):
        second.layers["heat"]


def test_define_layer_passes_dimensions_dtype_cell_shape_and_metadata():
    world = World(4, 3)
    layer = world.define_layer(
        "velocity", np.float32, (2, 3), shape=(2,), min=-1, max=5,
        decay=0.1, diffusion=0.2, color=[10, 20, 30], tooltip="Flow", kind="vector",
        units="cells/second",
    )
    assert world.layers["velocity"] is layer
    assert layer.data.shape == (3, 4, 2) and layer.data.dtype == np.dtype(np.float32)
    np.testing.assert_array_equal(layer.data, np.tile([2, 3], (3, 4, 1)))
    assert (layer.min, layer.max, layer.decay_rate, layer.diffusion_rate) == (-1, 5, 0.1, 0.2)
    assert layer.color == (10, 20, 30) and layer.tooltip == "Flow"
    assert layer.kind == "vector" and layer.props == {"units": "cells/second"}


def test_layer_replacement_is_explicit_allocates_fresh_data_and_preserves_order():
    world = World(4, 3)
    original = world.define_layer("heat", default=2)
    world.define_layer("other")
    original.set(2, 1, 7)
    with pytest.raises(DuplicateNameError, match="replace=True"):
        world.define_layer("heat", default=9)
    assert world.layers["heat"] is original and original.get(2, 1) == 7
    replacement = world.define_layer("heat", dtype=np.int16, default=9, replace=True)
    assert replacement is not original and world.layers["heat"] is replacement
    assert list(world.layers) == ["heat", "other"]
    np.testing.assert_array_equal(replacement.data, np.full((3, 4), 9, dtype=np.int16))
    assert original.get(2, 1) == 7  # Old references retain their old arrays.


def test_failed_replacement_does_not_discard_the_existing_layer():
    world = World(4, 3)
    original = world.define_layer("heat")
    with pytest.raises(ValueError):
        world.define_layer("heat", shape=(-1,), replace=True)
    assert world.layers["heat"] is original


def test_field_defaults_and_optional_update_metadata():
    world = World(4, 3)
    plain = world.define_field("plain")
    assert plain.is_float and plain.shape == () and plain.kind == "field"
    assert plain.default == 0 and plain.min == 0 and plain.max is None
    assert plain.props == {"regrow": 0.0, "regrow_by": None, "diffuse_on": None}
    world.define_terrain("ground", 1, fertility=0.5)
    field = world.define_field(
        "food", initial=2, min=1, max=10, decay=0.1, diffusion=0.3,
        regrow=0.2, regrow_by="fertility", diffuse_on=["ground"],
        color=(10, 20, 30), tooltip="Food supply", units="grams",
    )
    assert field.props == {"regrow": 0.2, "regrow_by": "fertility",
                           "diffuse_on": ["ground"], "units": "grams"}
    assert (field.min, field.max, field.decay_rate, field.diffusion_rate) == (1, 10, 0.1, 0.3)
    assert field.color == (10, 20, 30) and field.tooltip == "Food supply"
    np.testing.assert_array_equal(field.data, np.full((3, 4), 2.0))
    world.step()
    np.testing.assert_array_equal(field.data, np.full((3, 4), 2.0))  # No resources module yet.


@pytest.mark.parametrize("options, message", [
    ({"regrow": 0.2}, "max"),
    ({"regrow": 0.2, "max": 10, "regrow_by": "fertility"}, "fertility"),
    ({"regrow_by": "fertility"}, "fertility"),
])
def test_field_prerequisites_fail_before_creating_or_replacing_layers(options, message):
    world = World(4, 3)
    original = world.define_layer("food", default=3)
    with pytest.raises(ConfigError, match=message):
        world.define_field("food", replace=True, **options)
    assert world.layers["food"] is original
    with pytest.raises(ConfigError, match=message):
        world.define_field("new", **options)
    assert "new" not in world.layers


def test_regrowth_accepts_zero_max_and_a_property_defined_on_only_one_terrain():
    world = World()
    world.define_terrain("rock", 0)
    world.define_terrain("ground", 1, fertility=0.0)
    field = world.define_field("food", max=0, regrow=0.2, regrow_by="fertility")
    assert field.max == 0 and field.props["regrow_by"] == "fertility"


def test_field_initial_value_is_stored_without_implicit_clamping():
    field = World(2, 1).define_field("food", initial=20, max=10)
    np.testing.assert_array_equal(field.data, [[20, 20]])
    field.clamp()
    np.testing.assert_array_equal(field.data, [[10, 10]])


def test_field_replacement_uses_the_same_duplicate_policy_as_other_layers():
    world = World(2, 1)
    original = world.define_field("food", initial=2, max=10)
    with pytest.raises(DuplicateNameError):
        world.define_field("food", initial=3)
    assert world.layers["food"] is original
    updated = world.define_field("food", initial=3, replace=True)
    assert world.layers["food"] is updated and updated is not original
    assert updated.max is None
    np.testing.assert_array_equal(updated.data, [[3, 3]])


def test_world_terrain_wrappers_lookup_and_paint_floored_xy_coordinates():
    world = World(4, 3)
    ground = world.define_terrain("ground", 1, color=(1, 2, 3), fertility=0.5)
    mud = world.define_terrain("mud", 3, move_cost=2.5, passable=False,
                               color=(4, 5, 6), fertility=1.5)
    assert world.terrains.get("mud") is mud
    assert world.terrains.layer is None
    assert world.fill_terrain("ground") is None
    assert world.set_terrain(2.9, 1.2, "mud") is None
    assert world.terrain_at(2.9, 1.2) is mud
    assert world.terrain_at(1, 2) is ground
    assert world.layers["terrain"].get(2, 1) == 3
    np.testing.assert_array_equal(world.terrains.prop_grid("fertility"),
                                  [[0.5, 0.5, 0.5, 0.5], [0.5, 0.5, 1.5, 0.5],
                                   [0.5, 0.5, 0.5, 0.5]])


def test_terrain_api_notifications_happen_after_successful_changes(monkeypatch):
    world = World(4, 3)
    changes = []
    monkeypatch.setattr(world, "_paths_changed", lambda: changes.append(
        None if world.terrains.layer is None else world.terrains.layer.data.copy()))
    world.define_terrain("ground", 1)
    world.define_terrain("mud", 3)
    world.fill_terrain("ground")
    world.set_terrain(2, 1, "mud")
    world.define_terrain("mud", 3, move_cost=2)
    world.terrains.undefine("mud")
    assert len(changes) == 6
    assert changes[:2] == [None, None]
    np.testing.assert_array_equal(changes[2], np.ones((3, 4)))
    assert changes[3][1, 2] == 3
    assert world.layers["terrain"].get(2, 1) == 3
    with pytest.raises(UnknownTerrainError):
        world.terrain_at(2, 1)
    before = world.layers["terrain"].data.copy()
    for operation, error in [
        (lambda: world.set_terrain(0, 0, "missing"), UnknownTerrainError),
        (lambda: world.fill_terrain("missing"), UnknownTerrainError),
        (lambda: world.set_terrain(-0.1, 0, "ground"), OutOfBoundsError),
        (lambda: world.define_terrain("ground", 2), DuplicateNameError),
    ]:
        with pytest.raises(error):
            operation()
    assert len(changes) == 6
    np.testing.assert_array_equal(world.layers["terrain"].data, before)
    world.layers["terrain"][0, 0] = 99
    assert len(changes) == 6  # Raw array writes bypass the hook.


def test_unknown_terrain_paint_does_not_allocate_a_plane():
    world = World()
    with pytest.raises(UnknownTerrainError):
        world.fill_terrain("missing")
    with pytest.raises(UnknownTerrainError):
        world.set_terrain(0, 0, "missing")
    assert world.layers == {}


def test_defining_or_replacing_terrain_layer_notifies_hook_but_other_layers_do_not(monkeypatch):
    world = World(4, 3)
    notifications = []
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(world.layers["terrain"]))
    world.define_layer("heat")
    terrain = world.define_layer("terrain", dtype=np.int16, default=7, kind="terrain")
    assert notifications == [terrain] and world.terrains.layer is terrain
    with pytest.raises(DuplicateNameError):
        world.define_layer("terrain")
    assert notifications == [terrain]
    replacement = world.define_layer("terrain", dtype=np.int16, default=9, replace=True)
    assert notifications == [terrain, replacement]
    assert world.terrains.ensure_layer() is replacement
