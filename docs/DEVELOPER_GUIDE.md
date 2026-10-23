# Extending the Simulation Sandbox

The project is split into three layers: reusable simulation mechanics, game
content, and Pygame presentation. Hand-written engine entities live under
`game/entities`; editor content lives under `content/entities` and
`content/behaviors`; selectable scenarios are packages under `game/worlds`.
The Project Hub connects these workflows while world packages remain
automatically discovered.

## Directory structure

```text
src/sim_sandbox/
├── engine/
│   ├── entity.py       # Entity lifecycle contract
│   ├── world.py        # Ownership, ticking, lifecycle queues
│   ├── spatial.py      # Radius and rectangle queries
│   ├── clock.py        # Fixed-step timing and speed controls
│   └── camera.py       # Bounded pan/zoom camera
├── game/
│   ├── entities/
│   │   └── wandering_agent.py
│   ├── entity_projects/ # Editor schema, persistence, registry, runtime
│   ├── behavior_projects/ # Component schemas, registry, runtime, 24 presets
│   ├── project_types.py # Shared typed-property validation
│   ├── quick_sandbox.py
│   ├── terrain.py
│   ├── world_definition.py
│   └── worlds/
│       ├── discovery.py
│       ├── wandering_plains/
│       │   ├── __init__.py
│       │   └── definition.py
│       └── empty_sandbox/
│           ├── __init__.py
│           └── definition.py
├── presentation/
│   ├── app.py
│   ├── rendering.py
│   └── screens/
│       ├── project_hub.py
│       ├── world_selection.py
│       ├── quick_sandbox.py
│       ├── gameplay.py
│       ├── entity_editor.py
│       ├── behavior_editor.py
│       └── pause_menu.py
├── app.py              # Compatibility re-export and console entry point
├── benchmark.py
└── __main__.py
```

Engine modules do not import Pygame except indirectly when an entity chooses to
implement Pygame drawing. Input, windows, menus, terrain rendering, the HUD, and
the inspector remain in `presentation`.

Old paths such as `sim_sandbox.entity`, `sim_sandbox.world`,
`sim_sandbox.agents`, and `sim_sandbox.rendering` are thin compatibility
imports. New content should use the layered paths shown above.

## Entity lifecycle

Every simulated object subclasses `Entity`. Its lifecycle is:

1. `world.spawn(entity)` reserves an immutable numeric ID and queues activation.
2. At a tick boundary, `init(world)` runs exactly once.
3. Each fixed tick calls `update(world, dt)` once.
4. Visible entities may receive `draw(surface, camera, alpha)` every render frame.
5. `world.remove(entity_id)` queues removal; `delete(world)` runs once at a boundary.
6. `world.close()` calls `delete` once for every remaining active entity, then clears lifecycle queues and the spatial index.

Spawning and removal are deferred when requested during an update. That keeps
iteration order stable and prevents a behavior from mutating the active entity
collection halfway through a tick.

Inherited fields are:

| Field | Meaning |
| --- | --- |
| `entity_id` | Read-only ID assigned by `World.spawn` |
| `x`, `y` | Current position in continuous world pixels |
| `previous_x`, `previous_y` | Position at the start of the tick, maintained by `World` |
| `radius` | Entity size used by drawing or behavior |

## Add an entity

For the smallest working example, copy
`src/sim_sandbox/game/entities/simple_entity.py` and rename `SimpleEntity`.
It already demonstrates every lifecycle hook, interpolated drawing,
deterministic state hashing, and inspector fields.

Create `src/sim_sandbox/game/entities/energy_orb.py`:

