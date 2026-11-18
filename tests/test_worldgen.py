"""Seeded value noise, interpolation and random-generator ownership."""

from copy import deepcopy
import importlib

import numpy as np
import pytest

from simworld import World
from simworld.errors import UnknownTerrainError
from simworld import worldgen
from simworld.worldgen import value_noise


@pytest.mark.parametrize("height,width", [(7, 13), (13, 7), (1, 1), (1, 9), (9, 1), (0, 3), (4, 0)])
def test_noise_has_requested_shape_and_finite_normalized_values(height, width):
    noise = value_noise(np.random.default_rng(73), height, width, scale=3)
    assert noise.shape == (height, width) and noise.dtype == np.dtype(float)
    assert np.isfinite(noise).all()
    assert ((noise >= 0) & (noise <= 1)).all()
    if noise.size > 1:
        assert noise.min() == 0 and noise.max() == 1
    elif noise.size == 1:
        assert noise.item() == 0


def test_same_seed_reproduces_noise_and_subsequent_rng_state():
    first, second = np.random.default_rng(713), np.random.default_rng(713)
    a = value_noise(first, 11, 17, scale=5, octaves=3, persistence=0.7)
    b = value_noise(second, 11, 17, scale=5, octaves=3, persistence=0.7)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(first.random(8), second.random(8))
    other = value_noise(np.random.default_rng(714), 11, 17, scale=5, octaves=3)
    assert not np.array_equal(a, other)
    a[:] = -1
    assert (b >= 0).all()


class FixedGrids:
    """Supply hand-calculated lattice values without any random draws."""

    def __init__(self, *grids):
        self.grids = iter(grids)

    def random(self, shape):
        grid = np.asarray(next(self.grids), dtype=float)
        assert grid.shape == shape
        return grid


def test_single_octave_bilinearly_interpolates_both_axes_before_normalizing():
    rng = FixedGrids([[0, 1 / 3], [2 / 3, 1]])
    noise = value_noise(rng, 2, 3, scale=4, octaves=1)
    np.testing.assert_allclose(noise, [[0, 0.25, 0.5], [0.5, 0.75, 1]])


@pytest.mark.parametrize("persistence,expected", [
    (0, [[0, 0.5, 1], [0, 0.5, 1]]),
    (0.5, [[0, 1 / 3, 2 / 3], [1 / 3, 2 / 3, 1]]),
    (1, [[0, 0.25, 0.5], [0.5, 0.75, 1]]),
    (2, [[0, 1 / 6, 1 / 3], [2 / 3, 5 / 6, 1]]),
])
def test_octaves_halve_spacing_and_weight_finer_details(persistence, expected):
    rng = FixedGrids([[0, 1], [0, 1]], [[0, 0], [1, 1]])
    noise = value_noise(rng, 2, 3, scale=8, octaves=2, persistence=persistence)
    np.testing.assert_allclose(noise, expected)


def test_constant_lattices_normalize_to_zero_without_warnings():
    rng = FixedGrids(np.full((2, 2), 0.25), np.full((2, 2), 0.75))
    with np.errstate(all="raise"):
        noise = value_noise(rng, 2, 3, scale=8, octaves=2)
    np.testing.assert_array_equal(noise, np.zeros((2, 3)))


def test_subpixel_scales_use_pixel_spacing_without_excessive_lattice_allocation():
    a = value_noise(np.random.default_rng(91), 3, 5, scale=0.01)
    b = value_noise(np.random.default_rng(91), 3, 5, scale=1)
    np.testing.assert_array_equal(a, b)


def test_large_persistence_stays_finite_without_overflowing_amplitudes():
    with np.errstate(over="raise", invalid="raise"):
        noise = value_noise(np.random.default_rng(1), 2, 3, octaves=5, persistence=1e100)
    assert np.isfinite(noise).all()
    assert noise.min() == 0 and noise.max() == 1


def test_empty_output_does_not_consume_rng():
    rng = np.random.default_rng(7)
    before = deepcopy(rng.bit_generator.state)
    assert value_noise(rng, 0, 5).shape == (0, 5)
    assert rng.bit_generator.state == before


