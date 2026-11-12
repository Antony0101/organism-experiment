"""Layer allocation, metadata and named layer lookup contracts."""

import numpy as np
import pytest

from simworld import Position
from simworld.errors import OutOfBoundsError, SimWorldError, UnknownLayerError
from simworld.layers import Layer, LayerStore


def test_default_scalar_layer_uses_height_then_width_and_zero_fill():
    layer = Layer("ground", width=5, height=2)
    assert (layer.name, layer.width, layer.height, layer.shape) == ("ground", 5, 2, ())
    assert layer.dtype == np.dtype(float) and layer.is_float
    assert layer.default == 0
    np.testing.assert_array_equal(layer.data, np.zeros((2, 5)))
    assert layer.data.dtype == layer.dtype
    assert layer.min is layer.max is layer.color is None
    assert layer.decay_rate == layer.diffusion_rate == 0.0
    assert layer.tooltip == "" and layer.kind == "layer" and layer.props == {}


@pytest.mark.parametrize("dtype, default, floating", [
    (np.float32, 1.25, True), ("int16", 7, False), (bool, True, False),
])
def test_scalar_layer_retains_requested_dtype_and_default(dtype, default, floating):
    layer = Layer("values", 4, 3, dtype=dtype, default=default)
    assert layer.dtype == np.dtype(dtype)
    assert layer.data.dtype == np.dtype(dtype)
    assert layer.is_float is floating
    np.testing.assert_array_equal(layer.data, np.full((3, 4), default, dtype=dtype))


@pytest.mark.parametrize("shape, default", [
    ([2], [1.0, -2.0]), ((2, 3), [[1, 2, 3], [4, 5, 6]]), ((3,), 9),
])
def test_trailing_cell_dimensions_broadcast_defaults(shape, default):
    layer = Layer("vectors", 5, 2, dtype=np.float32, default=default, shape=shape)
    assert layer.shape == tuple(shape)
    assert layer.data.shape == (2, 5, *shape)
    assert layer.data.dtype == np.dtype(np.float32)
    np.testing.assert_array_equal(layer.data, np.broadcast_to(default, (2, 5, *shape)))


def test_metadata_is_retained_without_transforming_initial_data():
    props = {"regrow": 0.25, "regrow_by": "fertility"}
    layer = Layer("food", 3, 2, default=9, min=0, max=5, decay=0.1,
                  diffusion=0.2, color=(10, 20, 30), tooltip="Available food.",
                  kind="field", props=props)
    assert layer.default == 9 and (layer.min, layer.max) == (0, 5)
    assert (layer.decay_rate, layer.diffusion_rate) == (0.1, 0.2)
    assert layer.color == (10, 20, 30)
    assert layer.tooltip == "Available food." and layer.kind == "field"
    assert layer.props == props and layer.props is not props
    props["regrow"] = 99
    assert layer.props["regrow"] == 0.25
    np.testing.assert_array_equal(layer.data, np.full((2, 3), 9.0))


def test_layers_do_not_share_arrays_or_default_property_dictionaries():
    first = Layer("first", 2, 1, default=(1, 2), shape=(2,))
    second = Layer("second", 2, 1, default=(1, 2), shape=(2,))
    first.data[0, 0, 0] = 99
    first.props["custom"] = 1
    assert first.data[0, 1, 0] == 1
    np.testing.assert_array_equal(second.data, [[[1, 2], [1, 2]]])
    assert second.props == {}


def test_layer_store_preserves_dict_behavior_and_suggests_known_names():
    ground, food = Layer("ground", 3, 2), Layer("food", 3, 2)
    layers = LayerStore(ground=ground, food=food)
    assert layers["food"] is food and list(layers) == ["ground", "food"]
    with pytest.raises(UnknownLayerError) as caught:
        layers["groudn"]
    assert "Unknown layer 'groudn'" in str(caught.value)
    assert "Did you mean 'ground'" in str(caught.value)
    assert "food" in str(caught.value)
    assert "groudn" not in layers
    assert layers.get("missing") is None
    assert layers.get("missing", ground) is ground
    with pytest.raises(UnknownLayerError, match=r"Known layer names: \(none\)"):
        LayerStore()["missing"]