```python
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from ...engine.entity import Entity

if TYPE_CHECKING:
    from ...engine.camera import Camera2D
    from ...engine.world import World


class EnergyOrb(Entity):
    __slots__ = ("velocity_x", "velocity_y", "lifetime", "color")

    def __init__(self, x: float, y: float, lifetime: float = 10.0) -> None:
        super().__init__(x, y, radius=5.0)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.lifetime = lifetime
        self.color = (255, 220, 70)

    def init(self, world: World) -> None:
        # Use the world's seeded RNG for deterministic behavior.
        angle = world.rng.random() * math.tau
        speed = world.rng.uniform(15.0, 30.0)
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed

    def update(self, world: World, dt: float) -> None:
        next_x = self.x + self.velocity_x * dt
        next_y = self.y + self.velocity_y * dt

        if world.terrain.is_passable(next_x, self.y):
            self.x = next_x
        else:
            self.velocity_x *= -1.0

        if world.terrain.is_passable(self.x, next_y):
            self.y = next_y
        else:
            self.velocity_y *= -1.0

        self.lifetime -= dt
        if self.lifetime <= 0.0:
            world.remove(self.entity_id)

    def draw(self, surface: Any, camera: Camera2D, alpha: float) -> None:
        import pygame

        render_x = self.previous_x + (self.x - self.previous_x) * alpha
        render_y = self.previous_y + (self.y - self.previous_y) * alpha
        screen_x, screen_y = camera.world_to_screen(render_x, render_y)
        screen_radius = max(1, round(self.radius * camera.zoom))
        pygame.draw.circle(
            surface,
            self.color,
            (round(screen_x), round(screen_y)),
            screen_radius,
        )

    def delete(self, world: World) -> None:
        # Release entity-owned resources here. Simple entities need no cleanup.
        pass

    def state_values(self) -> tuple[object, ...]:
        return super().state_values() + (
            self.velocity_x,
            self.velocity_y,
            self.lifetime,
            self.color,
        )

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        return super().inspection_fields() + (
            ("Lifetime", f"{self.lifetime:.2f} s"),
            ("Velocity", f"{self.velocity_x:.2f}, {self.velocity_y:.2f}"),
        )
```

Export it from `game/entities/__init__.py` if world definitions should import it
as `from ...entities import EnergyOrb`.

`__slots__` is optional. It declares the per-instance attributes stored by this
subclass and avoids a normal instance `__dict__`, which can save memory for
large populations. Include only fields introduced by the subclass; inherited
entity fields already have slots in `Entity`.

`state_values()` should include every field that influences later behavior so
`World.state_digest()` can detect determinism regressions. The inspector uses
`inspection_fields()` and needs no central registration.

## Spawn, remove, and query entities

The world owns all entities:

```python
orb = EnergyOrb(100.0, 150.0)
orb_id = world.spawn(orb)

# Outside lifecycle hooks, flush if it must activate immediately.
world.flush()

same_orb = world.get(orb_id)
nearby = world.query_radius(100.0, 150.0, radius=80.0)
visible = world.query_rect(left, top, right, bottom)

world.remove(orb_id)
world.flush()
```

Do not call `flush()` from `init`, `update`, or `delete`. Queue the lifecycle
request and let the world apply it at the boundary. Spatial membership is
synchronized after movement on every completed tick.

## Entity Creation Studio

Open the integrated editor from the Project Hub or directly:

```powershell
simulation-sandbox --entity-editor
```

The editor has four tabs:

- **Design** configures metadata, tags, collision radius, declared properties, and appearance.
- **Behaviors** attaches, orders, enables, and configures reusable components.
- **Code** edits lifecycle callbacks with highlighting, line diagnostics, find, clipboard, indentation, and undo/redo.
- **Preview** runs up to 100 instances in a deterministic 32×32-tile test world.

`Ctrl+S` validates, saves, and applies. `F5` validates and applies the in-memory
draft without saving. Appearance edits are reflected in the Design preview
immediately. Restarting preview is required after code or property-schema
changes.

The library supports search, creation, duplication, and recoverable archival.
Archived projects are moved into `content/entities/.trash`; they are not
permanently deleted.

### Editable project files

Each project is inspectable and version-control friendly:

```text
content/entities/glowing_orb/
├── entity.json
├── behavior.py
└── assets/
    └── orb.png
```

`entity.json` uses schema version 2. It stores the immutable ID, display name,
description, collision radius, declared properties, tags, ordered behavior
attachments, appearance, and preview defaults. Schema-1 projects load as
entities with no tags or attachments and migrate on their next save. Supported
property types are `float`, `int`, `bool`, `str`, `color`, and `vec2`.

