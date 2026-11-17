"""Spatial bucket maintenance and radius searches against independent oracles."""

from math import hypot

import numpy as np
import pytest

from simworld import Position
from simworld.spatial import SpatialHash


def test_insert_moves_entities_between_buckets_without_duplicates():
    spatial = SpatialHash(cell_size=4)
    positions = {1: Position(0, 0), 2: Position(3, 3)}
    spatial.sync(positions)
    assert spatial._cells == {(0, 0): {1, 2}}
    spatial.insert(1, 1, 1)  # Same bucket: no extra membership.
    positions[1] = Position(8, 1)
    spatial.insert(1, 8, 1)
    assert spatial._cells == {(0, 0): {2}, (2, 0): {1}}
    assert spatial.query(8, 1, 0, positions) == [(0.0, 1)]
    positions[2] = Position(-0.1, -4)
    spatial.insert(2, -0.1, -4)
    assert (0, 0) not in spatial._cells  # Empty buckets are removed.
    assert spatial._where[2] == (-1, -1)
    spatial.insert(2, -4.1, 4)
    assert spatial._where[2] == (-2, 1)
    assert (-1, -1) not in spatial._cells


def test_remove_and_clear_leave_no_stale_bucket_memberships():
    spatial = SpatialHash()
    spatial.insert(1, 1, 1)
    spatial.insert(2, 2, 2)
    spatial.remove(1)
    spatial.remove(1)  # Removing an absent entity is harmless.
    assert spatial._where == {2: (0, 0)}
    assert spatial._cells == {(0, 0): {2}}
    spatial.remove(2)
    assert spatial._cells == spatial._where == {}
    spatial.insert(3, -10, 10)
    spatial.clear()
    assert spatial._cells == spatial._where == {}
    assert spatial.query(0, 0, 20, {}) == []
    spatial.insert(4, 0, 0)
    assert spatial.query(0, 0, 0, {4: Position()}) == [(0.0, 4)]


def test_sync_updates_moves_and_removes_entities_that_lost_position():
    spatial = SpatialHash(cell_size=2)
    positions = {1: Position(0, 0), 2: Position(1, 1)}
    spatial.sync(positions)
    positions[1].x = 10
    assert spatial.query(10, 0, 0, positions) == []  # Cross-bucket edits need sync.
    spatial.sync(positions)
    assert spatial.query(10, 0, 0, positions) == [(0.0, 1)]
    del positions[2]
    spatial.sync(positions)
    assert spatial._where == {1: (5, 0)}
    assert spatial._cells == {(5, 0): {1}}
    spatial.sync({})
    assert spatial._cells == spatial._where == {}


def test_sync_handles_removed_and_added_entities_with_the_same_store_length():
    spatial = SpatialHash(cell_size=2)
    positions = {1: Position(), 2: Position(10, 0)}
    spatial.sync(positions)
    del positions[1]
    positions[3] = Position(-10, 0)
    spatial.sync(positions)
    assert spatial._where == {2: (5, 0), 3: (-5, 0)}
    assert spatial.query(0, 0, 20, positions) == [(10.0, 2), (10.0, 3)]


def test_query_includes_circle_boundary_filters_box_corners_and_sorts_ties():
    positions = {9: Position(3, 4), 7: Position(-3, -4), 5: Position(0, 0),
                 4: Position(5, 0), 3: Position(4, 4), 2: Position(5.01, 0)}
    for order in [list(positions), list(reversed(positions))]:
        spatial = SpatialHash(cell_size=2.5)
        for entity in order:
            p = positions[entity]
            spatial.insert(entity, p.x, p.y)
        assert spatial.query(0, 0, 5, positions) == [(0.0, 5), (5.0, 4), (5.0, 7), (5.0, 9)]
        assert spatial.query(0, 0, 0, positions) == [(0.0, 5)]


def test_query_reads_current_positions_in_visited_buckets_and_ignores_missing_ones():
    spatial = SpatialHash()
    positions = {1: Position(1, 1), 2: Position(2, 2)}
    spatial.sync(positions)
    positions[1].x = 2  # Movement within a bucket needs no membership change.
    assert spatial.query(2, 1, 0, positions) == [(0.0, 1)]
    del positions[1]
    assert spatial.query(2, 1, 0, positions) == []
    spatial.sync(positions)
    assert 1 not in spatial._where


@pytest.mark.parametrize("cell_size", [0.5, 2, 8, 30])
def test_radius_queries_match_brute_force_after_moves_and_removals(cell_size):
    rng = np.random.default_rng(713)
    positions = {entity: Position(*map(float, xy))
                 for entity, xy in enumerate(rng.uniform(-30, 30, size=(100, 2)), 1)}
    spatial = SpatialHash(cell_size=cell_size)
    for phase in range(3):
        if phase == 1:
            for entity, p in positions.items():
                p.x += (entity % 5) * 7
                p.y -= (entity % 3) * 5
        elif phase == 2:
            for entity in list(positions)[::3]:
                del positions[entity]
        spatial.sync(positions)
        for x, y, radius in [(0, 0, 0), (-15.5, 8.25, 4), (2.5, -3.5, 15), (0, 0, 80)]:
            expected = sorted((hypot(p.x - x, p.y - y), entity)
                              for entity, p in positions.items()
                              if hypot(p.x - x, p.y - y) <= radius)
            actual = spatial.query(x, y, radius, positions)
            assert [entity for _, entity in actual] == [entity for _, entity in expected]
            np.testing.assert_allclose([d for d, _ in actual], [d for d, _ in expected],
                                       rtol=1e-14, atol=1e-14)


@pytest.mark.parametrize("cell_size", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_bucket_sizes_raise_clear_errors(cell_size):
    with pytest.raises(ValueError, match="cell_size"):
        SpatialHash(cell_size)


@pytest.mark.parametrize("radius", [-1, float("nan"), float("inf"), -float("inf")])
def test_invalid_query_radii_raise_clear_errors(radius):
    spatial = SpatialHash()
    with pytest.raises(ValueError, match="radius"):
        spatial.query(0, 0, radius, {})


def test_hashes_are_independent_and_cell_size_can_change_after_clear():
    first, second = SpatialHash(), SpatialHash()
    assert first.cell_size == second.cell_size == 8.0
    positions = {1: Position(7, 0)}
    first.sync(positions)
    assert second.query(7, 0, 0, positions) == []
    first.cell_size = 2
    first.clear()
    first.sync(positions)
    assert first._where[1] == (3, 0)
    assert first.query(7, 0, 0, positions) == [(0.0, 1)]
