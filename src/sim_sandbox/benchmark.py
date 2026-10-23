"""Headless simulation and rendering benchmark for discovered worlds."""

from __future__ import annotations

import argparse
import os
import statistics
import time
from collections.abc import Sequence
from pathlib import Path

from .game.world_definition import MAX_ENTITY_COUNT, MAX_SEED, WorldLaunchOptions
from .game.worlds.discovery import discover_worlds


def _create_behavior_stack_session(seed: int, entity_count: int):
    """Construct the lightweight component benchmark without editor files."""
    from .engine.world import World
    from .game.behavior_projects import BehaviorAttachment, BehaviorProjectRegistry
    from .game.entity_projects.model import (
        DEFAULT_BEHAVIOR_SOURCE,
        AppearanceDefinition,
        EntityProjectDefinition,
    )
    from .game.entity_projects.runtime import EditableEntity, compile_behavior
    from .game.terrain import TerrainMap
    from .game.world_definition import WorldSession

    terrain = TerrainMap(seed, width=256, height=256, tile_size=16)
    world = World(seed, terrain)
    behaviors = BehaviorProjectRegistry(Path("content/behaviors"))
    definition = EntityProjectDefinition(
        "benchmark_dot",
        "Benchmark Dot",
        behaviors=(
            BehaviorAttachment("velocity", "constant_velocity"),
            BehaviorAttachment("bounds", "keep_in_bounds"),
            BehaviorAttachment("spin", "spin"),
        ),
        appearance=AppearanceDefinition(kind="circle", size=(6.0, 6.0)),
    )
    callbacks = compile_behavior(DEFAULT_BEHAVIOR_SOURCE, "<benchmark-entity>")
    for _ in range(entity_count):
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(
            EditableEntity(
                definition,
                callbacks,
                Path("content/entities/benchmark_dot"),
                x,
                y,
                behaviors.instantiate_entity_behaviors(definition),
            )
        )
    world.flush()
    return WorldSession(
        world,
        (terrain.pixel_width / 2, terrain.pixel_height / 2),
        1.0,
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * percentile))]


def run_benchmark(
    seed: int,
    entity_count: int,
    ticks: int,
    render_frames: int,
    world_id: str = "wandering_plains",
    behavior_stack: bool = False,
) -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    from .engine.camera import Camera2D
    from .presentation.rendering import WorldRenderer

    definition = None if behavior_stack else discover_worlds().require(world_id)
    options = WorldLaunchOptions(seed, entity_count)
    pygame.init()
    surface = pygame.display.set_mode((1280, 720))
    setup_start = time.perf_counter()
    session = (
        _create_behavior_stack_session(seed, entity_count)
        if behavior_stack
        else definition.create(options)  # type: ignore[union-attr]
    )
    world = session.world
    camera = Camera2D(
        session.camera_position[0],
        session.camera_position[1],
        zoom=session.camera_zoom,
        world_width=world.terrain.pixel_width,
        world_height=world.terrain.pixel_height,
    )
    renderer = WorldRenderer(world)
    setup_seconds = time.perf_counter() - setup_start

    update_timings: list[float] = []
    for _ in range(ticks):
        started = time.perf_counter()
        world.step(1.0 / 60.0)
        update_timings.append((time.perf_counter() - started) * 1000.0)

    render_timings: list[float] = []
    visible_count = 0
    for _ in range(render_frames):
        started = time.perf_counter()
        visible_count = renderer.draw(surface, world, camera, 1.0)
        pygame.display.flip()
        render_timings.append((time.perf_counter() - started) * 1000.0)

    final_count = world.entity_count
    final_state = world.state_digest()
    session.close()
    pygame.quit()

    print(f"world: {'behavior_stack' if behavior_stack else world_id}")
    print(f"seed: {seed}")
    print(f"entities: {final_count:,} ({visible_count:,} visible)")
    print(f"setup: {setup_seconds:.3f} s")
    if update_timings:
        average = statistics.mean(update_timings)
        print(
            f"update: {average:.3f} ms average, "
            f"{_percentile(update_timings, 0.95):.3f} ms p95, "
            f"{1000.0 / average:.1f} ticks/s"
        )
    if render_timings:
        print(
            f"render: {statistics.mean(render_timings):.3f} ms average, "
            f"{_percentile(render_timings, 0.95):.3f} ms p95"
        )
    print(f"state: {final_state}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the 2D simulation sandbox")
    parser.add_argument("--world", default="wandering_plains", help="discovered world ID")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--entities", type=int)
    parser.add_argument("--ticks", type=int, default=300)
    parser.add_argument("--render-frames", type=int, default=120)
    parser.add_argument(
        "--behavior-stack",
        action="store_true",
        help="benchmark a lightweight three-component editable entity stack",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    catalog = discover_worlds()
    definition = catalog.get(args.world)
    if definition is None and not args.behavior_stack:
        available = ", ".join(item.id for item in catalog.definitions) or "none"
        parser.error(f"unknown world {args.world!r}; choose from: {available}")
    seed = (1 if args.behavior_stack else definition.default_seed) if args.seed is None else args.seed
    if args.entities is None:
        entity_count = (
            10_000
            if args.behavior_stack or definition.id == "wandering_plains"
            else definition.default_entity_count
        )
    else:
        entity_count = args.entities
    if not 0 <= seed <= MAX_SEED:
        parser.error(f"--seed must be between 0 and {MAX_SEED}")
    if not 0 <= entity_count <= MAX_ENTITY_COUNT:
        parser.error(f"--entities must be between 0 and {MAX_ENTITY_COUNT}")
    if min(args.ticks, args.render_frames) < 0:
        parser.error("--ticks and --render-frames cannot be negative")
    run_benchmark(
        seed,
        entity_count,
        args.ticks,
        args.render_frames,
        "behavior_stack" if args.behavior_stack else definition.id,
        args.behavior_stack,
    )


if __name__ == "__main__":
    main()
