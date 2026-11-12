"""Terrain definitions, lazy allocation and per-cell lookup/cache behavior."""

from types import SimpleNamespace

import numpy as np
import pytest

from simworld.errors import DuplicateNameError, SimWorldError, UnknownTerrainError
from simworld.layers import Layer, LayerStore
from simworld.terrain import TERRAIN_LAYER, Terrain, TerrainRegistry


@pytest.fixture
def terrain_host():
    return SimpleNamespace(width=4, height=3, layers=LayerStore())


def test_terrain_defaults_and_dict_format_copy_mutable_properties():
    first, second = Terrain("ground", 0), Terrain("water", 1)
    first.props["tags"] = ["walkable"]
    assert second.props == {}
    assert first.move_cost == 1.0 and first.passable is True
    assert first.color == (128, 128, 128)
    data = first.to_dict()
    assert data == {"name": "ground", "id": 0, "move_cost": 1.0,
                    "passable": True, "color": [128, 128, 128],
                    "props": {"tags": ["walkable"]}}
    data["props"]["tags"].append("changed")
    assert first.props["tags"] == ["walkable"]


def test_definitions_resolve_by_name_or_id_and_names_sort_by_id(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    assert terrains.layer is None
    mud = terrains.define("mud", np.int64(5), move_cost=2.5,
                          color=[120, 90, 55], fertility=1.4)
    ground = terrains.define("ground", 1)
    rock = terrains.define("rock", 3, move_cost=0, passable=False)
    assert terrains.get("mud") is terrains.get(5) is mud
    assert terrains.get(np.int64(1)) is ground
    assert terrains.by_name["rock"] is terrains.by_id[3] is rock
    assert mud.color == (120, 90, 55) and mud.props == {"fertility": 1.4}
    assert terrains.id_of("ground") == 1
    assert terrains.names() == ["ground", "rock", "mud"]
    assert terrains.layer is None  # Definitions do not allocate or repaint cells.
    names = terrains.names()
    names.clear()
    assert len(terrains.names()) == 3


def test_redefining_same_name_and_id_replaces_metadata_in_both_maps(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    old = terrains.define("mud", 2, fertility=1)
    updated = terrains.define("mud", 2, move_cost=3, passable=False,
                              color=(1, 2, 3), slippery=True)
    assert updated is not old
    assert terrains.by_name == {"mud": updated} and terrains.by_id == {2: updated}
    assert updated.move_cost == 3 and updated.passable is False
    assert updated.color == (1, 2, 3) and updated.props == {"slippery": True}
    assert old.props == {"fertility": 1}


@pytest.mark.parametrize("name, identifier", [("ground", 2), ("water", 1)])
def test_identity_conflicts_leave_both_maps_unchanged(terrain_host, name, identifier):
    terrains = TerrainRegistry(terrain_host)
    ground = terrains.define("ground", 1)
    with pytest.raises(DuplicateNameError):
        terrains.define(name, identifier)
    assert terrains.by_name == {"ground": ground} and terrains.by_id == {1: ground}


@pytest.mark.parametrize("identifier", [-1, 32768, 1.5, True])
def test_invalid_ids_fail_without_registering(terrain_host, identifier):
    terrains = TerrainRegistry(terrain_host)
    with pytest.raises(SimWorldError, match="id"):
        terrains.define("bad", identifier)
    assert terrains.by_name == terrains.by_id == {}
    assert terrain_host.layers == {}


@pytest.mark.parametrize("color", [(1, 2), (1, 2, 3, 4), (-1, 0, 0),
                                   (0, 0, 256), (0, 0, 1.5), None])
def test_invalid_rgb_redefinition_preserves_the_previous_record(terrain_host, color):
    terrains = TerrainRegistry(terrain_host)
    original = terrains.define("ground", 0)
    with pytest.raises(SimWorldError, match="RGB"):
        terrains.define("ground", 0, color=color)
    assert terrains.get("ground") is terrains.get(0) is original


@pytest.mark.parametrize("cost", [0, -1, float("nan"), float("inf")])
def test_passable_terrain_requires_finite_positive_movement_cost(terrain_host, cost):
    terrains = TerrainRegistry(terrain_host)
    with pytest.raises(SimWorldError, match="move_cost"):
        terrains.define("ground", 0, move_cost=cost)
    assert terrains.by_name == terrains.by_id == {}


def test_ensure_layer_allocates_int16_with_smallest_defined_id(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    terrains.define("mud", 5)
    terrains.define("ground", 1)
    layer = terrains.ensure_layer()
    assert TERRAIN_LAYER == "terrain"
    assert terrain_host.layers[TERRAIN_LAYER] is terrains.layer is layer
    assert layer.dtype == layer.data.dtype == np.dtype("int16")
    assert layer.name == "terrain" and layer.kind == "terrain" and layer.shape == ()
    assert layer.default == 1 and layer.tooltip == "terrain id per cell"
    np.testing.assert_array_equal(layer.data, np.full((3, 4), 1))


@pytest.mark.parametrize("identifier", [None, 32767])
def test_ensure_layer_handles_no_definitions_and_largest_storable_id(terrain_host, identifier):
    terrains = TerrainRegistry(terrain_host)
    if identifier is not None:
        terrains.define("last", identifier)
    expected = 0 if identifier is None else identifier
    np.testing.assert_array_equal(terrains.ensure_layer().data, np.full((3, 4), expected))


def test_ensure_layer_preserves_existing_object_data_and_metadata(terrain_host):
    existing = Layer("terrain", 4, 3, dtype="int16", default=7, kind="terrain")
    existing[1, 2] = 9
    terrain_host.layers["terrain"] = existing
    terrains = TerrainRegistry(terrain_host)
    terrains.define("ground", 1)
    assert terrains.ensure_layer() is existing
    terrains.undefine("ground")
    assert terrains.ensure_layer() is existing
    assert existing.default == 7 and existing[1, 2] == 9


def test_undefine_removes_both_names_without_repainting_existing_cells(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    ground = terrains.define("ground", 1)
    terrains.define("water", 2)
    layer = terrains.ensure_layer()
    assert terrains.undefine("ground") is ground
    assert "ground" not in terrains.by_name and 1 not in terrains.by_id
    assert terrains.names() == ["water"]
    np.testing.assert_array_equal(layer.data, np.full((3, 4), 1))
    with pytest.raises(UnknownTerrainError, match="water"):
        terrains.undefine("ground")


def test_unknown_terrain_lookup_lists_names_and_suggestions(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    terrains.define("ground", 1)
    with pytest.raises(UnknownTerrainError, match="Did you mean 'ground'"):
        terrains.get("groudn")
    with pytest.raises(UnknownTerrainError, match="ground"):
        terrains.get(99)


def test_registries_keep_definitions_and_layers_independent():
    first_host = SimpleNamespace(width=2, height=1, layers=LayerStore())
    second_host = SimpleNamespace(width=2, height=1, layers=LayerStore())
    first, second = TerrainRegistry(first_host), TerrainRegistry(second_host)
    first.define("ground", 1)
    assert second.names() == []
    first.ensure_layer()[0, 0] = 2
    assert second.ensure_layer()[0, 0] == 0


@pytest.fixture
def mapped_terrains(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    terrains.define("ground", 1, fertility=0.5)
    terrains.define("mud", 3, move_cost=2.5, fertility=1.5)
    terrains.define("rock", 5, move_cost=0, passable=False, char="#")
    terrains.ensure_layer().data[:] = [[1, 3, 5, 2], [99, -1, 0, 3], [5, 1, 3, 1]]
    return terrains


def test_lookup_tables_include_defaults_for_sparse_undefined_ids(mapped_terrains):
    terrains = mapped_terrains
    assert terrains._mc == [1, 1, 1, 2.5, 1, 0]
    assert terrains._pass == [True, True, True, True, True, False]
    np.testing.assert_array_equal(terrains.move_cost_lut, terrains._mc)
    np.testing.assert_array_equal(terrains.passable_lut, terrains._pass)
    assert terrains.move_cost_lut.dtype.kind == "f"
    assert terrains.passable_lut.dtype == np.dtype(bool)


def test_cell_lookups_floor_xy_and_distinguish_record_from_fallback(mapped_terrains):
    terrains = mapped_terrains
    assert terrains.at(1.9, 0.2) is terrains.get("mud")
    assert terrains.move_cost_at(1.9, 0.2) == 2.5
    assert terrains.passable_at(2, 0) is False
    for x, y in [(3, 0), (0, 1), (1, 1), (2, 1)]:
        with pytest.raises(UnknownTerrainError):
            terrains.at(x, y)
        assert terrains.move_cost_at(x, y) == 1.0
        assert terrains.passable_at(x, y) is True


@pytest.mark.parametrize("method", ["at", "move_cost_at", "passable_at"])
def test_terrain_cell_lookups_keep_layer_bounds_errors(mapped_terrains, method):
    from simworld.errors import OutOfBoundsError

    with pytest.raises(OutOfBoundsError):
        getattr(mapped_terrains, method)(-0.1, 0)


def test_grid_lookups_match_cells_and_do_not_expose_lookup_storage(mapped_terrains):
    terrains = mapped_terrains
    costs = terrains.move_cost_grid()
    passable = terrains.passable_grid()
    np.testing.assert_array_equal(costs, [[1, 2.5, 0, 1], [1, 1, 1, 2.5], [0, 1, 2.5, 1]])
    np.testing.assert_array_equal(passable, terrains.layer.data != 5)
    assert costs.dtype.kind == "f" and passable.dtype == np.dtype(bool)
    for y in range(3):
        for x in range(4):
            assert costs[y, x] == terrains.move_cost_at(x, y)
            assert passable[y, x] == terrains.passable_at(x, y)
    costs[:] = -10
    passable[:] = False
    assert terrains.move_cost_at(0, 0) == 1 and terrains.passable_at(0, 0)
    terrains.layer[0, 0] = 5
    assert terrains.move_cost_grid()[0, 0] == 0
    assert not terrains.passable_grid()[0, 0]


def test_property_grids_default_for_missing_properties_and_unknown_ids(mapped_terrains):
    terrains = mapped_terrains
    expected = [[0.5, 1.5, 0, 0], [0, 0, 0, 1.5], [0, 0.5, 1.5, 0.5]]
    grid = terrains.prop_grid("fertility")
    np.testing.assert_array_equal(grid, expected)
    assert grid.dtype.kind == "f"
    np.testing.assert_array_equal(terrains.prop_grid("missing", 7), np.full((3, 4), 7.0))
    np.testing.assert_array_equal(terrains.prop_grid("fertility", -2),
                                  [[0.5, 1.5, -2, -2], [-2, -2, -2, 1.5],
                                   [-2, 0.5, 1.5, 0.5]])


def test_property_cache_reuses_luts_but_reads_current_cells(mapped_terrains):
    terrains = mapped_terrains
    first = terrains.prop_grid("fertility")
    cached = terrains._prop_cache[("fertility", 0.0)]
    first[:] = -99
    terrains.layer[0, 0] = 3
    assert terrains.prop_grid("fertility")[0, 0] == 1.5
    assert terrains._prop_cache[("fertility", 0.0)] is cached
    terrains.prop_grid("fertility", 2)
    assert len(terrains._prop_cache) == 2
    terrains.define("mud", 3, move_cost=4, passable=False, fertility=9)
    assert terrains._prop_cache == {}
    assert terrains.prop_grid("fertility")[0, 0] == 9
    assert terrains.move_cost_grid()[0, 0] == 4
    assert not terrains.passable_grid()[0, 0]


def test_undefine_rebuilds_all_grids_without_repainting(mapped_terrains):
    terrains = mapped_terrains
    before = terrains.layer.data.copy()
    terrains.prop_grid("fertility")
    terrains.undefine("mud")
    assert terrains._prop_cache == {}
    np.testing.assert_array_equal(terrains.layer.data, before)
    assert terrains.move_cost_at(1, 0) == 1 and terrains.passable_at(1, 0)
    assert terrains.prop_grid("fertility")[0, 1] == 0
    with pytest.raises(UnknownTerrainError):
        terrains.at(1, 0)
    terrains.undefine("rock")  # Shrinks LUT; the old highest id stays safe.
    assert len(terrains.move_cost_lut) == 2
    assert terrains.move_cost_grid()[0, 2] == 1
    assert terrains.passable_grid()[0, 2]


def test_named_masks_support_single_names_collections_and_empty_selection(mapped_terrains):
    terrains = mapped_terrains
    np.testing.assert_array_equal(terrains.mask("mud"), terrains.layer.data == 3)
    np.testing.assert_array_equal(terrains.mask(["ground", "mud", "mud"]),
                                  np.isin(terrains.layer.data, [1, 3]))
    np.testing.assert_array_equal(terrains.mask([]), np.zeros((3, 4), dtype=bool))
    with pytest.raises(UnknownTerrainError, match="ground"):
        terrains.mask(["groudn"])
    terrains.layer[0, 0] = 3
    assert terrains.mask("mud")[0, 0]


def test_empty_registry_grids_lazily_create_layer_with_safe_defaults(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    assert terrains.layer is None
    np.testing.assert_array_equal(terrains.move_cost_grid(), np.ones((3, 4)))
    np.testing.assert_array_equal(terrains.passable_grid(), np.ones((3, 4), dtype=bool))
    np.testing.assert_array_equal(terrains.prop_grid("fertility", 2), np.full((3, 4), 2.0))
    np.testing.assert_array_equal(terrains.mask([]), np.zeros((3, 4), dtype=bool))
    with pytest.raises(UnknownTerrainError):
        terrains.at(0, 0)


def test_rebuild_notifies_owner_after_updates_and_never_on_failed_definitions(terrain_host):
    terrains = TerrainRegistry(terrain_host)
    notifications = []
    terrain_host._paths_changed = lambda: notifications.append(terrains.move_cost_lut.copy())
    terrains.define("ground", 1, move_cost=2)
    terrains.prop_grid("fertility")
    with pytest.raises(DuplicateNameError):
        terrains.define("ground", 2)
    with pytest.raises(SimWorldError):
        terrains.define("ground", 1, move_cost=0)
    with pytest.raises(UnknownTerrainError):
        terrains.undefine("missing")
    assert len(notifications) == 1 and terrains._prop_cache
    terrains.define("ground", 1, move_cost=3)
    terrains.undefine("ground")
    assert len(notifications) == 3
    assert notifications[0][1] == 2 and notifications[1][1] == 3
    np.testing.assert_array_equal(notifications[2], [1.0])


def test_empty_spatial_axes_and_largest_terrain_id_are_supported():
    terrains = TerrainRegistry(SimpleNamespace(width=0, height=2, layers=LayerStore()))
    terrains.define("last", 32767, fertility=4)
    for grid in [terrains.move_cost_grid(), terrains.passable_grid(),
                 terrains.prop_grid("fertility"), terrains.mask("last")]:
        assert grid.shape == (2, 0)
    assert terrains.move_cost_lut[32767] == 1
    populated = TerrainRegistry(SimpleNamespace(width=1, height=1, layers=LayerStore()))
    populated.define("last", 32767, move_cost=2, passable=False, fertility=4)
    assert populated.at(0, 0).id == 32767
    np.testing.assert_array_equal(populated.move_cost_grid(), [[2.0]])
    np.testing.assert_array_equal(populated.passable_grid(), [[False]])
    np.testing.assert_array_equal(populated.prop_grid("fertility"), [[4.0]])


def test_property_lookup_rejects_nonnumeric_values_without_caching_partial_table(mapped_terrains):
    with pytest.raises(ValueError):
        mapped_terrains.prop_grid("char")
    assert ("char", 0.0) not in mapped_terrains._prop_cache
    assert mapped_terrains.get("rock").props["char"] == "#"