def test_world_coordinates_floor_into_rows_and_columns_on_a_rectangular_grid():
    layer = Layer("grid", width=5, height=2)
    layer.set(4.9, 1.8, 7)
    layer.set(1.2, 0.9, 3)
    assert layer.get(4, 1) == 7
    assert layer.get(1.99, 0.01) == 3
    assert layer.data[1, 4] == 7 and layer.data[0, 1] == 3
    assert layer.get(0, 1) == 0
    assert layer.in_bounds(0, 0) and layer.in_bounds(4.999, 1.999)


@pytest.mark.parametrize("point", [(3.9, 1.2), [3.9, 1.2], Position(3.9, 1.2)])
def test_get_and_set_accept_coordinate_pairs_and_position_objects(point):
    layer = Layer("grid", 5, 2)
    layer.set(point, 8)
    assert layer.get(point) == 8
    assert layer.get(3, 1) == 8
    layer.set(point, 4)
    assert layer.get(point) == 4


@pytest.mark.parametrize("x, y", [(-0.01, 0), (0, -0.01), (-1, 1),
                                  (5, 0), (0, 2), (5.5, 2.5)])
def test_out_of_bounds_coordinates_raise_or_return_the_explicit_default(x, y):
    layer = Layer("food", 5, 2, default=3)
    before = layer.data.copy()
    assert not layer.in_bounds(x, y)
    with pytest.raises(OutOfBoundsError) as caught:
        layer.get(x, y)
    assert "food" in str(caught.value) and "5" in str(caught.value) and "2" in str(caught.value)
    assert layer.get((x, y), default=None) is None
    assert layer.get(Position(x, y), default=0) == 0
    fallback = object()
    assert layer.get(x, y, default=fallback) is fallback
    with pytest.raises(OutOfBoundsError):
        layer.set(x, y, 9)
    with pytest.raises(OutOfBoundsError):
        layer.set((x, y), 9)
    np.testing.assert_array_equal(layer.data, before)


@pytest.mark.parametrize("lower, upper, expected", [
    (0, 5, [0, 0, 3, 5]), (0, None, [0, 0, 3, 9]),
    (None, 5, [-2, 0, 3, 5]), (None, None, [-2, 0, 3, 9]),
])
def test_float_set_clamps_to_supplied_limits_only(lower, upper, expected):
    layer = Layer("field", 4, 1, dtype=np.float32, min=lower, max=upper)
    for x, value in enumerate([-2, 0, 3, 9]):
        layer.set(x, 0, value)
    np.testing.assert_array_equal(layer.data, [expected])
    assert layer.data.dtype == np.dtype(np.float32)


@pytest.mark.parametrize("dtype, value, expected", [("int16", 9, 9), (bool, True, True)])
def test_non_float_set_uses_dtype_conversion_without_range_clamping(dtype, value, expected):
    layer = Layer("discrete", 2, 1, dtype=dtype, min=0, max=0)
    layer.set(1, 0, value)
    assert layer.get(1, 0) == expected
    assert layer.data.dtype == np.dtype(dtype)


def test_vector_cell_access_preserves_shape_and_clamps_each_float_element():
    layer = Layer("velocity", 5, 2, shape=(2,), min=-1, max=1)
    layer.set(Position(4.9, 1.9), [-3, 4])
    np.testing.assert_array_equal(layer.get((4, 1)), [-1, 1])
    cell = layer.get(4, 1)
    assert cell.shape == (2,)
    assert np.shares_memory(cell, layer.data)
    fallback = np.array([99, 99])
    assert layer.get(5, 0, default=fallback) is fallback


