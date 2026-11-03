"""World construction and shared runtime state."""

import dataclasses as dc

import numpy as np
import pytest

import simworld
from simworld.world import World, WorldSettings
from simworld import Appearance, Position
from simworld.components import Parent
from simworld.errors import (
    DuplicateNameError, MissingComponentError, NotAComponentError,
    SimWorldError, StaleEntityError, UnknownComponentError, UnknownNameError,
)


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


def test_spawn_stores_supplied_instances_and_supports_empty_entities():
    world = World()
    position, appearance = Position(3, 4), Appearance()
    entity = world.spawn(position, appearance, name="hero")
    empty = world.spawn()
    assert world.is_alive(entity) and world.is_alive(empty)
    assert world._stores["Position"][entity] is position
    assert world._stores["Appearance"][entity] is appearance
    assert world._names == {"hero": entity}
    assert world._entity_names == {entity: "hero"}
    assert world._alloc.count_alive() == 2


@pytest.mark.parametrize("failure", ["duplicate_component", "unregistered", "duplicate_name", "invalid_name", "class", "string"])
def test_spawn_validation_failure_leaves_all_world_state_unchanged(failure):
    world = World()
    entity = world.spawn(Position(), name="taken")
    recycled = world.spawn()
    world.despawn(recycled)
    before = (world._alloc.to_dict(), {k: dict(v) for k, v in world._stores.items()},
              dict(world._names), dict(world._entity_names))
    components, name, error = [Appearance()], None, SimWorldError
    if failure == "duplicate_component":
        components = [Position(), Position(2, 3)]
    elif failure == "unregistered":
        components.append(object())
        error = NotAComponentError
    elif failure == "duplicate_name":
        name, error = "taken", DuplicateNameError
    elif failure == "invalid_name":
        name, error = [], TypeError
    elif failure == "class":
        components, error = [Position], NotAComponentError
    else:
        components, error = ["Position"], NotAComponentError
    with pytest.raises(error) as caught:
        world.spawn(*components, name=name)
    if failure == "duplicate_component":
        assert "spawn() got two 'Position' components." in str(caught.value)
    assert (world._alloc.to_dict(), world._stores, world._names, world._entity_names) == before
    assert world.is_alive(entity)
    assert world.spawn() == recycled + (1 << 32)


def test_despawn_cleans_all_stores_and_names_and_prevents_stale_deletion():
    world = World()
    entity = world.spawn(Position(), Appearance(), name="hero")
    survivor = world.spawn(Position(7, 8), name="survivor")
    world.despawn(entity)
    assert not world.is_alive(entity) and world.is_alive(survivor)
    assert all(entity not in store for store in world._stores.values())
    assert world._names == {"survivor": survivor}
    assert world._entity_names == {survivor: "survivor"}
    replacement = world.spawn(Appearance(), name="hero")
    assert replacement != entity and world._names["hero"] == replacement
    before = world._alloc.to_dict()
    with pytest.raises(StaleEntityError):
        world.despawn(entity)
    assert world._alloc.to_dict() == before
    assert world.is_alive(replacement)
    assert world._stores["Appearance"][replacement] == Appearance()


def test_despawn_empty_entity_and_empty_string_name():
    world = World()
    entity = world.spawn(name="")
    world.despawn(entity)
    assert world._names == {} and world._entity_names == {}
    assert world._alloc.count_alive() == 0


def test_world_name_maps_and_entities_are_independent():
    first, second = World(), World()
    first.spawn(Position(), name="same")
    second.spawn(Appearance(), name="same")
    assert list(first._stores) == ["Position"]
    assert list(second._stores) == ["Appearance"]
    assert first._names is not second._names
    assert first._entity_names is not second._entity_names


@pytest.mark.parametrize("reference", [Position, "Position", Position()])
def test_component_lookup_accepts_registered_classes_names_and_instances(reference):
    world = World()
    position = Position(2, 5)
    entity = world.spawn(position)
    assert world.get(entity, reference) is position
    assert world.try_get(entity, reference) is position
    assert world.has(entity, reference)
    world.remove(entity, reference)
    assert world.try_get(entity, reference) is None
    assert not world.has(entity, reference)


def test_add_replaces_component_instances_and_has_requires_all_components():
    world = World()
    entity = world.spawn(Position())
    other = world.spawn(Position())
    replacement, appearance = Position(7, 8), Appearance()
    world.add(entity, replacement, appearance)
    assert world.get(entity, Position) is replacement
    assert world.get(entity, Appearance) is appearance
    assert world.has(entity, Position, "Appearance")
    assert not world.has(other, Position, Appearance)
    assert list(world._stores["Position"]) == [entity, other]
    world.remove(entity, Appearance, Position)
    world.remove(entity, Appearance)  # Removing an absent registered type is harmless.
    assert world.components_of(entity) == {}
    assert world.is_alive(entity)