@pytest.mark.parametrize("options,message", [
    ({"height": -1}, "height"), ({"width": -1}, "width"),
    ({"scale": 0}, "scale"), ({"scale": -1}, "scale"),
    ({"scale": float("nan")}, "scale"), ({"scale": float("inf")}, "scale"),
    ({"octaves": 0}, "octaves"), ({"octaves": -1}, "octaves"),
    ({"persistence": -1}, "persistence"),
    ({"persistence": float("nan")}, "persistence"),
    ({"persistence": float("inf")}, "persistence"),
])
def test_invalid_parameters_fail_before_consuming_rng(options, message):
    rng = np.random.default_rng(7)
    before = deepcopy(rng.bit_generator.state)
    kwargs = {"height": 3, "width": 5, **options}
    with pytest.raises(ValueError, match=message):
        value_noise(rng, **kwargs)
    assert rng.bit_generator.state == before


@pytest.mark.parametrize("options", [{"height": 1.5}, {"width": 2.5}, {"octaves": 1.5}])
def test_dimensions_and_octave_count_require_integers(options):
    with pytest.raises(TypeError):
        value_noise(np.random.default_rng(7), **{"height": 3, "width": 5, **options})


def test_module_import_and_generation_use_only_the_supplied_rng(monkeypatch):
    rng = np.random.default_rng(713)

    def unexpected_draw(*args, **kwargs):
        raise AssertionError("Noise must use the supplied generator")

    for name in ["default_rng", "random", "rand", "uniform", "seed"]:
        monkeypatch.setattr(np.random, name, unexpected_draw)
    module = importlib.reload(importlib.import_module("simworld.worldgen"))
    assert module.value_noise(rng, 3, 5).shape == (3, 5)


@pytest.fixture
def terrain_world():
    world = World(5, 3, seed=17)
    world.define_terrain("ground", 1)
    world.define_terrain("mud", 3)
    world.define_terrain("old", 9)
    world.fill_terrain("old")
    return world


def test_noise_bands_include_boundaries_extrema_and_above_last_threshold(terrain_world, monkeypatch):
    world = terrain_world
    noise = np.array([[0, 0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8, 0.9],
                      [1, 0, 0.2, 0.8, 1]])
    calls, notifications = [], []

    def fixed_noise(rng, height, width, scale, octaves):
        calls.append((rng, height, width, scale, octaves))
        return noise

    monkeypatch.setattr(worldgen, "value_noise", fixed_noise)
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(world.layers["terrain"].data.copy()))
    layer, data = world.layers["terrain"], world.layers["terrain"].data
    result = worldgen.terrain_from_noise(world, [("ground", 0.2), ("mud", 0.8)], scale=4, octaves=2)
    assert result is noise
    assert calls == [(world.rng, 3, 5, 4, 2)]
    expected = [[1, 1, 1, 3, 3], [3, 3, 3, 3, 3], [3, 1, 1, 3, 3]]
    np.testing.assert_array_equal(data, expected)
    assert world.layers["terrain"] is layer and layer.data is data
    assert len(notifications) == 1
    np.testing.assert_array_equal(notifications[0], expected)


def test_noise_band_order_first_match_and_exact_zero_are_preserved(terrain_world, monkeypatch):
    world = terrain_world
    noise = np.array([[0, 0.5, 1, 0.5, 0]] * 3)
    monkeypatch.setattr(worldgen, "value_noise", lambda *args, **kwargs: noise)
    worldgen.terrain_from_noise(world, [("ground", 0.8), ("old", 0.2), ("mud", 0.9)])
    np.testing.assert_array_equal(world.layers["terrain"].data, [[1, 1, 3, 1, 1]] * 3)
    worldgen.terrain_from_noise(world, [("ground", 0), ("mud", 1)])
    np.testing.assert_array_equal(world.layers["terrain"].data, [[1, 3, 3, 3, 1]] * 3)


