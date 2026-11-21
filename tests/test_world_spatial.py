"""World spatial lifecycle, nearby queries and scheduled synchronization."""

from math import hypot

import numpy as np
import pytest

from simworld import Appearance, Position, World
from simworld.errors import (
    MissingComponentError, NotAComponentError, StaleEntityError, UnknownComponentError,
)
from simworld.spatial import SpatialHash
from simworld.worldgen import paint_blobs, random_positions


def test_world_owns_independent_indexes_using_configured_cell_size():
    first, second = World(cell_size=2), World(cell_size=4)
    assert isinstance(first.spatial, SpatialHash) and first.spatial.cell_size == 2
    assert second.spatial.cell_size == 4
    entity = first.spawn(Position(1, 1))
    assert first.nearby((1, 1), 0) == [entity]
    assert second.nearby((1, 1), 0) == []
    assert first.layers == second.layers == {}


def test_spawn_add_replace_remove_and_despawn_update_memberships_immediately():
    world = World(cell_size=2)
    entity = world.spawn(Position(1, 1))
    empty = world.spawn()
    assert world.nearby((1, 1), 0) == [entity]
    world.add(empty, Position(10, 1))
    world.add(entity, Position(10, 1))
    assert world.nearby((1, 1), 0) == []
    assert world.nearby((10, 1), 0) == [entity, empty]
    world.remove(entity, Position)
    assert world.nearby((10, 1), 0) == [empty]
    assert entity not in world.spatial._where
    world.remove(entity, Position)
    world.despawn(empty)
    assert world.nearby((10, 1), 0) == []
    assert world.spatial._where == world.spatial._cells == {}
    replacement = world.spawn(Position(10, 1))
    assert replacement != empty and world.nearby((10, 1), 0) == [replacement]


def test_prefab_and_deferred_lifecycle_use_the_same_index_hooks():
    world = World(cell_size=2)
    world.define_prefab("marker", {"Position": {"x": 5, "y": 5}})
    direct = world.spawn_prefab("marker")
    queued = world.commands.spawn_prefab("marker")
    bare = world.commands.spawn()
    assert world.is_alive(queued) and world.nearby((5, 5), 0) == [direct]
    world.commands.apply()
    assert world.nearby((5, 5), 0) == [direct, queued]
    world.commands.add(bare, Position(5, 5))
    world.commands.remove(direct, Position)
    world.commands.despawn(queued)
    world.commands.apply()
    assert world.nearby((5, 5), 0) == [bare]
    assert direct not in world.spatial._where and queued not in world.spatial._where


def test_failed_component_edits_preserve_spatial_membership():
    world = World(cell_size=2)
    entity = world.spawn(Position(1, 1))
    with pytest.raises(NotAComponentError):
        world.add(entity, Position(10, 1), object())
    with pytest.raises(UnknownComponentError):
        world.remove(entity, Position, "Unregistered")
    assert world.nearby((1, 1), 0) == [entity]
    assert world.nearby((10, 1), 0) == []


def test_nearby_accepts_coordinate_pairs_objects_and_entity_ids():
    world = World()
    source = world.spawn(Position(2, 3))
    close = world.spawn(Position(5, 7))
    world.spawn(Position(18, 18))
    expected = [source, close]
    assert world.nearby((2, 3), 5) == expected
    assert world.nearby([2, 3], 5) == expected
    assert world.nearby(Position(2, 3), 5) == expected
    assert world.nearby(source, 5) == [close]
    assert world.nearby(source, 5, distances=True) == [(5.0, close)]
    assert world.nearby((2, 3), 5, distances=True) == [(0.0, source), (5.0, close)]
    assert world.nearby((2, 3), 5, exclude=source) == [close]
    assert world.nearby(source, 5, exclude=close) == []


def test_nearby_filters_require_all_components_and_preserve_tie_order():
    world = World()
    first = world.spawn(Position(-1, 0), Appearance())
    second = world.spawn(Position(1, 0), Appearance())
    plain = world.spawn(Position(0, 0))
    assert world.nearby((0, 0), 2) == [plain, first, second]
    assert world.nearby((0, 0), 2, with_=(Position, "Appearance")) == [first, second]
    assert world.nearby((0, 0), 2, with_=(Appearance(),), distances=True) == [
        (1.0, first), (1.0, second),
    ]
    world.remove(first, Appearance)
    assert world.nearby((0, 0), 2, with_=(Appearance,)) == [second]
    world.remove(second, Position)
    world.add(second, Position(1, 0))
    world.add(first, Appearance())
    assert world.nearby((0, 0), 2, with_=(Appearance,)) == [first, second]


def test_nearby_unknown_filters_fail_even_when_no_entities_match():
    world = World()
    with pytest.raises(UnknownComponentError):
        world.nearby((0, 0), 1, with_=("Unregistered",))
    with pytest.raises(MissingComponentError):
        world.nearby(world.spawn(), 1)
    old = world.spawn(Position())
    world.despawn(old)
    world.spawn(Position())
    with pytest.raises(StaleEntityError):
        world.nearby(old, 1)
    with pytest.raises(StaleEntityError):
        world.nearby(True, 1)


def test_manual_bucket_crossing_needs_sync_and_queries_do_not_sync_implicitly():
    world = World(cell_size=2)
    entity = world.spawn(Position(1, 1))
    world.get(entity, Position).x = 10
    assert world.nearby((10, 1), 0) == []
    assert world.sync_spatial() is None
    assert world.nearby((10, 1), 0) == [entity]
    world.get(entity, Position).x = 11  # Same bucket: current coordinates are read.
    assert world.nearby((11, 1), 0) == [entity]


