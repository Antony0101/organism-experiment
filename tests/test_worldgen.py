"""Seeded value noise, interpolation and random-generator ownership."""

from copy import deepcopy
import importlib

import numpy as np
import pytest

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
