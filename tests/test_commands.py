"""Deferred structural changes and bounded command application rounds."""

import pytest

from simworld import Appearance, Position, World
from simworld.errors import (
    DuplicateNameError, MissingComponentError, SerializationError,
    SimWorldError, StaleEntityError,
)


def test_spawn_reserves_live_id_without_components_or_name_until_apply():
    world = World()
    position = Position(2, 3)
    entity = world.commands.spawn(position, name="walker")
    assert world.is_alive(entity)
    assert world.entities() == [entity] and world.count() == 1
    assert list(world.query(Position)) == []
    assert world.components_of(entity) == {} and world.name_of(entity) is None
    assert world.commands.apply() == 1
    assert list(world.query(Position)) == [(entity, position)]
    assert world.get(entity, Position) is position
    assert world.entity("walker") == entity
    assert world.commands.apply() == 0


def test_queued_mutations_target_reserved_ids_and_preserve_queue_order():
    world = World()
    commands = world.commands
    entity = commands.spawn(Position())
    commands.add(entity, Appearance(size=3))
    commands.remove(entity, Position)
    observed = []
    commands.defer(lambda w: observed.append(w.components_of(entity)))
    commands.add(entity, Position(7, 8))
    commands.despawn(entity)
    assert world.is_alive(entity) and world.components_of(entity) == {}
    assert commands.apply(world) == 6
    assert observed == [{"Appearance": Appearance(size=3)}]
    assert not world.is_alive(entity)
    assert list(world.query(Position)) == list(world.query(Appearance)) == []


def test_prefabs_are_built_when_queued_and_can_receive_later_commands():
    world = World()
    world.define_prefab("walker", {"Position": {"x": 1}, "Appearance": {}})
    overrides = {"x": 4}
    entity = world.commands.spawn_prefab(
        "walker", entity_name="hero", Position=overrides, Appearance=None,
        **{"Position.y": 6},
    )
    overrides["x"] = 99
    world.define_prefab("walker", {"Position": {"x": 100}})
    world.commands.add(entity, Appearance(size=2))
    assert world.components_of(entity) == {}
    assert world.commands.apply() == 2
    assert world.get(entity, Position) == Position(4, 6)
    assert world.get(entity, Appearance).size == 2
    assert world.entity("hero") == entity
    allocation = world._alloc.to_dict()
    with pytest.raises(SerializationError):
        world.commands.spawn_prefab("walker", Position={"bad": 1})
    assert world._alloc.to_dict() == allocation
    assert world.commands.apply() == 0


def test_callbacks_queue_work_for_the_next_round():
    world = World()
    observed = []

    def enqueue(w):
        observed.append("first")
        entity = w.commands.spawn(Position(9, 1))
        w.commands.defer(lambda current: observed.append(current.get(entity, Position).x))

    world.commands.defer(enqueue)
    world.commands.defer(lambda w: observed.append(w.count(Position)))
    assert world.commands.apply(max_rounds=2) == 4
    assert observed == ["first", 0, 9]


def test_recursive_defers_are_bounded_and_leave_next_round_pending():
    world = World()
    calls = []

    def repeat(w):
        calls.append(w)
        w.commands.defer(repeat)

    world.commands.defer(repeat)
    with pytest.raises(RuntimeError, match="Command buffer did not settle"):
        world.commands.apply(max_rounds=3)
    assert calls == [world] * 3
    with pytest.raises(RuntimeError, match="Command buffer did not settle"):
        world.commands.apply(max_rounds=1)
    assert calls == [world] * 4


def test_world_buffers_are_independent_and_empty_spawns_work():
    world, other = World(), World()
    entity = world.commands.spawn(name="empty")
    assert other.commands.apply() == 0 and other.entities() == []
    assert world.commands.apply() == 1
    assert world.entity("empty") == entity and world.components_of(entity) == {}


def test_invalid_spawn_completion_does_not_partially_attach_components():
    world = World()
    entity = world.commands.spawn(Position(), Position(2, 3))
    with pytest.raises(SimWorldError, match="two 'Position'"):
        world.commands.apply()
    assert world.components_of(entity) == {}
    world.spawn(name="taken")
    entity = world.commands.spawn(Position(), name="taken")
    with pytest.raises(DuplicateNameError):
        world.commands.apply()
    assert world.components_of(entity) == {} and world.name_of(entity) is None


def test_repeated_despawns_skip_stale_targets_and_accumulate_per_buffer():
    world, other = World(), World()
    commands = world.commands
    assert commands.strict is False and commands.skipped == 0
    entity = world.spawn(Position())
    survivor = world.spawn()
    commands.despawn(entity)
    commands.despawn(entity)
    commands.add(survivor, Position(7, 8))
    assert commands.apply() == 2
    assert commands.skipped == 1
    assert world.get(survivor, Position) == Position(7, 8)
    assert commands.apply() == 0 and commands.skipped == 1
    commands.despawn(entity)
    assert commands.apply() == 0 and commands.skipped == 2
    assert other.commands.skipped == 0 and other.commands.strict is False


@pytest.mark.parametrize("operation", ["spawn", "despawn", "add", "remove", "defer"])
@pytest.mark.parametrize("strict", [False, True])
def test_stale_operations_never_mutate_a_reused_slot(operation, strict):
    world = World()
    commands = world.commands
    commands.strict = strict
    if operation == "spawn":
        entity = commands.spawn(Position(1, 2), name="old")
    else:
        entity = world.spawn(Position(1, 2))
        if operation == "despawn":
            commands.despawn(entity)
        elif operation == "add":
            commands.add(entity, Appearance())
        elif operation == "remove":
            commands.remove(entity, Position)
        else:
            commands.defer(lambda w: w.get(entity, Position))
    world.despawn(entity)
    replacement = world.spawn(Position(9, 10), name="new")

    if strict:
        with pytest.raises(StaleEntityError):
            commands.apply()
        assert commands.skipped == 0
    else:
        assert commands.apply() == 0
        assert commands.skipped == 1
    assert world.entities() == [replacement]
    assert world.components_of(replacement) == {"Position": Position(9, 10)}
    assert world.name_of(replacement) == "new"


def test_stale_commands_queued_by_callbacks_skip_without_stopping_later_rounds():
    world = World()
    survivor = world.spawn(Position())
    observed = []

    def enqueue(w):
        entity = w.commands.spawn(Position(2, 3))
        w.commands.despawn(entity)
        w.commands.despawn(entity)
        w.commands.add(entity, Appearance())
        w.commands.remove(survivor, Position)

    world.commands.defer(enqueue)
    world.commands.defer(lambda w: observed.append(w.count(Position)))
    assert world.commands.apply(max_rounds=2) == 5
    assert world.commands.skipped == 2
    assert observed == [1]
    assert world.entities() == [survivor] and world.components_of(survivor) == {}


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("error_type", [MissingComponentError, DuplicateNameError, ValueError])
def test_non_stale_callback_errors_propagate_and_preserve_next_round(strict, error_type):
    world = World()
    commands = world.commands
    commands.strict = strict
    observed = []
    error = error_type("callback failed")

    def fail(w):
        observed.append("before error")
        w.commands.defer(lambda current: observed.append("next round"))
        raise error

    commands.defer(fail)
    commands.defer(lambda w: observed.append("detached tail"))
    with pytest.raises(error_type) as caught:
        commands.apply()
    assert caught.value is error
    assert commands.skipped == 0
    assert observed == ["before error"]
    assert commands.apply() == 1
    assert observed == ["before error", "next round"]
