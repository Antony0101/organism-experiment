"""Prefab validation, overrides and ownership of mutable data."""

from types import MappingProxyType

import pytest

from simworld import Appearance, Position, World, component, prop
from simworld.errors import SerializationError, SimWorldError, UnknownComponentError, UnknownPrefabError


pytestmark = pytest.mark.usefixtures("clean_components")


def test_partial_prefabs_accept_mapping_inputs_and_registered_class_keys():
    world = World()
    world.define_prefab("walker", MappingProxyType({Position: {"x": 2}, "Appearance": {}}))
    entity = world.spawn_prefab("walker", entity_name="hero")
    assert world.get(entity, Position) == Position(2, 0)
    assert world.get(entity, Appearance) == Appearance()
    assert world.entity("hero") == entity
    assert world.prefabs == {"walker": {"Position": {"x": 2}, "Appearance": {}}}


def test_nested_and_dotted_overrides_merge_with_template_fields_and_restore_tuples():
    world = World()
    world.define_prefab("walker", {"Position": {"x": 1, "y": 2}, "Appearance": {"size": 3}})
    entity = world.spawn_prefab("walker", Position={"x": 9}, **{"Position.y": 8},
                               Appearance={"color": [10, 20, 30]})
    assert world.get(entity, Position) == Position(9, 8)
    assert world.get(entity, Appearance) == Appearance((10, 20, 30), 3)
    assert world.get(world.spawn_prefab("walker"), Position) == Position(1, 2)


def test_component_replacement_removal_and_new_components():
    world = World()
    world.define_prefab("walker", {"Position": {"x": 1}, "Appearance": {}})
    replacement = Position(8, 9)
    entity = world.spawn_prefab("walker", Position=replacement, Appearance=None)
    assert world.get(entity, Position) == replacement
    assert world.get(entity, Position) is not replacement
    assert not world.has(entity, Appearance)
    patched = world.spawn_prefab("walker", Position=replacement, **{"Position.x": 6})
    assert world.get(patched, Position) == Position(6, 9)
    assert replacement == Position(8, 9)
    with pytest.raises(SerializationError):
        world.spawn_prefab("walker", Position=replacement, **{"Position.bad": 1})
    world.define_prefab("empty", {})
    assert world.has(world.spawn_prefab("empty", Appearance={"size": 4}), Appearance)
    with pytest.raises(SimWorldError):
        world.spawn_prefab("walker", Position=Appearance())


def test_prefab_input_override_and_spawned_mutable_values_are_independent():
    @component
    class Bag:
        contents: dict = prop(default_factory=dict)

    world = World()
    definition = {"Bag": {"contents": {"items": [1]}}}
    world.define_prefab("bag", definition)
    definition["Bag"]["contents"]["items"].append(99)
    first, second = world.spawn_prefab("bag"), world.spawn_prefab("bag")
    world.get(first, Bag).contents["items"].append(2)
    assert world.get(second, Bag).contents == {"items": [1]}
    overrides = {"contents": {"items": [7]}}
    third = world.spawn_prefab("bag", Bag=overrides)
    world.get(third, Bag).contents["items"].append(8)
    assert overrides == {"contents": {"items": [7]}}
    snapshot = world.prefabs
    snapshot["bag"]["Bag"]["contents"]["items"].append(5)
    assert world.get(world.spawn_prefab("bag"), Bag).contents == {"items": [1]}


def test_invalid_definitions_fail_before_replacing_existing_prefab():
    world = World()
    world.define_prefab("walker", {"Position": {"x": 1}})
    before = world.prefabs
    for spec, error in [({"Position": {"bad": 3}}, SerializationError),
                        ({"Missing": {}}, UnknownComponentError),
                        ({"Position": 5}, SerializationError)]:
        with pytest.raises(error):
            world.define_prefab("walker", spec)
        assert world.prefabs == before
    world.define_prefab("walker", {"Position": {"x": 4}})
    assert world.get(world.spawn_prefab("walker"), Position).x == 4


def test_failed_overrides_consume_no_id_and_preserve_template():
    world = World()
    world.define_prefab("walker", {"Position": {}})
    before, allocation = world.prefabs, world._alloc.to_dict()
    for overrides, error in [({"Position": {"bad": 1}}, SerializationError),
                             ({"Position.bad": 1}, SerializationError),
                             ({"Missing": None}, UnknownComponentError),
                             ({"Position": 2}, SimWorldError)]:
        with pytest.raises(error):
            world.spawn_prefab("walker", **overrides)
        assert world.prefabs == before and world._alloc.to_dict() == allocation
    assert world._stores == {}


def test_unknown_prefabs_list_known_names_and_worlds_keep_separate_templates():
    world, other = World(), World()
    world.define_prefab("walker", {})
    with pytest.raises(UnknownPrefabError) as caught:
        world.spawn_prefab("walkre")
    assert "walker" in str(caught.value) and "Did you mean" in str(caught.value)
    assert other.prefabs == {}