def test_raw_indexing_preserves_numpy_order_views_and_bypasses_clamping():
    layer = Layer("grid", 5, 2, min=0, max=1)
    layer[1, 4] = 9
    assert layer.get(4, 1) == 9
    layer[0, :] = np.arange(5)
    np.testing.assert_array_equal(layer[0], np.arange(5))
    view = layer[:, 1:3]
    view[:] = -5
    assert layer.get(1, 0) == -5 and layer.get(2, 1) == -5
    assert layer[-1, -1] == 9
    with pytest.raises(IndexError):
        _ = layer[4, 1]
    with pytest.raises(IndexError):
        layer[0.5, 1] = 2


@pytest.mark.parametrize("point", [(4.8, 1.2), Position(4.8, 1.2)])
def test_add_reports_signed_actual_change_and_accepts_coordinate_forms(point):
    layer = Layer("food", 5, 2, default=2, min=0, max=5)
    assert layer.add(point, 10) == 3.0
    assert layer.get(point) == 5
    assert layer.add(4, 1, 1) == 0.0
    assert layer.add(point, -10) == -5.0
    assert layer.get(point) == 0
    assert layer.add(4, 1, 0) == 0.0
    assert layer.get(0, 0) == 2


@pytest.mark.parametrize("dtype, amount, expected", [(np.float32, 1e-10, 0.0),
                                                    ("int16", 0.5, 0.0)])
def test_add_reports_the_stored_change_after_dtype_conversion(dtype, amount, expected):
    layer = Layer("values", 1, 1, dtype=dtype, default=1)
    assert layer.add(0, 0, amount) == expected
    assert layer.get(0, 0) == 1


def test_integer_add_does_not_apply_float_range_limits():
    layer = Layer("counts", 1, 1, dtype="int16", default=2, min=0, max=3)
    assert layer.add(0, 0, 5) == 5.0
    assert layer.get(0, 0) == 7


def test_taking_more_than_available_returns_two_then_zero():
    layer = Layer("food", 5, 2, default=2)
    assert layer.take(4.9, 1.9, 10) == 2.0
    assert layer.get(4, 1) == 0
    assert layer.take(Position(4, 1), 10) == 0.0
    assert layer.get(0, 0) == 2


@pytest.mark.parametrize("lower, expected", [(None, 0), (0, 0), (2, 2), (-3, -3)])
def test_take_respects_the_configured_floor_and_returns_actual_removal(lower, expected):
    layer = Layer("food", 2, 1, default=5, min=lower)
    assert layer.take((1, 0), 100) == 5 - expected
    assert layer.get(1, 0) == expected
    assert layer.take(1, 0, 1) == 0
    assert layer.take(0, 0, 0) == 0
    assert layer.get(0, 0) == 5


def test_take_does_not_repair_existing_raw_values_outside_limits():
    layer = Layer("food", 2, 1, min=2, max=5)
    layer[0] = [1, 10]
    assert layer.take(0, 0, 3) == 0
    assert layer.get(0, 0) == 1
    assert layer.take(1, 0, 1) == 1
    assert layer.get(1, 0) == 9


def test_fractional_take_on_integer_cells_removes_only_available_whole_units():
    layer = Layer("counts", 1, 1, dtype="int16", default=5, min=2.5)
    assert layer.take(0, 0, 1.7) == 1
    assert layer.get(0, 0) == 4
    assert layer.take(0, 0, 99) == 1
    assert layer.get(0, 0) == 3
    assert layer.take(0, 0, 99) == 0


def test_take_preserves_large_integer_counts_until_reporting_the_float_result():
    maximum = int(np.iinfo(np.uint64).max)
    layer = Layer("counts", 1, 1, dtype=np.uint64, default=maximum)
    assert layer.take(0, 0, maximum) == float(maximum)
    assert layer.get(0, 0) == 0


@pytest.mark.parametrize("point", [(1, 0), Position(1, 0)])
def test_negative_take_is_rejected_without_changing_data(point):
    layer = Layer("food", 2, 1, default=5)
    with pytest.raises(SimWorldError, match="negative"):
        layer.take(point, -1)
    np.testing.assert_array_equal(layer.data, [[5, 5]])


