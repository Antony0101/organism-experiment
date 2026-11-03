"""System metadata and registration context contracts."""

import pytest

import simworld
from simworld import World
from simworld.errors import DuplicateNameError
from simworld.registry import active_world, loading_into
from simworld.systems import SystemDef, system


def test_system_definition_defaults_and_decorator_metadata_preserve_function():
    calls = []

    def update(world):
        """Update the world."""
        calls.append(world)

    decorated = system(update, order=3, reads=["Position"], writes=["Appearance"], every=2)
    assert decorated is update and calls == []
    definition = decorated.__sim_system__
    assert isinstance(definition, SystemDef)
    assert (definition.name, definition.fn, definition.stage) == ("update", update, "update")
    assert definition.order == 3 and definition.base_order == 3
    assert definition.reads == ("Position",) and definition.writes == ("Appearance",)
    assert definition.every == 2 and definition.enabled and definition.module is None
    assert definition.doc == "Update the world."
    plain = SystemDef("plain", update)
    assert plain.reads == plain.writes == ()
    assert plain.every == 1 and plain.seq == 0 and plain.base_order == 0
    assert simworld.system is system and "system" in simworld.__all__


def test_outside_context_registration_is_explicit_and_world_definitions_are_independent():
    @system(name="movement", stage="act", order=4)
    def move(world):
        pass

    first, second = World(), World()
    assert first._systems == {} and second._systems == {}
    first.register(move)
    second.register(move)
    assert first._systems["movement"].fn is move
    assert first._systems["movement"] is not second._systems["movement"]
    first._systems["movement"].enabled = False
    assert second._systems["movement"].enabled and move.__sim_system__.enabled


def test_nested_registration_contexts_restore_outer_world_even_after_error():
    first, second = World(), World()
    assert active_world() is None
    with loading_into(first):
        assert active_world() is first

        @system
        def outer(world):
            pass

        with pytest.raises(RuntimeError, match="context probe"):
            with loading_into(second):
                assert active_world() is second

                @system()
                def inner(world):
                    pass

                raise RuntimeError("context probe")
        assert active_world() is first
    assert active_world() is None
    assert list(first._systems) == ["outer"] and list(second._systems) == ["inner"]


def test_context_restores_after_duplicate_registration_error():
    world = World()

    @system
    def update(world):
        pass

    world.register(update)
    original = world._systems["update"]
    with pytest.raises(DuplicateNameError):
        with loading_into(world):
            system(update)
    assert active_world() is None and world._systems["update"] is original


def test_explicit_system_registration_copies_overrides_and_module_origin():
    world = World()

    def update(world):
        pass

    definition = SystemDef("update", update, order=7)
    world._current_module = "example"
    registered = world.add_system(definition, name="custom", order=9, every=3)
    assert world._systems["custom"] is registered
    assert registered.module == "example"
    assert registered.base_order == 7 and registered.order == 9 and registered.every == 3
    assert definition.name == "update" and definition.order == 7 and definition.module is None
    assert world.add_system(update, name="plain").fn is update
    with pytest.raises(TypeError):
        world.register(object())