Appearance supports circles, rectangles, or a static PNG sprite. It includes
size, fill/tint, outline, rotation, scale, and visibility. Imported sprites are
copied into the project and referenced with a project-relative path. Sprite
sheets and animation states are not part of version one.

`behavior.py` contains optional module-level callbacks:

```python
def init(entity, world):
    entity.state["energy"] = 100.0


def update(entity, world, dt):
    speed = entity.state["speed"]
    next_x = entity.x + speed * dt
    if world.terrain.is_passable(next_x, entity.y):
        entity.x = next_x

    entity.visual.rotation_degrees += 90.0 * dt
    if entity.state["energy"] <= 0:
        world.remove(entity.entity_id)


def delete(entity, world):
    pass
```

The runtime object is a normal `Entity`. Custom values must remain in
`entity.state` and must match their declared types. The visual state exposes:

```python
entity.visual.visible
entity.visual.color              # RGBA tuple
entity.visual.rotation_degrees
entity.visual.scale_x
entity.visual.scale_y
```

Changing state keys or assigning an incompatible type pauses preview with a
diagnostic. Declared values and mutable visual state are included in
`state_values()` for deterministic hashes and visible declared properties are
added to the inspector.

### Use projects in a world

Loading behavior in normal gameplay is explicit because it executes trusted
Python in the game process:

```python
from pathlib import Path

from sim_sandbox.game.entity_projects import EntityProjectRegistry


registry = EntityProjectRegistry(Path("content/entities"))
registry.configure_world(world)

for _ in range(options.entity_count):
    x, y = terrain.random_passable_position(world.rng)
    world.spawn_project("glowing_orb", x, y)

world.flush()
```

Call `registry.refresh()` after files change. Existing live instances retain
the callbacks and definition with which they were created; restart the world to
pick up saved changes.

## Behavior components and Behavior Studio

Open the component authoring tool with:

```powershell
simulation-sandbox --behavior-editor
simulation-sandbox --list-behaviors
```

Packaged presets are read-only. Duplicating one creates a normal project:

```text
content/behaviors/seek_food/
├── behavior.json
└── behavior.py
```

The manifest declares `id`, `name`, `description`, `category`, typed
`parameters`, typed private `state`, `required_properties`,
`required_behaviors`, `writes`, `allow_multiple`, and an optional
`exclusive_group`. Custom IDs cannot shadow built-ins. Archive moves projects
to `.trash` and is rejected while an entity manifest references them.

Component code receives an attachment-local runtime object:

```python
def init(behavior, entity, world):
    behavior.state["timer"] = 0.0


def update(behavior, entity, world, dt):
    behavior.state["timer"] += dt
    entity.x += behavior.config["speed"] * dt


def delete(behavior, entity, world):
    pass
```

`behavior.config` is a validated read-only mapping. `behavior.state` is mutable,
typed, namespaced per attachment, and included in hashes/snapshots. Attachment
IDs are unique inside one entity. Enabled attachment `init` and `update`
callbacks run top to bottom, then the entity's custom callbacks run. Cleanup
runs custom `delete` first and attachments bottom to top.

The registry API is also available directly:

```python
from sim_sandbox.game.behavior_projects import BehaviorProjectRegistry

behaviors = BehaviorProjectRegistry("content/behaviors")
project = behaviors.require("wander")
instance = behaviors.instantiate(attachment)
```

Entity validation rejects missing projects, invalid parameters, missing
property/behavior requirements, duplicate non-multiple components, and
exclusive-group conflicts. Multiple position writers are legal but reported
as a warning because stack order changes the result.

Behavior Preview can generate a host with required properties or use a saved
entity. Fixture rows add saved entities or tagged markers for target/sensor and
organism interactions. Draft behavior bundles execute in the spawned preview
worker without being saved first.

### Built-in pack

The 24 built-ins are:

- Movement/terrain: Constant Velocity, Wander, Seek Nearest, Flee Nearest,
  Orbit Nearest, Keep In Bounds, Avoid Blocked Terrain, Terrain Speed Modifier.