@pytest.mark.parametrize("operation", ["add", "take"])
def test_arithmetic_rejects_out_of_bounds_and_vector_cells_without_mutating(operation):
    layer = Layer("food", 2, 1, default=5)
    with pytest.raises(OutOfBoundsError):
        getattr(layer, operation)(-0.1, 0, 1)
    np.testing.assert_array_equal(layer.data, [[5, 5]])
    vector = Layer("vector", 2, 1, default=(1, 2), shape=(2,))
    with pytest.raises(SimWorldError, match="scalar"):
        getattr(vector, operation)(0, 0, 1)
    np.testing.assert_array_equal(vector.data, [[[1, 2], [1, 2]]])


def test_fill_clamps_floats_in_place_without_changing_default_metadata():
    layer = Layer("food", 3, 2, dtype=np.float32, default=2, min=0, max=5)
    original = layer.data
    layer.fill(10)
    assert layer.data is original and layer.default == 2
    np.testing.assert_array_equal(layer.data, np.full((2, 3), 5))
    layer.fill(-2)
    np.testing.assert_array_equal(layer.data, np.zeros((2, 3)))


@pytest.mark.parametrize("lower, upper, expected", [
    (0, 5, [0, 3, 5]), (0, None, [0, 3, 9]),
    (None, 5, [-2, 3, 5]), (None, None, [-2, 3, 9]),
])
def test_clamp_applies_only_specified_float_bounds_in_place(lower, upper, expected):
    layer = Layer("field", 3, 1, min=lower, max=upper)
    original = layer.data
    layer[0] = [-2, 3, 9]
    layer.clamp()
    assert layer.data is original
    np.testing.assert_array_equal(layer.data, [expected])


def test_integer_fill_and_clamp_preserve_dtype_without_float_limits():
    layer = Layer("terrain", 2, 1, dtype="int16", min=0, max=1)
    layer.fill(9)
    layer.clamp()
    np.testing.assert_array_equal(layer.data, [[9, 9]])
    assert layer.data.dtype == np.dtype("int16")


@pytest.mark.parametrize("dtype", [np.float32, "int16"])
def test_total_and_mean_reduce_all_scalar_cells_to_python_floats(dtype):
    layer = Layer("values", 3, 2, dtype=dtype)
    layer.data[:] = [[0, 1, 2], [3, 4, 5]]
    assert layer.total() == 15.0 and type(layer.total()) is float
    assert layer.mean() == 2.5 and type(layer.mean()) is float


def test_bulk_operations_support_vector_cells_and_reduce_all_elements():
    layer = Layer("vector", 3, 2, shape=(2,), min=0, max=5)
    layer.fill([-2, 9])
    np.testing.assert_array_equal(layer.data, np.broadcast_to([0, 5], (2, 3, 2)))
    assert layer.total() == 30 and layer.mean() == 2.5


@pytest.mark.parametrize("x, y, expected", [
    (0.5, 0.5, 0), (2.5, 1.5, 120), (1, 1, 55), (1.25, 0.75, 32.5),
    (2, 1, 65), (0, 0, 0), (3, 2, 120), (-5, 1, 50),
    (100, 1, 70), (1, 100, 105),
])
def test_bilinear_sampling_uses_cell_centers_and_extends_edge_values(x, y, expected):
    layer = Layer("field", 3, 2)
    layer.data[:] = [[0, 10, 20], [100, 110, 120]]
    assert layer.sample(x, y) == pytest.approx(expected)


@pytest.mark.parametrize("dtype, values, midpoint, slope", [
    ("uint8", [250, 0], 125, -125), (bool, [True, False], 0.5, -0.5),
])
def test_sampling_and_gradients_use_numeric_values_without_discrete_dtype_overflow(
    dtype, values, midpoint, slope,
):
    layer = Layer("discrete", 2, 1, dtype=dtype)
    layer.data[0] = values
    assert layer.sample(1, 0.5) == midpoint
    assert layer.gradient(1, 0.5) == (slope, 0.0)
    np.testing.assert_array_equal(layer.data, [values])