@pytest.mark.parametrize("bands,error", [([], ValueError), ([("missing", 1)], UnknownTerrainError),
                                        ([("ground", float("nan"))], ValueError),
                                        ([("ground", float("inf"))], ValueError)])
def test_invalid_noise_bands_preserve_cells_rng_and_notifications(terrain_world, monkeypatch, bands, error):
    world = terrain_world
    before = deepcopy(world.rng.bit_generator.state)
    notifications = []
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(True))
    with pytest.raises(error):
        worldgen.terrain_from_noise(world, bands)
    assert world.rng.bit_generator.state == before and notifications == []
    np.testing.assert_array_equal(world.layers["terrain"].data, np.full((3, 5), 9))


def test_noise_painting_reproduces_cells_noise_and_following_rng_state():
    worlds = [World(11, 7, seed=73), World(11, 7, seed=73)]
    results = []
    for world in worlds:
        world.define_terrain("ground", 1)
        world.define_terrain("mud", 3)
        results.append(worldgen.terrain_from_noise(world, [("ground", 0.4), ("mud", 0.8)], scale=4))
        assert set(np.unique(world.layers["terrain"].data)) == {1, 3}
    np.testing.assert_array_equal(results[0], results[1])
    np.testing.assert_array_equal(worlds[0].layers["terrain"].data, worlds[1].layers["terrain"].data)
    np.testing.assert_array_equal(worlds[0].rng.random(8), worlds[1].rng.random(8))


class FixedEllipse:
    def __init__(self, *values):
        self.values = iter(values)
        self.bounds = []

    def uniform(self, low, high):
        self.bounds.append((low, high))
        value = next(self.values)
        assert low <= value <= high
        return value


def test_blobs_paint_cell_center_ellipse_with_separate_radii_and_one_notification(terrain_world, monkeypatch):
    world = terrain_world
    rng = FixedEllipse(1.5, 1.5, 1, 0.5)
    world.resources["rng"] = rng
    notifications = []
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(world.layers["terrain"].data.copy()))
    data = world.layers["terrain"].data
    assert worldgen.paint_blobs(world, "mud", 1, radius=(0.5, 1)) is None
    assert rng.bounds == [(0, 5), (0, 3), (0.5, 1), (0.5, 1)]
    expected = [[9, 9, 9, 9, 9], [3, 3, 3, 9, 9], [9, 9, 9, 9, 9]]
    assert world.layers["terrain"].data is data
    np.testing.assert_array_equal(data, expected)
    assert len(notifications) == 1
    np.testing.assert_array_equal(notifications[0], expected)


@pytest.mark.parametrize("cx,cy,cell", [(0.25, 0.25, (0, 0)), (4.75, 2.75, (2, 4))])
def test_blobs_clip_at_world_edges_without_wrapping(terrain_world, cx, cy, cell):
    world = terrain_world
    world.resources["rng"] = FixedEllipse(cx, cy, 1, 1)
    worldgen.paint_blobs(world, "mud", 1, radius=(1, 1))
    expected = np.full((3, 5), 9)
    expected[cell] = 3
    np.testing.assert_array_equal(world.layers["terrain"].data, expected)


@pytest.mark.parametrize("options,error", [
    ({"terrain": "missing"}, UnknownTerrainError), ({"count": -1}, ValueError),
    ({"count": 1.5}, TypeError), ({"radius": (0, 1)}, ValueError),
    ({"radius": (2, 1)}, ValueError), ({"radius": (1, float("inf"))}, ValueError),
    ({"radius": (float("nan"), 1)}, ValueError),
])
def test_invalid_blob_parameters_preserve_cells_rng_and_notifications(terrain_world, monkeypatch, options, error):
    world = terrain_world
    before = deepcopy(world.rng.bit_generator.state)
    notifications = []
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(True))
    with pytest.raises(error):
        worldgen.paint_blobs(world, **{"terrain": "mud", "count": 2, **options})
    assert world.rng.bit_generator.state == before and notifications == []
    np.testing.assert_array_equal(world.layers["terrain"].data, np.full((3, 5), 9))


