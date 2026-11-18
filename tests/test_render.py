"""Hand-calculated headless RGB composition and ASCII map contracts."""

from copy import deepcopy

import numpy as np
import pytest

from simworld import Appearance, Position, World
from simworld.errors import UnknownLayerError
from simworld.render import render_ascii, render_rgb


def test_rgb_empty_world_uses_gray_without_allocating_or_mutating_services():
    world = World(3, 2, seed=73)
    world.define_terrain("ground", 1, color=(1, 2, 3))
    before = deepcopy(world.rng.bit_generator.state)
    rgb = render_rgb(world)
    assert rgb.shape == (2, 3, 3) and rgb.dtype == np.uint8
    np.testing.assert_array_equal(rgb, np.full((2, 3, 3), 40, dtype=np.uint8))
    assert world.layers == {} and world._stores == {}
    assert world.rng.bit_generator.state == before
    rgb[:] = 0
    assert render_rgb(world)[0, 0].tolist() == [40, 40, 40]


def test_terrain_colors_handle_sparse_unknown_and_negative_ids_without_wrapping():
    world = World(3, 2)
    world.define_terrain("ground", 1, color=(10, 20, 30))
    world.define_terrain("water", 3, color=(40, 80, 120))
    data = world.terrains.ensure_layer().data
    data[:] = [[1, 3, 2], [99, -1, 1]]
    before = data.copy()
    expected = [[[10, 20, 30], [40, 80, 120], [40, 40, 40]],
                [[40, 40, 40], [40, 40, 40], [10, 20, 30]]]
    np.testing.assert_array_equal(render_rgb(world, entities=False), expected)
    np.testing.assert_array_equal(data, before)


def test_field_opacity_uses_max_clips_values_and_respects_global_alpha():
    world = World(4, 1)
    world.define_field("food", max=10, color=(200, 100, 0)).data[:] = [[-2, 0, 5, 20]]
    rgb = render_rgb(world, field_alpha=0.5)
    np.testing.assert_array_equal(rgb, [[[40, 40, 40], [40, 40, 40], [80, 55, 30], [120, 70, 20]]])
    np.testing.assert_array_equal(render_rgb(world, field_alpha=0), np.full((1, 4, 3), 40))


@pytest.mark.parametrize("maximum", [None, 0])
def test_field_without_truthy_max_uses_data_peak_and_zero_field_is_transparent(maximum):
    world = World(2, 1)
    field = world.define_field("food", max=maximum, color=(200, 100, 0))
    np.testing.assert_array_equal(render_rgb(world), np.full((1, 2, 3), 40))
    field.data[:] = [[1, 2]]
    np.testing.assert_array_equal(render_rgb(world, field_alpha=1), [[[120, 70, 20], [200, 100, 0]]])
    assert render_rgb(world)[0, 1].tolist() == [136, 76, 16]


def test_field_selection_layer_order_and_colored_field_only_policy():
    world = World(1, 1)
    world.define_field("red", initial=1, max=1, color=(200, 0, 0))
    world.define_field("blue", initial=1, max=1, color=(0, 0, 200))
    world.define_field("invisible", initial=100, max=100)
    world.define_layer("ordinary", default=100, color=(0, 255, 0))
    np.testing.assert_array_equal(render_rgb(world, field_alpha=0.5), [[[60, 10, 110]]])
    np.testing.assert_array_equal(render_rgb(world, fields=["blue", "red"], field_alpha=0.5), [[[110, 10, 60]]])
    np.testing.assert_array_equal(render_rgb(world, fields="red", field_alpha=1), [[[200, 0, 0]]])
    np.testing.assert_array_equal(render_rgb(world, fields=[]), [[[40, 40, 40]]])
    with pytest.raises(UnknownLayerError):
        render_rgb(world, fields=["missing"])


def test_entities_override_fields_use_appearance_or_white_and_can_be_hidden():
    world = World(3, 2)
    world.define_field("food", initial=1, max=1, color=(0, 100, 0))
    world.spawn(Position(1.9, 0.2), Appearance(color=(200, 30, 20), size=9))
    world.spawn(Position(2, 1))
    world.spawn(Appearance(color=(255, 0, 255)))  # No Position means no marker.
    rgb = render_rgb(world, field_alpha=1)
    assert rgb[0, 1].tolist() == [200, 30, 20]
    assert rgb[1, 2].tolist() == [255, 255, 255]
    assert rgb[0, 0].tolist() == [0, 100, 0]
    np.testing.assert_array_equal(render_rgb(world, entities=False, field_alpha=1),
                                  np.tile([0, 100, 0], (2, 3, 1)))