@pytest.mark.parametrize("width, height, values, expected", [
    (1, 1, [[7]], 7), (1, 2, [[2], [6]], 4), (2, 1, [[2, 6]], 4),
])
def test_sampling_single_cell_rows_and_columns(width, height, values, expected):
    layer = Layer("tiny", width, height)
    layer.data[:] = values
    assert layer.sample(1, 1) == expected


def test_gradient_uses_world_x_y_axes_and_centered_unit_differences():
    layer = Layer("slope", 5, 4)
    y, x = np.indices((4, 5))
    layer.data[:] = 10 + 2 * x + 3 * y
    assert layer.gradient(2.1, 1.8) == pytest.approx((2, 3))
    assert layer.gradient(0.5, 1.5) == pytest.approx((1, 3))
    assert layer.gradient(0.5, 0.5) == pytest.approx((1, 1.5))
    assert layer.gradient(-10, -10) == (0, 0)
    assert Layer("constant", 1, 1, default=7).gradient(0.5, 0.5) == (0, 0)


def test_sampling_and_gradients_preserve_vector_dimensions_without_mutating_data():
    layer = Layer("vector", 2, 1, shape=(2,))
    layer.data[:] = [[[0, 10], [4, 2]]]
    before = layer.data.copy()
    value = layer.sample(1, 0.5)
    np.testing.assert_allclose(value, [2, 6])
    assert not np.shares_memory(value, layer.data)
    gx, gy = layer.gradient(1, 0.5)
    np.testing.assert_allclose(gx, [2, -4])
    np.testing.assert_allclose(gy, [0, 0])
    np.testing.assert_array_equal(layer.data, before)


@pytest.mark.parametrize("width, height", [(0, 2), (2, 0)])
def test_empty_layers_cannot_be_sampled(width, height):
    layer = Layer("empty", width, height)
    with pytest.raises(OutOfBoundsError, match="empty"):
        layer.sample(0.5, 0.5)


@pytest.mark.parametrize("x, y, radius, origin, expected", [
    (0.9, 0.4, 1, (0, 0), [[0, 1], [4, 5]]),
    (3.2, 2.8, 1, (2, 1), [[6, 7], [10, 11]]),
    (2, 1, 0, (2, 1), [[6]]),
    (2, 1, 1, (1, 0), [[1, 2, 3], [5, 6, 7], [9, 10, 11]]),
])
def test_windows_floor_the_center_clip_edges_and_report_their_origin(
    x, y, radius, origin, expected,
):
    layer = Layer("grid", 4, 3)
    layer.data[:] = np.arange(12).reshape(3, 4)
    window, x0, y0 = layer.window(x, y, radius)
    assert (x0, y0) == origin
    np.testing.assert_array_equal(window, expected)
    assert np.shares_memory(window, layer.data)
    window[0, 0] = 99
    assert layer.get(x0, y0) == 99


def test_windows_support_large_radii_outside_centers_and_trailing_dimensions():
    layer = Layer("vector", 4, 3, shape=(2,))
    window, x0, y0 = layer.window(0, 0, radius=99)
    assert window.shape == (3, 4, 2) and (x0, y0) == (0, 0)
    window, x0, y0 = layer.window(-10, 1)
    assert window.shape == (3, 0, 2) and (x0, y0) == (0, 0)
    window, x0, y0 = layer.window(10, 1)
    assert window.shape == (3, 0, 2) and (x0, y0) == (4, 0)
    with pytest.raises(SimWorldError, match="radius"):
        layer.window(0, 0, radius=-1)
    with pytest.raises(TypeError):
        layer.window(0, 0, radius=1.5)