- State/lifecycle: Maximum Lifetime, Age Counter, Health, Energy Metabolism,
  Hunger, Regeneration, Growth Over Time.
- Interaction/organism: Nearest Tag Sensor, Contact Damage, Eat Nearby,
  Reproduce, Periodic Spawner.
- Visual: Spin, Pulse Scale, Face Velocity, Property Color Map.

Targeting parameters support required tags and an optional entity project ID.
`World.query_radius()` and `World.nearest_entity()` accept those filters, and
equal-distance targets resolve by immutable entity ID. Reproduction and
spawners call `world.spawn_project()`, so a world must be configured with an
entity registry. Spawns remain deferred to tick boundaries.

## Quick Sandbox

The Project Hub's Quick Sandbox screen builds Compact (64×64), Standard
(128×128), or Large (256×256) terrain and accepts up to eight entity-project
population rows. Total population is capped at 10,000. The equivalent direct
launch is:

```powershell
simulation-sandbox --sandbox glowing_orb --terrain standard --seed 4 --entities 100
```

### Preview isolation and trust

The preview owns a real `World` in a spawned child process and sends normalized
entity snapshots to the editor. Syntax errors, imports, runtime exceptions, and
traceback line numbers are reported in the UI. A worker that stops responding
for two seconds is terminated, which recovers from most accidental infinite
loops.

This is not an operating-system security sandbox. A script can still access
the filesystem, network, and other Python APIs. Only run entity projects you
trust. Normal gameplay loads them in-process by design.

## World definition API

`game/world_definition.py` contains three immutable data classes:

| Type | Purpose |
| --- | --- |
| `WorldLaunchOptions(seed, entity_count)` | Validated input selected by the menu or CLI |
| `WorldDefinition(...)` | Discoverable metadata plus the session factory |
| `WorldSession(world, camera_position, camera_zoom)` | Live world and its initial camera view |

A definition contains `id`, `name`, `description`, `menu_order`, `default_seed`,
`default_population`, and `factory`. Calling `definition.create(options)`
invokes the factory and requires a `WorldSession` result.

Factories, rather than `World` subclasses, are usually the right place to
choose terrain size, initial entities, camera position, and scenario defaults.

## Add a selectable world

Create a package whose folder name is the world ID:

```text
src/sim_sandbox/game/worlds/orb_garden/
├── __init__.py
└── definition.py
```

Put this in `definition.py`:

```python
from ...entities.energy_orb import EnergyOrb
from ...terrain import TerrainMap
from ...world_definition import WorldDefinition, WorldLaunchOptions, WorldSession
from ....engine.world import World


def create_world(options: WorldLaunchOptions) -> WorldSession:
    terrain = TerrainMap(
        seed=options.seed,
        width=128,
        height=128,
        tile_size=16,
    )
    world = World(
        seed=options.seed,
        terrain=terrain,
        spatial_cell_size=64.0,
    )

    for _ in range(options.entity_count):
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(EnergyOrb(x, y))

    # Activate the initial population before returning the session.
    world.flush()
    return WorldSession(
        world=world,
        initial_camera_position=(terrain.pixel_width / 2, terrain.pixel_height / 2),
        initial_zoom=1.0,
    )


WORLD_DEFINITION = WorldDefinition(
    id="orb_garden",              # Must exactly match the folder name.
    name="Orb Garden",
    description="A garden of short-lived moving energy orbs.",
    menu_order=30,                # Lower values appear first in the menu.
    default_seed=1,
    default_population=250,
    factory=create_world,
)
```

That is all the application wiring required. At startup, discovery scans
immediate packages under `game/worlds`, imports each `definition.py`, and reads
`WORLD_DEFINITION`. Definitions are sorted by `(menu_order, name, id)`.

Discovery validates the ID syntax, folder/ID match, name, description, default
ranges, factory, and duplicate IDs. A broken package is reported without
hiding other valid worlds. Discovery is intentionally limited to trusted
packages in this project; external mods are not loaded.

Verify it with:

```powershell
simulation-sandbox --list-worlds
simulation-sandbox --world orb_garden --seed 42 --entities 500
```