def test_blob_batches_reproduce_cells_and_following_rng_state(monkeypatch):
    worlds = [World(20, 12, seed=73), World(20, 12, seed=73)]
    for world in worlds:
        world.define_terrain("ground", 1)
        world.define_terrain("mud", 3)
        world.fill_terrain("ground")
        notifications = []
        monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(True))
        worldgen.paint_blobs(world, "mud", 4, radius=(1, 3))
        assert notifications == [True]
        assert set(np.unique(world.layers["terrain"].data)) == {1, 3}
    np.testing.assert_array_equal(worlds[0].layers["terrain"].data, worlds[1].layers["terrain"].data)
    np.testing.assert_array_equal(worlds[0].rng.random(8), worlds[1].rng.random(8))


@pytest.mark.parametrize("width,height,count", [(5, 3, 0), (0, 3, 2), (5, 0, 2)])
def test_empty_blob_work_does_not_allocate_consume_rng_or_notify(monkeypatch, width, height, count):
    world = World(width, height, seed=73)
    world.define_terrain("mud", 3)
    before = deepcopy(world.rng.bit_generator.state)
    notifications = []
    monkeypatch.setattr(world, "_paths_changed", lambda: notifications.append(True))
    assert worldgen.paint_blobs(world, "mud", count) is None
    assert world.layers == {} and world.rng.bit_generator.state == before
    assert notifications == []


@pytest.mark.parametrize("width,height", [(1, 1), (0, 3), (5, 0)])
def test_terrain_bands_handle_single_cells_and_empty_grids(width, height):
    world = World(width, height)
    world.define_terrain("ground", 1)
    world.define_terrain("mud", 3)
    noise = worldgen.terrain_from_noise(world, [("ground", 0), ("mud", 0.8)])
    assert noise.shape == world.layers["terrain"].data.shape == (height, width)
    if noise.size:
        assert world.terrain_at(0, 0).name == "ground"


def test_random_positions_return_python_floats_inside_rectangular_world():
    world = World(7, 3, seed=73)
    positions = worldgen.random_positions(world, np.int64(20), passable_only=False)
    assert len(positions) == 20 and world.count() == 0
    assert all(type(x) is float and type(y) is float for x, y in positions)
    assert all(0 <= x < 7 and 0 <= y < 3 for x, y in positions)
    assert world.layers == {}  # Bypassing terrain does not allocate a plane.


def test_random_positions_stay_in_area_and_reject_blocked_cells():
    world = World(7, 3, seed=73)
    world.define_terrain("ground", 1)
    world.define_terrain("rock", 3, passable=False)
    world.fill_terrain("ground")
    world.layers["terrain"].data[:, 2:4] = 3
    positions = worldgen.random_positions(world, 30, area=(2.2, 0.3, 4.7, 1.8))
    assert len(positions) == 30
    assert all(4 <= x < 4.7 and 0.3 <= y < 1.8 for x, y in positions)
    assert all(world.terrains.passable_at(x, y) for x, y in positions)


def test_random_positions_can_bypass_passability_filtering():
    world = World(2, 1, seed=73)
    world.define_terrain("rock", 1, passable=False)
    world.fill_terrain("rock")
    positions = worldgen.random_positions(world, 4, passable_only=False)
    assert len(positions) == 4
    assert all(not world.terrains.passable_at(x, y) for x, y in positions)


def test_random_positions_allow_undefined_terrain_ids_and_lazy_default_plane():
    world = World(2, 1, seed=73)
    assert len(worldgen.random_positions(world, 2)) == 2
    assert world.terrains.layer is not None
    world.layers["terrain"].data[:] = 32767
    assert len(worldgen.random_positions(world, 2)) == 2  # Undefined ids are passable.


class CountingCandidates:
    """Offer one passable candidate optionally, then repeat a blocked point."""

    def __init__(self, first_passable=False):
        self.calls = 0
        self.first_passable = first_passable

    def uniform(self, low, high):
        self.calls += 1
        if self.calls % 2 == 0:
            return np.float64(0.5)
        return np.float64(0.5 if self.first_passable and self.calls == 1 else 1.5)