def test_missing_component_error_is_distinct_from_stale_entity_error():
    world = World()
    entity = world.spawn(Position())
    with pytest.raises(MissingComponentError) as caught:
        world.get(entity, Appearance)
    message = str(caught.value)
    assert str(entity) in message and "Appearance" in message and "Position" in message
    world.despawn(entity)
    replacement = world.spawn(Appearance())
    for operation in [lambda: world.get(entity, Position),
                      lambda: world.add(entity, Position()),
                      lambda: world.remove(entity, Position),
                      lambda: world.components_of(entity)]:
        with pytest.raises(StaleEntityError):
            operation()
    assert world.has(replacement, Appearance)


@pytest.mark.parametrize("dead", [0, -1, None, [], 1 << 60])
def test_optional_component_access_is_safe_for_invalid_or_dead_ids(dead):
    world = World()
    assert world.try_get(dead, Position) is None
    assert world.has(dead, Position) is False
    assert world.try_get(dead, "Unregistered") is None
    assert world.has(dead, "Unregistered") is False
    with pytest.raises(StaleEntityError):
        world.get(dead, Position)


def test_stale_optional_access_does_not_find_replacement_entity():
    world = World()
    old = world.spawn(Position())
    world.despawn(old)
    world.spawn(Position(4, 5))
    assert world.try_get(old, Position) is None
    assert world.has(old, Position) is False


def test_components_of_returns_independent_mapping_with_original_instances():
    world = World()
    position = Position()
    entity = world.spawn(position, Appearance())
    components = world.components_of(entity)
    assert list(components) == ["Position", "Appearance"]
    assert components["Position"] is position
    components.clear()
    assert world.has(entity, Position, Appearance)


def test_component_mutations_validate_all_arguments_before_changing_stores():
    world = World()
    entity = world.spawn(Position())
    before = world.components_of(entity)
    with pytest.raises(NotAComponentError):
        world.add(entity, Appearance(), object())
    with pytest.raises(NotAComponentError):
        world.add(entity, Appearance)
    with pytest.raises(UnknownComponentError):
        world.remove(entity, Position, "Unregistered")
    assert world.components_of(entity) == before
    assert "Appearance" not in world._stores
    for operation in [world.get, world.try_get, world.has]:
        with pytest.raises(UnknownComponentError):
            operation(entity, "Unregistered")


def test_false_valued_components_remain_present(clean_components):
    @simworld.component
    class FalseValue:
        def __bool__(self):
            return False

    world = World()
    component = FalseValue()
    entity = world.spawn(component)
    assert world.get(entity, FalseValue) is component
    assert world.try_get(entity, FalseValue) is component
    assert world.has(entity, FalseValue)


def test_query_uses_smallest_store_order_and_preserves_requested_tuple_order():
    world = World()
    first = world.spawn(Position(1, 1))
    second = world.spawn(Position(2, 2))
    world.spawn(Position(3, 3))
    world.add(second, Appearance(size=2))
    world.add(first, Appearance(size=3))
    rows = list(world.query("Position", Appearance))
    assert [row[0] for row in rows] == [second, first]
    for entity, position, appearance in rows:
        assert position is world.get(entity, Position)
        assert appearance is world.get(entity, Appearance)
    assert [row[0] for row in world.query(Appearance, Position)] == [second, first]


def test_query_ties_follow_first_requested_store_order():
    world = World()
    first, second = world.spawn(Position()), world.spawn(Position())
    world.add(second, Appearance())
    world.add(first, Appearance())
    assert [row[0] for row in world.query(Position, Appearance)] == [first, second]
    assert [row[0] for row in world.query(Appearance, Position)] == [second, first]


def test_query_excludes_any_requested_type_and_handles_empty_intersections():
    world = World()
    keep = world.spawn(Position())
    world.spawn(Position(), Appearance())
    world.spawn(Position(), Parent())
    assert [row[0] for row in world.query(Position, without=(Appearance, "Parent"))] == [keep]
    assert list(world.query(Appearance, Parent)) == []
    assert list(World().query(Position)) == []


@pytest.mark.parametrize("multiple", [False, True])
def test_query_allows_despawn_during_iteration(multiple):
    world = World()
    entities = [world.spawn(Position(), Appearance()) for _ in range(4)]
    requested = (Position, Appearance) if multiple else (Position,)
    seen = []
    for row in world.query(*requested):
        seen.append(row[0])
        world.despawn(row[0])
    assert seen == entities
    assert world.count() == 0


