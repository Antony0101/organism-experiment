"""World run loops, clock ownership and scheduled structural mutation."""

import pytest

from simworld import Appearance, Position, StaleEntityError, World
from simworld.errors import DuplicateNameError, UnknownSystemError
from simworld.registry import active_world, loading_into


def test_bound_system_decorator_registers_once_and_restores_outer_context():
    world, other = World(), World()
    with loading_into(other):
        @world.system(stage="act", order=3, reads=("Position",),
                      writes=("Appearance",), name="bound", every=2)
        def update(w):
            """A bound system."""
            pass
        assert active_world() is other
        with pytest.raises(DuplicateNameError):
            world.system(name="bound")(update)
        assert active_world() is other
    assert active_world() is None
    assert [sd.name for sd in other.scheduler.ordered()] == ["spatial_sync", "spatial_sync_late"]
    definition = world.scheduler.get("bound")
    assert definition.fn is update and definition.stage == "act"
    assert (definition.order, definition.base_order, definition.every) == (3, 3, 2)
    assert definition.reads == ("Position",) and definition.writes == ("Appearance",)
    assert definition.doc == "A bound system."
    assert definition is not update.__sim_system__


def test_world_enable_disable_and_every_n_tick_gates():
    world = World(dt=0.5)
    calls = []

    @world.system(every=2)
    def even(w):
        calls.append((w.tick, w.time))

    world.disable_system("even")
    world.step()
    world.enable_system("even")
    world.run(3)
    assert calls == [(2, 1.0)]
    assert world.tick == 4 and world.time == 2
    world.enable_system("even", False)
    world.step()
    assert calls == [(2, 1.0)]
    for change in [world.enable_system, world.disable_system]:
        with pytest.raises(UnknownSystemError):
            change("missing")


def test_systems_see_previous_system_commands_before_clock_advances():
    world = World(dt=0.5)
    seen = []

    @world.system(stage="act")
    def create(w):
        w.commands.spawn(Position(2, 3), name="created")

    @world.system(stage="act", order=1)
    def attach(w):
        entity = w.entity("created")
        seen.append((w.tick, w.time, w.get(entity, Position)))
        w.commands.add(entity, Appearance(size=3))

    @world.system(stage="late")
    def observe(w):
        assert w.has(w.entity("created"), Appearance)
        assert w.tick == 0 and w.time == 0

    world.step()
    assert seen == [(0, 0.0, Position(2, 3))]
    assert world.tick == 1 and world.time == 0.5
    assert world.commands.apply() == 0


def test_world_without_user_systems_flushes_pending_commands_and_step_advances_clock():
    world = World(dt=0.5)
    entity = world.commands.spawn(Position())
    world.step(dt=0.25)
    assert world.get(entity, Position) == Position()
    assert (world.tick, world.time, world.dt) == (1, 0.25, 0.5)
    world.step()
    assert (world.tick, world.time, world.dt) == (2, 0.75, 0.5)


def test_dt_override_is_used_by_systems_and_callbacks_are_after_complete_steps():
    world = World(dt=0.5)
    seen, callbacks = [], []

    @world.system()
    def observe(w):
        seen.append((w.tick, w.time, w.dt))

    def stop(w):
        callbacks.append((w.tick, w.time, w.dt))
        return w.tick < 2

    assert world.run(5, dt=0.25, callback=stop) is world
    assert seen == [(0, 0.0, 0.25), (1, 0.25, 0.25)]
    assert callbacks == [(1, 0.25, 0.5), (2, 0.5, 0.5)]
    assert world.settings.dt == world.dt == 0.5
    assert world.run(0, callback=stop) is world
    assert len(callbacks) == 2


def test_zero_dt_is_an_override_and_only_false_stops_run():
    world = World(dt=0.5)
    callbacks = []

    def keep_running(w):
        callbacks.append(w.tick)
        return 0

    world.run(3, dt=0, callback=keep_running)
    assert callbacks == [1, 2, 3]
    assert (world.tick, world.time, world.dt) == (3, 0.0, 0.5)


@pytest.mark.parametrize("failure", ["system", "command"])
def test_failed_step_restores_dt_without_advancing_clock_or_rolling_back(failure):
    world = World(dt=0.5)
    error = RuntimeError("system failed")

    @world.system()
    def fail(w):
        w.resources["side_effect"] = w.dt
        if failure == "system":
            raise error
        w.commands.strict = True
        w.commands.despawn(0)

    with pytest.raises(RuntimeError if failure == "system" else StaleEntityError) as caught:
        world.step(dt=0.25)
    if failure == "system":
        assert caught.value is error
    assert (world.tick, world.time, world.dt) == (0, 0.0, 0.5)
    assert world.resources["side_effect"] == 0.25


def test_callback_exception_propagates_after_successful_step():
    world = World(dt=0.5)

    def fail(w):
        raise ValueError("callback failed")

    with pytest.raises(ValueError, match="callback failed"):
        world.run(3, dt=0.25, callback=fail)
    assert (world.tick, world.time, world.dt) == (1, 0.25, 0.5)


def test_scheduler_direct_execution_flushes_commands_without_advancing_clock():
    world = World()
    world.add_system(lambda w: w.commands.spawn(Position()), name="spawn")
    world.add_system(lambda w: w.resources.update(found=w.count(Position)), name="observe")
    world.scheduler.run_step()
    assert world.resources["found"] == 1
    assert (world.tick, world.time) == (0, 0)


def test_profiling_includes_commands_and_records_time_on_command_failure(monkeypatch):
    world = World()
    elapsed = [0.0]
    monkeypatch.setattr("simworld.systems.perf_counter", lambda: elapsed[0])
    world.scheduler.profile = True

    def slow_command(w):
        elapsed[0] += 4

    command = slow_command

    def update(w):
        elapsed[0] += 2
        w.commands.defer(command)

    world.add_system(update)
    world.step()
    assert world.scheduler.timings == {"spatial_sync": 0, "update": 6, "spatial_sync_late": 0}

    def fail(w):
        elapsed[0] += 3
        raise ValueError("apply failed")

    command = fail
    with pytest.raises(ValueError, match="apply failed"):
        world.step()
    assert world.scheduler.timings == {"spatial_sync": 0, "update": 11, "spatial_sync_late": 0}
    assert (world.tick, world.time) == (1, 1)