def test_neighbours_yield_row_ordered_coordinate_value_triples_without_the_center():
    layer = Layer("grid", 3, 3, dtype="int16")
    layer.data[:] = np.arange(9).reshape(3, 3)
    assert list(layer.neighbours(1.9, 1.2)) == [
        (0, 0, 0), (1, 0, 1), (2, 0, 2), (0, 1, 3),
        (2, 1, 5), (0, 2, 6), (1, 2, 7), (2, 2, 8),
    ]
    assert list(layer.neighbours(1, 1, diagonal=False)) == [
        (1, 0, 1), (0, 1, 3), (2, 1, 5), (1, 2, 7),
    ]
    assert list(layer.neighbours(0, 0)) == [(1, 0, 1), (0, 1, 3), (1, 1, 4)]
    assert list(layer.neighbours(-1, 0, diagonal=False)) == [(0, 0, 0)]
    assert list(Layer("single", 1, 1).neighbours(0, 0)) == []


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_diffusion_spreads_to_four_neighbors_and_conserves_mass_in_place(dtype):
    layer = Layer("field", 5, 3, dtype=dtype, min=0, max=1)
    layer[1, 2] = 8
    original = layer.data
    layer.diffuse(0.125)
    expected = np.zeros((3, 5))
    expected[1, 2] = 4
    expected[0, 2] = expected[2, 2] = expected[1, 1] = expected[1, 3] = 1
    np.testing.assert_allclose(layer.data, expected)
    assert layer.data is original and layer.data.dtype == np.dtype(dtype)
    assert layer.total() == 8  # Limits are not implicitly clamped after diffusion.
    for _ in range(20):
        layer.diffuse(0.25)
    assert layer.total() == pytest.approx(8, abs=2e-6)
    assert np.all(layer.data >= 0)


def test_diffusion_does_not_wrap_or_lose_mass_at_the_border():
    layer = Layer("field", 3, 2)
    layer[0, 0] = 4
    layer.diffuse(0.25)
    np.testing.assert_array_equal(layer.data, [[2, 1, 0], [1, 0, 0]])
    assert layer.total() == 4


def test_diffusion_mask_blocks_transport_and_preserves_masked_out_cells():
    layer = Layer("field", 5, 3)
    layer[1, 0], layer[1, 4], layer[:, 2] = 8, 2, 7
    mask = np.ones((3, 5), dtype=bool)
    mask[:, 2] = False
    before_mask = mask.copy()
    for _ in range(10):
        layer.diffuse(0.2, mask=mask)
    assert layer.data[:, :2].sum() == pytest.approx(8)
    assert layer.data[:, 3:].sum() == pytest.approx(2)
    np.testing.assert_array_equal(layer[:, 2], [7, 7, 7])
    np.testing.assert_array_equal(mask, before_mask)


def test_all_true_and_all_false_diffusion_masks():
    unmasked, masked = Layer("plain", 3, 2), Layer("masked", 3, 2)
    unmasked.data[:] = masked.data[:] = [[1, 2, 3], [4, 5, 6]]
    unmasked.diffuse(0.2)
    masked.diffuse(0.2, mask=[[True] * 3] * 2)
    np.testing.assert_array_equal(masked.data, unmasked.data)
    before = masked.data.copy()
    masked.diffuse(0.2, mask=np.zeros((2, 3), dtype=bool))
    np.testing.assert_array_equal(masked.data, before)
    masked.diffuse(0)
    np.testing.assert_array_equal(masked.data, before)


def test_masked_diffusion_keeps_vector_components_independent():
    layer = Layer("vector", 3, 2, shape=(2,))
    layer[0, 0] = [4, 8]
    layer.diffuse(0.25, mask=[[True, True, False], [False, False, False]])
    expected = np.zeros((2, 3, 2))
    expected[0, 0], expected[0, 1] = [3, 6], [1, 2]
    np.testing.assert_array_equal(layer.data, expected)
    np.testing.assert_array_equal(layer.data.sum(axis=(0, 1)), [4, 8])