def test_entity_callback_overrides_appearance_and_only_sees_visible_entities():
    world = World(2, 1)
    first = world.spawn(Position(0.9, 0.1), Appearance(color=(1, 2, 3)))
    second = world.spawn(Position(0.5, 0.5))
    world.spawn(Position(-0.1, 0))
    world.spawn(Position(2, 0))
    seen = []

    def color(owner, entity):
        assert owner is world
        seen.append(entity)
        return (10, 20, 30) if entity == first else (40, 50, 60)

    assert render_rgb(world, entity_color=color)[0, 0].tolist() == [40, 50, 60]
    assert seen == [first, second]
    seen.clear()
    render_rgb(world, entities=False, entity_color=color)
    assert seen == []


def test_scale_repeats_each_cell_and_entity_as_exact_pixel_squares():
    world = World(3, 2)
    world.spawn(Position(1.2, 0.2), Appearance(color=(10, 20, 30)))
    base = render_rgb(world)
    scaled = render_rgb(world, scale=np.int64(3))
    assert scaled.shape == (6, 9, 3) and scaled.dtype == np.uint8
    for y in range(2):
        for x in range(3):
            np.testing.assert_array_equal(scaled[y * 3:(y + 1) * 3, x * 3:(x + 1) * 3],
                                          np.tile(base[y, x], (3, 3, 1)))


@pytest.mark.parametrize("width,height", [(0, 3), (4, 0), (0, 0)])
def test_empty_axes_render_with_correct_shape_and_empty_ascii(width, height):
    world = World(width, height)
    world.define_field("empty", color=(1, 2, 3))
    assert render_rgb(world, scale=2).shape == (height * 2, width * 2, 3)
    assert render_ascii(world) == ""


@pytest.mark.parametrize("options,error", [({"scale": 0}, ValueError), ({"scale": -1}, ValueError),
                                           ({"scale": 1.5}, TypeError),
                                           ({"field_alpha": -0.1}, ValueError),
                                           ({"field_alpha": 1.1}, ValueError),
                                           ({"field_alpha": float("nan")}, ValueError)])
def test_invalid_rgb_parameters_fail_clearly(options, error):
    with pytest.raises(error):
        render_rgb(World(), **options)


def test_colored_vector_fields_raise_a_clear_error():
    world = World(2, 1)
    world.define_layer("vector", shape=(2,), kind="field", color=(1, 2, 3))
    with pytest.raises(ValueError, match="scalar"):
        render_rgb(world)


def test_ascii_terrain_chars_name_fallback_unknown_cells_and_entity_toggle():
    world = World(3, 2)
    world.define_terrain("ground", 1, char=".")
    world.define_terrain("Water", 3)
    world.terrains.ensure_layer().data[:] = [[1, 3, 99], [-1, 1, 3]]
    world.spawn(Position(1.9, 1.2))
    world.spawn(Position(-0.1, 0))
    assert render_ascii(world) == ".W?\n?oW"
    assert render_ascii(world, entities=False) == ".W?\n?.W"
    assert render_ascii(World(3, 2)) == "...\n..."


def test_ascii_downsamples_both_axes_and_keeps_entities_in_their_output_bin():
    world = World(7, 4)
    world.define_terrain("ground", 1, char=".")
    world.define_terrain("Water", 3, char="~")
    world.fill_terrain("ground")
    world.set_terrain(3, 0, "Water")
    world.spawn(Position(5.9, 2.9))
    world.spawn(Position(6.9, 3.9))
    assert render_ascii(world, max_width=3) == ".o.\n..o"
    assert render_ascii(world, max_width=3, entities=False) == ".~.\n..."


@pytest.mark.parametrize("max_width,error", [(0, ValueError), (-1, ValueError), (1.5, TypeError)])
def test_invalid_ascii_width_is_rejected(max_width, error):
    with pytest.raises(error):
        render_ascii(World(), max_width=max_width)