@pytest.mark.parametrize("n", [1, 3])
def test_blocked_sampling_stops_at_exact_attempt_budget(n):
    world = World(2, 1)
    world.define_terrain("rock", 1, passable=False)
    world.fill_terrain("rock")
    rng = CountingCandidates()
    world.resources["rng"] = rng
    with pytest.raises(RuntimeError, match=f"{1000 * n} attempts"):
        worldgen.random_positions(world, n)
    assert rng.calls == 2 * 1000 * n
    assert world.count() == 0


def test_sampling_attempt_budget_includes_accepted_candidates():
    world = World(2, 1)
    world.define_terrain("ground", 1)
    world.define_terrain("rock", 3, passable=False)
    world.fill_terrain("rock")
    world.set_terrain(0, 0, "ground")
    rng = CountingCandidates(first_passable=True)
    world.resources["rng"] = rng
    with pytest.raises(RuntimeError, match="2000 attempts"):
        worldgen.random_positions(world, 2)
    assert rng.calls == 4000


def test_rounded_upper_endpoint_is_rejected_before_terrain_lookup():
    world = World(5, 3)
    rng = FixedEllipse(5, 1, 0.5, 0.5)
    world.resources["rng"] = rng
    assert worldgen.random_positions(world, 1) == [(0.5, 0.5)]
    assert rng.bounds == [(0, 5), (0, 3), (0, 5), (0, 3)]


@pytest.mark.parametrize("width,height", [(5, 3), (0, 3)])
def test_zero_random_positions_are_a_noop(width, height):
    world = World(width, height, seed=73)
    before = deepcopy(world.rng.bit_generator.state)
    assert worldgen.random_positions(world, 0) == []
    assert world.layers == {} and world.rng.bit_generator.state == before


@pytest.mark.parametrize("area", [(-1, 0, 2, 1), (0, 0, 6, 1), (3, 0, 2, 1),
                                   (1, 0, 1, 1), (0, 2, 1, 2),
                                   (0, 0, float("inf"), 1),
                                   (0, float("nan"), 1, 2), (0, 0, 1)])
def test_invalid_sampling_areas_fail_without_rng_or_grid_changes(area):
    world = World(5, 3, seed=73)
    before = deepcopy(world.rng.bit_generator.state)
    with pytest.raises(ValueError):
        worldgen.random_positions(world, 1, area=area)
    assert world.layers == {} and world.rng.bit_generator.state == before


@pytest.mark.parametrize("n,error", [(-1, ValueError), (1.5, TypeError)])
def test_invalid_sampling_counts_fail_without_rng_changes(n, error):
    world = World(seed=73)
    before = deepcopy(world.rng.bit_generator.state)
    with pytest.raises(error):
        worldgen.random_positions(world, n)
    assert world.layers == {} and world.rng.bit_generator.state == before


def test_sampling_empty_world_rejects_nonzero_request_without_drawing():
    world = World(0, 3, seed=73)
    before = deepcopy(world.rng.bit_generator.state)
    with pytest.raises(ValueError, match="area"):
        worldgen.random_positions(world, 1)
    assert world.layers == {} and world.rng.bit_generator.state == before


def test_generated_terrain_sampling_reproduces_positions_and_following_rng_state():
    worlds = [World(11, 7, seed=73), World(11, 7, seed=73)]
    results = []
    for world in worlds:
        world.define_terrain("ground", 1)
        world.define_terrain("rock", 3, passable=False)
        worldgen.terrain_from_noise(world, [("rock", 0.5), ("ground", 1)], scale=3)
        worldgen.paint_blobs(world, "ground", 2, radius=(1, 2))
        data = world.layers["terrain"].data.copy()
        positions = worldgen.random_positions(world, 10)
        assert all(world.terrains.passable_at(x, y) for x, y in positions)
        np.testing.assert_array_equal(world.layers["terrain"].data, data)
        assert world.count() == 0
        results.append(positions)
    assert results[0] == results[1]
    np.testing.assert_array_equal(worlds[0].rng.random(8), worlds[1].rng.random(8))