def test_core_sync_definitions_are_world_owned_and_have_blueprint_priorities():
    first, second = World(), World()
    expected = [("spatial_sync", "sense", -100), ("spatial_sync_late", "late", 100)]
    assert [(sd.name, sd.stage, sd.order) for sd in first.scheduler.ordered()] == expected
    for name, _, order in expected:
        definition = first.scheduler.get(name)
        assert definition.module == "core" and definition.enabled
        assert definition.every == 1 and definition.base_order == order
        assert definition is not second.scheduler.get(name)
    first.disable_system("spatial_sync")
    assert second.scheduler.get("spatial_sync").enabled


def test_sense_and_late_sync_at_their_scheduled_priorities():
    world = World(cell_size=2)
    entity = world.spawn(Position(1, 1))
    world.get(entity, Position).x = 5
    observed = []

    @world.system(stage="sense", order=-101)
    def before_sense(w):
        observed.append(w.nearby((5, 1), 0))

    @world.system(stage="sense", order=-99)
    def after_sense(w):
        observed.append(w.nearby((5, 1), 0))

    @world.system(stage="update")
    def move(w):
        w.get(entity, Position).x = 9

    @world.system(stage="late", order=99)
    def before_late(w):
        observed.append(w.nearby((9, 1), 0))

    @world.system(stage="late", order=101)
    def after_late(w):
        observed.append(w.nearby((9, 1), 0))

    world.step()
    assert observed == [[], [entity], [], [entity]]
    assert world.nearby((9, 1), 0) == [entity] and world.tick == 1


def test_commands_become_spatially_visible_between_systems():
    world = World()
    seen = []

    @world.system(stage="act")
    def spawn(w):
        w.commands.spawn(Position(4, 5), name="queued")

    @world.system(stage="act", order=1)
    def inspect(w):
        seen.extend(w.nearby((4, 5), 0))
        w.commands.despawn(w.entity("queued"))

    world.step()
    assert len(seen) == 1
    assert world.nearby((4, 5), 0) == [] and world.spatial._where == {}


@pytest.mark.parametrize("cell_size", [1.0, 8.0])
def test_world_nearby_matches_full_scan_through_lifecycle_changes(cell_size):
    world = World(cell_size=cell_size, seed=123)
    for i, xy in enumerate(world.rng.uniform(-20, 20, size=(60, 2))):
        components = [Position(*map(float, xy))]
        if i % 2:
            components.append(Appearance())
        world.spawn(*components)
    for phase in range(3):
        if phase == 1:
            for _, p in world.query(Position):
                p.x += 9
            world.sync_spatial()
        elif phase == 2:
            for i, entity in enumerate(world.entities()):
                if i % 4 == 0:
                    world.despawn(entity)
                elif i % 4 == 1:
                    world.remove(entity, Position)
                elif i % 4 == 2:
                    world.add(entity, Position(-1, 0))
        for x, y, radius in [(0, 0, 5), (-10, 8, 15), (2, 3, 60)]:
            for required in [(), (Appearance,)]:
                expected = sorted((hypot(p.x - x, p.y - y), e)
                                  for e, p in world.query(Position)
                                  if hypot(p.x - x, p.y - y) <= radius and world.has(e, *required))
                actual = world.nearby((x, y), radius, with_=required, distances=True)
                assert [e for _, e in actual] == [e for _, e in expected]
                np.testing.assert_allclose([d for d, _ in actual], [d for d, _ in expected],
                                           rtol=1e-14, atol=1e-14)


def test_generated_world_spatial_queries_match_full_scan_after_scheduled_lifecycle_changes():
    world = World(12, 7, seed=42, modules=(), cell_size=3)
    world.define_terrain("ground", 1)
    world.define_terrain("rock", 3, passable=False)
    world.fill_terrain("ground")
    paint_blobs(world, "rock", 3, radius=(1, 2))
    terrain = world.layers["terrain"].data.copy()
    for i, (x, y) in enumerate(random_positions(world, 30)):
        components = [Position(x, y)]
        if i % 2:
            components.append(Appearance())
        world.spawn(*components)
    world.define_prefab("marker", {"Position": {"x": 6, "y": 3}, "Appearance": {}})

    @world.system(stage="act")
    def edit(w):
        for i, entity in enumerate(w.entities()):
            if i % 7 == 0:
                w.commands.despawn(entity)
            elif i % 4 == 0:
                w.commands.remove(entity, Position)
            elif i % 3 == 0:
                w.commands.add(entity, Position((i + 2) % w.width, 2))
            else:
                p = w.try_get(entity, Position)
                if p is not None:
                    p.x, p.y = (p.x + 4.5) % w.width, (p.y + 0.75) % w.height
        w.commands.spawn_prefab("marker")

    for phase in range(4):
        if phase:
            world.step()  # Commands land between systems; late sync picks up direct moves.
        for x, y, radius in [(6, 3, 0), (6, 3, 2.5), (0, 0, 20)]:
            for required in [(), (Appearance,)]:
                expected = sorted((hypot(p.x - x, p.y - y), e)
                                  for e, p in world.query(Position)
                                  if hypot(p.x - x, p.y - y) <= radius and world.has(e, *required))
                actual = world.nearby((x, y), radius, with_=required, distances=True)
                assert [e for _, e in actual] == [e for _, e in expected]
                np.testing.assert_allclose([d for d, _ in actual], [d for d, _ in expected],
                                           rtol=1e-14, atol=1e-14)
    assert world.tick == 3
    np.testing.assert_array_equal(world.layers["terrain"].data, terrain)
