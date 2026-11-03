"""System metadata and registration context contracts."""

import pytest

import simworld
from simworld import World
from simworld.errors import DuplicateNameError, UnknownSystemError
from simworld.registry import active_world, loading_into
from simworld.systems import DEFAULT_STAGES, Scheduler, SystemDef, system


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


def test_scheduler_stage_order_and_registration_sequence_break_ties():
    world = World()
    scheduler = world.scheduler
    assert isinstance(scheduler, Scheduler)
    assert scheduler.stages == ["input", "sense", "decide", "act", "update", "late"]
    assert tuple(scheduler.stages) == DEFAULT_STAGES == simworld.DEFAULT_STAGES
    calls = []
    for name, stage, order in [("late", "late", -10), ("first", "update", 2),
                               ("input", "input", 99), ("second", "update", 2),
                               ("early", "update", -1)]:
        scheduler.add(SystemDef(name, lambda w, name=name: calls.append(name),
                                stage=stage, order=order, seq=999))
    assert scheduler.get("first").seq < scheduler.get("second").seq
    assert [s.name for s in scheduler.ordered()] == ["input", "early", "first", "second", "late"]
    scheduler.run_step()
    assert calls == ["input", "early", "first", "second", "late"]
    assert world.tick == 0 and world.time == 0  # Clock advancement belongs to World.step.


def test_custom_stages_and_invalid_stage_edits():
    scheduler = World().scheduler
    scheduler.add_stage("prepare", before="input")
    scheduler.add_stage("cleanup", after="update")
    scheduler.add_stage("final")
    assert scheduler.stages == ["prepare", "input", "sense", "decide", "act", "update", "cleanup", "late", "final"]
    before = scheduler.stages[:]
    with pytest.raises(DuplicateNameError):
        scheduler.add_stage("input")
    with pytest.raises(ValueError):
        scheduler.add_stage("bad", before="input", after="late")
    with pytest.raises(UnknownSystemError, match="stage"):
        scheduler.add_stage("bad", after="missing")
    assert scheduler.stages == before
    scheduler.add(SystemDef("custom", lambda w: None, stage="cleanup"))
    assert scheduler.ordered()[0].name == "custom"


def test_scheduler_registration_errors_replacement_removal_and_enabled_flags():
    scheduler = World().scheduler
    original = SystemDef("same", lambda w: None)
    scheduler.add(original)
    with pytest.raises(DuplicateNameError):
        scheduler.add(SystemDef("same", lambda w: None))
    with pytest.raises(UnknownSystemError, match="stage"):
        scheduler.add(SystemDef("bad", lambda w: None, stage="missing"))
    assert list(scheduler.systems) == ["same"] and scheduler.get("same") is original
    replacement = SystemDef("same", lambda w: None)
    scheduler.add(replacement, replace=True)
    assert scheduler.get("same") is replacement and replacement.seq > original.seq
    scheduler.set_enabled("same", False)
    assert not replacement.enabled
    scheduler.remove("same")
    assert scheduler.ordered() == []
    for operation in [scheduler.get, scheduler.remove, lambda n: scheduler.set_enabled(n, True)]:
        with pytest.raises(UnknownSystemError):
            operation("same")


def test_scheduler_cache_invalidates_on_membership_stage_and_explicit_order_edits():
    world = World()
    scheduler = world.scheduler
    calls = []
    world.add_system(lambda w: calls.append("a"), name="a", order=1)
    scheduler.ordered()
    cached = scheduler._sorted
    scheduler.ordered()
    assert scheduler._sorted is cached
    world.add_system(lambda w: calls.append("b"), name="b", order=2)
    assert scheduler._sorted is None
    scheduler.run_step()
    assert calls == ["a", "b"]
    scheduler.get("b").order = 0
    scheduler._sorted = None  # Direct metadata edits must invalidate the cache (§5.8).
    calls.clear()
    scheduler.run_step()
    assert calls == ["b", "a"]
    scheduler.remove("a")
    assert scheduler._sorted is None
    assert [s.name for s in scheduler.ordered()] == ["b"]
    scheduler.add_stage("custom")
    assert scheduler._sorted is None
    scheduler.ordered()
    scheduler.add(SystemDef("b", lambda w: None), replace=True)
    assert scheduler._sorted is None


def test_scheduler_gates_disabled_modules_and_every_n_ticks_without_enforcing_reads_writes():
    world = World()
    calls = []
    world.module_enabled = lambda name: name != "disabled_module"
    for name, options in [("always", {"every": 0}), ("even", {"every": 2}),
                          ("disabled", {"enabled": False}),
                          ("module", {"module": "disabled_module"})]:
        world.scheduler.add(SystemDef(name, lambda w, name=name: calls.append((w.tick, name)),
                                      reads=("UnknownData",), writes=("UnknownData",), **options))
    for tick in range(4):
        world.resources["tick"] = tick
        world.scheduler.run_step()
    assert calls == [(0, "always"), (0, "even"), (1, "always"),
                     (2, "always"), (2, "even"), (3, "always")]
    world.scheduler.set_enabled("disabled", True)
    world.module_enabled = lambda name: True
    calls.clear()
    world.scheduler.run_step()
    assert calls == [(3, "always"), (3, "disabled"), (3, "module")]


def test_scheduler_profiling_accumulates_enabled_system_time(monkeypatch):
    scheduler = World().scheduler
    scheduler.add(SystemDef("active", lambda w: None))
    scheduler.add(SystemDef("disabled", lambda w: None, enabled=False))
    clock = iter([1.0, 1.25, 2.0, 2.5])
    monkeypatch.setattr("simworld.systems.perf_counter", lambda: next(clock))
    scheduler.run_step()
    assert scheduler.timings == {}
    scheduler.profile = True
    scheduler.run_step()
    scheduler.run_step()
    assert scheduler.timings == {"active": 0.75}


def test_world_registration_uses_scheduler_stage_validation_and_context():
    world = World()
    with loading_into(world):
        @system(stage="act", name="move")
        def move(world):
            pass
    assert world.scheduler.get("move").fn is move
    assert world._systems is world.scheduler.systems
    with pytest.raises(UnknownSystemError, match="stage"):
        world.add_system(move, name="invalid", stage="missing")
    assert list(world.scheduler.systems) == ["move"]
