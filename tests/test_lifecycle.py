from __future__ import annotations

import pytest

from sim_sandbox.entity import Entity
from sim_sandbox.terrain import TerrainMap
from sim_sandbox.world import World


class RecordingEntity(Entity):
    def __init__(self, name: str, events: list[str], x: float = 10, y: float = 10) -> None:
        super().__init__(x, y, radius=1)
        self.name = name
        self.events = events

    def init(self, world: World) -> None:
        self.events.append(f"init:{self.name}")

    def update(self, world: World, dt: float) -> None:
        self.events.append(f"update:{self.name}")

    def delete(self, world: World) -> None:
        self.events.append(f"delete:{self.name}")


def small_world(seed: int = 1) -> World:
    return World(seed, TerrainMap(seed, width=12, height=12, tile_size=8))


def test_lifecycle_runs_once_and_id_is_immutable() -> None:
    events: list[str] = []
    world = small_world()
    entity = RecordingEntity("one", events)

    assert world.spawn(entity) == 1
    assert entity.entity_id == 1
    assert events == []
    world.flush()
    world.step(1 / 60)
    assert events == ["init:one", "update:one"]

    assert world.remove(entity.entity_id)
    world.flush()
    world.flush()
    assert events == ["init:one", "update:one", "delete:one"]
    assert not world.remove(entity.entity_id)
    with pytest.raises(RuntimeError):
        world.spawn(entity)


def test_spawn_during_update_activates_after_current_tick() -> None:
    events: list[str] = []

    class Parent(RecordingEntity):
        def update(self, world: World, dt: float) -> None:
            super().update(world, dt)
            if world.tick_index == 0:
                world.spawn(RecordingEntity("child", events))

    world = small_world()
    world.spawn(Parent("parent", events))
    world.step(1 / 60)
    assert events == ["init:parent", "update:parent", "init:child"]
    world.step(1 / 60)
    assert events[-2:] == ["update:parent", "update:child"]


def test_removal_during_update_skips_later_entity() -> None:
    events: list[str] = []
    world = small_world()

    class Killer(RecordingEntity):
        victim_id: int

        def update(self, world: World, dt: float) -> None:
            super().update(world, dt)
            world.remove(self.victim_id)

    killer = Killer("killer", events)
    world.spawn(killer)
    victim = RecordingEntity("victim", events)
    killer.victim_id = world.spawn(victim)
    world.step(1 / 60)
    assert "update:victim" not in events
    assert events[-1] == "delete:victim"
    assert world.entity_count == 1


def test_cancelled_spawn_never_runs_lifecycle() -> None:
    events: list[str] = []
    world = small_world()
    entity = RecordingEntity("cancelled", events)
    entity_id = world.spawn(entity)
    world.remove(entity_id)
    world.flush()
    assert events == []
    assert world.entity_count == 0


def test_close_deletes_active_entities_once_and_clears_state() -> None:
    events: list[str] = []
    world = small_world()
    world.spawn(RecordingEntity("one", events))
    pending = RecordingEntity("pending", events)
    world.flush()
    world.spawn(pending)

    world.close()
    world.close()

    assert events == ["init:one", "delete:one"]
    assert world.is_closed
    assert world.entity_count == 0
    assert len(world.spatial) == 0
    with pytest.raises(RuntimeError, match="closed"):
        world.spawn(RecordingEntity("late", events))