## Application and screen flow

`presentation/app.py` owns only screen transitions and session lifetime:

```text
Project Hub --> World Selection --> Gameplay --> Pause Menu
     |              |                |          /   |   \
     |              └---- Start -----┘      Resume Restart Main Hub
     ├--> Quick Sandbox ---- Start --> Gameplay
     ├--> Entity Studio
     └--> Behavior Studio
```

- `ProjectHubScreen` is the default launcher and displays recent projects.
- `WorldSelectionScreen` handles scenario cards, numeric input, and validation.
- `QuickSandboxScreen` builds ad-hoc entity population mixes.
- `GameplayScreen` owns the camera, clock, renderer, selection, follow mode, and gameplay input.
- `PauseMenuScreen` returns Resume, Restart, Main Hub, or Quit actions.
- Entity/Behavior Studio keep dirty-change confirmation inside their screens.
- Restart preserves the current world ID, seed, and population.
- Returning to the hub, restarting, or quitting closes the active session first.

To change presentation behavior, edit the relevant screen rather than the
engine. To add scenario content, add a world package rather than branching in
the application state machine.

## Terrain API

The live world exposes its terrain as `world.terrain`. These methods accept
world-space pixels unless the name explicitly says `tile`:

```python
terrain_type = world.terrain.terrain_at(x, y)
movement_cost = world.terrain.movement_cost_at(x, y)
can_enter = world.terrain.is_passable(x, y)
tile_x, tile_y = world.terrain.world_to_tile(x, y)
spawn_x, spawn_y = world.terrain.random_passable_position(world.rng)
```

Water and rock are blocked. Grass costs `1.0`; sand and forest slow movement by
different amounts. Terrain generation is in `game/terrain.py`; Pygame colors
and cached chunk drawing are in `presentation/rendering.py`.

## Determinism rules

- Use `world.rng`, never module-level random functions.
- Apply external commands at consistent tick boundaries.
- Keep a fixed update step (`1 / 60`); never pass render-frame duration to entities.
- Do not mutate simulation state in `draw`.
- Preserve entity order and include custom behavior fields in `state_values()`.
- Use identical seeds and tick-aligned inputs when comparing `state_digest()`.

Determinism targets the same code and Python runtime; cross-version replay
compatibility is outside this version's scope.

## Test custom content

Keep tests small by constructing an explicit terrain and engine world:

```python
from sim_sandbox.engine.world import World
from sim_sandbox.game.entities.energy_orb import EnergyOrb
from sim_sandbox.game.terrain import TerrainMap


def make_world(seed: int) -> World:
    terrain = TerrainMap(seed, width=24, height=24, tile_size=8)
    return World(seed, terrain)


def test_orb_expires() -> None:
    world = make_world(10)
    x, y = world.terrain.random_passable_position(world.rng)
    entity_id = world.spawn(EnergyOrb(x, y, lifetime=0.01))

    world.step(1.0 / 60.0)

    assert world.get(entity_id) is None
    world.close()
```

Run everything with:

```powershell
python -m pytest
simulation-benchmark --behavior-stack --entities 10000 --ticks 300 --render-frames 120
```

The suite covers lifecycle boundaries, spatial queries, terrain, deterministic
sessions, discovery errors, all 24 presets, preview isolation, compatibility
imports, controls, rendering, and screen transitions. The behavior-stack
benchmark reports setup, average/p95 update and render timing, visible count,
and the final deterministic state digest.

## Common mistakes

- Forgetting `super().__init__(x, y, radius)` leaves required spatial state unset.
- Reading `entity_id` before `world.spawn(entity)` raises `RuntimeError`.
- Calling `world.flush()` during an update raises `RuntimeError`.
- Reusing one entity instance in another spawn raises `RuntimeError`.
- Using `random.random()` rather than `world.rng.random()` breaks reproducibility.
- Changing simulation state in `draw` couples behavior to render FPS.
- Letting a definition ID differ from its package folder prevents discovery.
- Forgetting `WORLD_DEFINITION` makes the package appear as a reported discovery error.