@pytest.mark.parametrize("width, height, values, expected", [
    (1, 1, [[4]], [[4]]), (3, 1, [[4, 0, 0]], [[3, 1, 0]]),
    (1, 3, [[4], [0], [0]], [[3], [1], [0]]),
    (0, 2, np.empty((2, 0)), np.empty((2, 0))),
])
def test_diffusion_handles_single_rows_columns_and_empty_axes(width, height, values, expected):
    layer = Layer("tiny", width, height)
    layer.data[:] = values
    layer.diffuse(0.25)
    np.testing.assert_array_equal(layer.data, expected)


@pytest.mark.parametrize("rate", [-0.01, 0.250001, float("nan"), float("inf"), -float("inf")])
def test_invalid_diffusion_rates_raise_before_mutation(rate):
    layer = Layer("field", 3, 2, default=2)
    with pytest.raises(SimWorldError, match="0.25"):
        layer.diffuse(rate)
    np.testing.assert_array_equal(layer.data, np.full((2, 3), 2))


@pytest.mark.parametrize("shape", [(1, 3), (2, 3, 1)])
def test_invalid_mask_shape_raises_before_diffusion_mutates_data(shape):
    layer = Layer("field", 3, 2)
    layer[0, 0] = 4
    before = layer.data.copy()
    with pytest.raises(SimWorldError, match="mask"):
        layer.diffuse(0.2, mask=np.ones(shape, dtype=bool))
    np.testing.assert_array_equal(layer.data, before)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_exponential_decay_matches_split_intervals_and_preserves_array(dtype):
    whole, split = Layer("whole", 3, 2, dtype=dtype), Layer("split", 3, 2, dtype=dtype)
    whole.data[:] = split.data[:] = [[1, 2, 3], [4, 5, 6]]
    original = whole.data
    whole.decay(0.4, dt=3)
    for _ in range(4):
        split.decay(0.4, dt=0.75)
    np.testing.assert_allclose(whole.data, np.arange(1, 7).reshape(2, 3) * np.exp(-1.2), rtol=2e-6)
    np.testing.assert_allclose(split.data, whole.data, rtol=2e-6)
    assert whole.data is original and whole.data.dtype == np.dtype(dtype)


def test_decay_uses_metadata_unless_overridden_and_does_not_implicitly_clamp():
    layer = Layer("field", 2, 1, default=2, min=2, decay=0.2)
    layer.decay(dt=2)
    np.testing.assert_allclose(layer.data, [[2 * np.exp(-0.4)] * 2])
    layer.decay(rate=0.1, dt=1)
    np.testing.assert_allclose(layer.data, [[2 * np.exp(-0.5)] * 2])
    assert layer.decay_rate == 0.2
    before = layer.data.copy()
    layer.decay(0, dt=10)
    layer.decay(dt=0)
    np.testing.assert_array_equal(layer.data, before)


def test_decay_scales_all_vector_components():
    layer = Layer("vector", 2, 1, default=(2, 4), shape=(2,))
    layer.decay(np.log(2))
    np.testing.assert_allclose(layer.data, [[[1, 2], [1, 2]]])


@pytest.mark.parametrize("rate, dt", [(-1, 1), (float("nan"), 1), (float("inf"), 1),
                                     (1, -1), (1, float("nan")), (1, float("inf"))])
def test_invalid_decay_rate_or_time_raises_without_mutation(rate, dt):
    layer = Layer("field", 2, 1, default=3)
    with pytest.raises(SimWorldError, match="non-negative"):
        layer.decay(rate, dt=dt)
    np.testing.assert_array_equal(layer.data, [[3, 3]])


@pytest.mark.parametrize("dtype", ["int16", bool])
@pytest.mark.parametrize("operation", ["diffuse", "decay"])
def test_field_evolution_requires_floating_point_storage(dtype, operation):
    layer = Layer("discrete", 2, 1, dtype=dtype, default=1)
    with pytest.raises(SimWorldError, match="float"):
        getattr(layer, operation)(0.1)
    np.testing.assert_array_equal(layer.data, [[1, 1]])
