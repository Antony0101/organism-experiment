"""Fault-isolated entity preview worker and main-process controller."""

from __future__ import annotations

import multiprocessing
import time
import traceback
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from ...engine.world import World
from ...game.entity_projects.model import (
    DEFAULT_BEHAVIOR_SOURCE as ENTITY_BEHAVIOR_SOURCE,
    AppearanceDefinition,
    EntityProjectDefinition,
)
from ...game.entity_projects.runtime import (
    EditableEntity,
    EntityScriptRuntimeError,
    compile_behavior,
)
from ...game.entity_projects.registry import EntityProjectRegistry
from ...game.behavior_projects.registry import BehaviorProjectRegistry
from ...game.behavior_projects.model import BehaviorDefinition
from ...game.behavior_projects.registry import BehaviorProject
from ...game.behavior_projects.runtime import BehaviorRuntimeError
from ...game.terrain import TerrainMap

FIXED_DT = 1.0 / 60.0
SNAPSHOT_INTERVAL = 1.0 / 30.0
HEARTBEAT_INTERVAL = 0.1
PREVIEW_MAP_TILES = 32


def _send(connection: Connection, message: dict[str, object]) -> bool:
    try:
        connection.send(message)
        return True
    except (BrokenPipeError, EOFError, OSError):
        return False


