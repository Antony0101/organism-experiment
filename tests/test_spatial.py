from __future__ import annotations

from sim_sandbox.spatial import SpatialHash


def test_insert_move_query_and_remove() -> None:
    spatial = SpatialHash(cell_size=10)
    spatial.insert(1, 2, 3)
    spatial.insert(2, 12, 3)

    assert spatial.query_rect(0, 0, 9, 9) == [1]
    assert spatial.query_radius(7, 3, 6) == [1, 2]

    spatial.update(1, 25, 25)
    assert spatial.query_rect(0, 0, 9, 9) == []
    assert spatial.query_radius(25, 25, 0) == [1]

    spatial.remove(1)
    assert list(spatial.ids) == [2]


def test_queries_are_sorted_and_validate_radius() -> None:
    spatial = SpatialHash(cell_size=5)
    spatial.insert(9, 1, 1)
    spatial.insert(2, 2, 2)
    assert spatial.query_rect(0, 0, 4, 4) == [2, 9]