def test_query_snapshots_at_call_time_and_skips_deleted_ids_after_reuse():
    world = World()
    old = world.spawn(Position())
    keep = world.spawn(Position())
    rows = world.query(Position)
    world.despawn(old)
    replacement = world.spawn(Position())
    assert [row[0] for row in rows] == [keep]
    assert world.has(replacement, Position)


@pytest.mark.parametrize("removed", [Position, Appearance])
def test_multi_component_query_rechecks_membership_before_yielding(removed):
    world = World()
    entity = world.spawn(Position(), Appearance())
    rows = world.query(Position, Appearance)
    world.remove(entity, removed)
    assert list(rows) == []


def test_query_and_count_reject_unknown_components_and_empty_query_immediately():
    world = World()
    with pytest.raises(SimWorldError, match="at least one component"):
        world.query()
    for request in [lambda: world.query("Unregistered"),
                    lambda: world.query(Position, without=("Unregistered",)),
                    lambda: world.count("Unregistered")]:
        with pytest.raises(UnknownComponentError):
            request()


def test_entity_listing_and_counts_include_empty_entities_and_current_generations():
    world = World()
    empty = world.spawn()
    first = world.spawn(Position(), Appearance())
    second = world.spawn(Position())
    assert world.entities() == [empty, first, second]
    snapshot = world.entities()
    snapshot.clear()
    assert world.count() == 3
    assert world.count(Position) == 2
    assert world.count(Position, Appearance) == 1
    assert world.count(Position, without=(Appearance,)) == 1
    world.despawn(empty)
    replacement = world.spawn()
    assert world.entities() == [replacement, first, second]
    assert world.count() == 3 and empty not in world.entities()


def test_entity_naming_supports_lookup_rename_and_name_removal():
    world = World()
    entity = world.spawn(name="original")
    assert world.entity("original") == entity
    assert world.name_of(entity) == "original"
    world.set_name(entity, "renamed")
    assert world.entity("renamed") == entity
    assert world.name_of(entity) == "renamed"
    assert world._names == {"renamed": entity}
    assert world._entity_names == {entity: "renamed"}
    with pytest.raises(UnknownNameError):
        world.entity("original")
    world.set_name(entity, None)
    assert world.name_of(entity) is None
    assert world._names == {} and world._entity_names == {}
    assert world.is_alive(entity)
    world.set_name(entity, None)


def test_same_entity_name_is_a_noop_and_empty_string_remains_a_valid_name():
    world = World()
    first, second = world.spawn(name="first"), world.spawn(name="second")
    world.set_name(first, "first")
    assert list(world._names) == ["first", "second"]
    world.set_name(first, "")
    assert world.entity("") == first
    world.set_name(first, None)
    world.set_name(second, "")
    assert world.name_of(second) == "" and world.entity("") == second
    world.despawn(second)
    with pytest.raises(UnknownNameError):
        world.entity("")


def test_duplicate_rename_preserves_both_existing_names_and_world_state():
    world = World()
    first, second = world.spawn(name="first"), world.spawn(name="second")
    before = (dict(world._names), dict(world._entity_names), world._alloc.to_dict())
    with pytest.raises(DuplicateNameError, match="second"):
        world.set_name(first, "second")
    assert (world._names, world._entity_names, world._alloc.to_dict()) == before
    assert world.entity("first") == first and world.entity("second") == second


@pytest.mark.parametrize("invalid", [123, [], False])
def test_invalid_name_edits_are_atomic(invalid):
    world = World()
    entity = world.spawn(name="original")
    before = (dict(world._names), dict(world._entity_names))
    with pytest.raises(TypeError):
        world.set_name(entity, invalid)
    with pytest.raises(TypeError):
        world.entity(invalid)
    assert (world._names, world._entity_names) == before


def test_stale_id_cannot_read_or_change_replacement_entity_name():
    world = World()
    old = world.spawn(name="hero")
    world.despawn(old)
    current = world.spawn(name="hero")
    for operation in [lambda: world.set_name(old, "other"), lambda: world.name_of(old)]:
        with pytest.raises(StaleEntityError):
            operation()
    assert world.entity("hero") == current
    assert world.name_of(current) == "hero"
    assert world._names == {"hero": current}
    assert world._entity_names == {current: "hero"}


def test_unknown_entity_names_give_entity_specific_suggestions():
    world = World()
    world.spawn(name="walker")
    with pytest.raises(UnknownNameError) as caught:
        world.entity("walkre")
    message = str(caught.value)
    assert "Unknown entity" in message and "walker" in message and "Did you mean" in message
    assert world.name_of(world.spawn()) is None