def _error_message(exc: BaseException) -> dict[str, object]:
    reported = exc.cause if isinstance(exc, EntityScriptRuntimeError) else exc
    result: dict[str, object] = {
        "type": "error",
        "error_type": type(reported).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    if isinstance(exc, BehaviorRuntimeError):
        result.update(
            {
                "behavior_id": exc.behavior_id,
                "attachment_id": exc.attachment_id,
                "callback": exc.callback,
                "entity_id": exc.entity_id,
            }
        )
    elif isinstance(exc, EntityScriptRuntimeError):
        result.update(
            {"callback": exc.callback, "entity_id": exc.entity_id}
        )
    return result


def _build_world(
    definition: EntityProjectDefinition,
    behavior_source: str,
    project_directory: Path,
    seed: int,
    instances: int,
    behavior_drafts: tuple[dict[str, str], ...] = (),
    fixtures: tuple[dict[str, object], ...] = (),
) -> World:
    callbacks = compile_behavior(
        behavior_source, str(project_directory / "behavior.py")
    )
    terrain = TerrainMap(
        seed, width=PREVIEW_MAP_TILES, height=PREVIEW_MAP_TILES, tile_size=16
    )
    world = World(seed, terrain)
    overrides = tuple(
        BehaviorProject(
            BehaviorDefinition.from_json(item["manifest"]),
            item["source"],
            Path(item["directory"]) if item.get("directory") else None,
            False,
        )
        for item in behavior_drafts
    )
    behavior_registry = BehaviorProjectRegistry(
        project_directory.parent.parent / "behaviors", overrides=overrides
    )
    entity_registry = EntityProjectRegistry(
        project_directory.parent, behavior_registry
    )

    def create_project(project_id: str, x: float, y: float) -> EditableEntity:
        if project_id == definition.id:
            return EditableEntity(
                definition,
                callbacks,
                project_directory,
                x,
                y,
                behavior_registry.instantiate_entity_behaviors(definition),
            )
        return entity_registry.create(project_id, x, y)

    world.configure_entity_factory(create_project)
    for _ in range(instances):
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(create_project(definition.id, x, y))
    fixture_callbacks = compile_behavior(ENTITY_BEHAVIOR_SOURCE, "<preview-fixture>")
    for index, fixture in enumerate(fixtures):
        count = int(fixture.get("count", 0))
        if not 0 <= count <= 50:
            raise ValueError("each preview fixture row must contain 0..50 instances")
        project_id = str(fixture.get("project_id", ""))
        tags = tuple(str(tag) for tag in fixture.get("tags", ()))
        marker_definition = EntityProjectDefinition(
            id=f"preview_fixture_{index}",
            name=f"Fixture {index + 1}",
            collision_radius=5.0,
            tags=tags,
            appearance=AppearanceDefinition(
                kind="circle",
                size=(10.0, 10.0),
                fill_color=(245, 154, 75, 255),
                outline_color=(255, 232, 196, 255),
                outline_width=1,
            ),
        )
        for _ in range(count):
            x, y = terrain.random_passable_position(world.rng)
            if project_id:
                entity = entity_registry.create(project_id, x, y)
            else:
                entity = EditableEntity(
                    marker_definition, fixture_callbacks, project_directory, x, y
                )
            world.spawn(entity)
    world.flush()
    return world


def _snapshot(world: World, paused: bool, speed: float, update_ms: float) -> dict[str, object]:
    entities: list[dict[str, object]] = []
    for entity in world:
        if not isinstance(entity, EditableEntity):
            raise TypeError(
                "preview behavior spawned an unsupported entity type; only the selected editable entity is allowed"
            )
        entities.append(entity.snapshot())
    return {
        "type": "snapshot",
        "seed": world.seed,
        "tick": world.tick_index,
        "paused": paused,
        "speed": speed,
        "update_ms": update_ms,
        "entities": entities,
    }


def preview_worker_main(connection: Connection) -> None:
    """Worker entry point. It must stay at module scope for Windows spawn."""
    world: World | None = None
    definition: EntityProjectDefinition | None = None
    behavior_source = ""
    behavior_drafts: tuple[dict[str, str], ...] = ()
    fixtures: tuple[dict[str, object], ...] = ()
    project_directory = Path.cwd()
    seed = 1
    instances = 1
    paused = False
    speed = 1.0
    pending_steps = 0
    accumulator = 0.0
    update_ms = 0.0
    last_time = time.perf_counter()
    last_snapshot = 0.0
    last_heartbeat = 0.0
    running = True

    def replace_world() -> None:
        nonlocal world, accumulator, pending_steps, update_ms
        if world is not None:
            world.close()
            world = None
        assert definition is not None
        world = _build_world(
            definition,
            behavior_source,
            project_directory,
            seed,
            instances,
            behavior_drafts,
            fixtures,
        )
        accumulator = 0.0
        pending_steps = 0
        update_ms = 0.0

    _send(connection, {"type": "ready"})
    while running:
        now = time.perf_counter()
        real_dt = min(0.25, max(0.0, now - last_time))
        last_time = now
        try:
            while connection.poll():
                message = connection.recv()
                command = message.get("command")
                if command == "shutdown":
                    running = False
                    break
                if command == "load":
                    project_directory = Path(str(message["project_directory"]))
                    definition = EntityProjectDefinition.from_json(
                        str(message["manifest"]), project_directory
                    )
                    behavior_source = str(message["behavior"])
                    behavior_drafts = tuple(message.get("behavior_drafts", ()))
                    fixtures = tuple(message.get("fixtures", ()))
                    seed = int(message.get("seed", definition.preview.seed))
                    instances = int(message.get("instances", definition.preview.instances))
                    paused = False
                    speed = 1.0
                    replace_world()
                    _send(connection, {"type": "loaded"})
                elif command == "reset" and definition is not None:
                    seed = int(message.get("seed", seed))
                    instances = int(message.get("instances", instances))
                    replace_world()
                elif command == "pause":
                    paused = bool(message.get("paused", not paused))
                    accumulator = 0.0
                elif command == "step":
                    paused = True
                    pending_steps += 1
                elif command == "speed":
                    requested = float(message["speed"])
                    if requested not in (0.25, 1.0, 2.0, 4.0):
                        raise ValueError("preview speed must be 0.25, 1, 2, or 4")
                    speed = requested

            if not running:
                break
            if world is not None:
                steps = 0
                if paused:
                    steps = min(pending_steps, 16)
                    pending_steps -= steps
                else:
                    accumulator += real_dt * speed
                    steps = min(int(accumulator / FIXED_DT), 16)
                    accumulator -= steps * FIXED_DT
                if steps:
                    started = time.perf_counter()
                    for _ in range(steps):
                        world.step(FIXED_DT)
                    measured = (time.perf_counter() - started) * 1000.0
                    update_ms = measured if update_ms == 0.0 else update_ms * 0.9 + measured * 0.1
                if now - last_snapshot >= SNAPSHOT_INTERVAL:
                    if not _send(connection, _snapshot(world, paused, speed, update_ms)):
                        break
                    last_snapshot = now
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                if not _send(connection, {"type": "heartbeat", "time": now}):
                    break
                last_heartbeat = now
        except BaseException as exc:
            paused = True
            if not _send(connection, _error_message(exc)):
                break
        time.sleep(0.002)

    if world is not None:
        try:
            world.close()
        except BaseException:
            pass
    connection.close()


@dataclass(slots=True)
class PreviewStatus:
    running: bool = False
    loaded: bool = False
    timed_out: bool = False
    error: dict[str, object] | None = None
    snapshot: dict[str, object] | None = None


class PreviewController:
    """Own a preview process and convert its messages into UI-friendly state."""

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.status = PreviewStatus()
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._last_contact = 0.0

    @property
    def process(self) -> multiprocessing.Process | None:
        return self._process

    def start(self) -> None:
        self.stop()
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=preview_worker_main,
            args=(child,),
            name="entity-preview",
            daemon=True,
        )
        process.start()
        child.close()
        self._process = process
        self._connection = parent
        self._last_contact = time.monotonic()
        self.status = PreviewStatus(running=True)

    def _send(self, message: dict[str, object]) -> None:
        if self._process is None or not self._process.is_alive() or self._connection is None:
            self.start()
        assert self._connection is not None
        self._connection.send(message)

    def apply(
        self,
        definition: EntityProjectDefinition,
        behavior_source: str,
        project_directory: Path,
        *,
        seed: int | None = None,
        instances: int | None = None,
        behavior_drafts: tuple[dict[str, str], ...] = (),
        fixtures: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.status.error = None
        self.status.timed_out = False
        self.status.loaded = False
        self._send(
            {
                "command": "load",
                "manifest": definition.to_json(),
                "behavior": behavior_source,
                "project_directory": str(project_directory.resolve()),
                "seed": definition.preview.seed if seed is None else seed,
                "instances": definition.preview.instances if instances is None else instances,
                "behavior_drafts": behavior_drafts,
                "fixtures": fixtures,
            }
        )

    def reset(self, seed: int, instances: int) -> None:
        self._send({"command": "reset", "seed": seed, "instances": instances})

    def pause(self, paused: bool) -> None:
        self._send({"command": "pause", "paused": paused})

    def step(self) -> None:
        self._send({"command": "step"})

    def set_speed(self, speed: float) -> None:
        self._send({"command": "speed", "speed": speed})

    def poll(self) -> PreviewStatus:
        now = time.monotonic()
        connection = self._connection
        if connection is not None:
            try:
                while connection.poll():
                    message = connection.recv()
                    self._last_contact = now
                    message_type = message.get("type")
                    if message_type == "ready":
                        self.status.running = True
                    elif message_type == "loaded":
                        self.status.loaded = True
                    elif message_type == "snapshot":
                        self.status.snapshot = message
                    elif message_type == "error":
                        self.status.error = message
            except (EOFError, BrokenPipeError, OSError):
                self.status.running = False
        process = self._process
        if process is not None and not process.is_alive():
            self.status.running = False
            if self.status.error is None and process.exitcode not in (0, None):
                self.status.error = {
                    "type": "error",
                    "error_type": "PreviewProcessError",
                    "message": f"preview process exited with code {process.exitcode}",
                    "traceback": "",
                }
        elif process is not None and now - self._last_contact > self.timeout_seconds:
            process.terminate()
            process.join(timeout=0.5)
            self.status.running = False
            self.status.timed_out = True
            self.status.error = {
                "type": "error",
                "error_type": "PreviewTimeout",
                "message": "preview stopped because entity code did not respond within two seconds",
                "traceback": "",
            }
        return self.status

    def stop(self) -> None:
        process = self._process
        connection = self._connection
        if process is not None and process.is_alive():
            if connection is not None:
                try:
                    connection.send({"command": "shutdown"})
                except (BrokenPipeError, EOFError, OSError):
                    pass
            process.join(timeout=0.5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.5)
        if connection is not None:
            connection.close()
        self._process = None
        self._connection = None
        self.status = PreviewStatus()

    def __enter__(self) -> PreviewController:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


__all__ = [
    "PREVIEW_MAP_TILES",
    "PreviewController",
    "PreviewStatus",
    "preview_worker_main",
]
