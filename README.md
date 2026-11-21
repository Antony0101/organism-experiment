# simworld

A Python engine for experimenting with 2D simulations. Create entities, attach
components that hold their data, and write systems that update them over time.
NumPy grids represent terrain and fields such as food or heat. The engine can
render a world as text or save a PNG without opening a window.

The project is being built incrementally from [BLUEPRINT.md](BLUEPRINT.md), with
a scene editor planned for later phases.

## Project status

**Steps 001–043 of 194 are complete. The Phase 0, Phase 1 and Phase 2 gates have
passed.** The current engine supports entities, components, scheduling, deferred
commands, grids, terrain, spatial queries, seeded world generation and headless
rendering. The saved [20×20 milestone PNG](docs/artifacts/phase-2-grid.png) was
validated and visually inspected.

Queued events, actions and brains are next. Built-in simulation modules,
pathfinding, complete world persistence, plugins and the editor are still
planned. The declared `simworld-editor` entry point cannot launch yet. Worlds
currently use `modules=()`; installing simulation modules is not implemented.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Define your own components](#define-your-own-components)
- [Generate terrain and save an image](#generate-terrain-and-save-an-image)
- [Available features](#available-features)
- [Run the checks](#run-the-checks)
- [Documentation](#documentation)
- [Repository layout](#repository-layout)
- [Development workflow](#development-workflow)

## Installation

Use **Python 3.12 or newer** for the pinned development environment. From the
repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

[requirements-dev.txt](requirements-dev.txt) installs this checkout in editable
mode with its test extra. Changes under `simworld/` take effect without
reinstalling. If `.venv` already exists, use its interpreter directly; activation
is optional. Run the Python examples below with `.venv/bin/python`.

To use the dependency ranges in [pyproject.toml](pyproject.toml) instead of the
recorded pins, install with:

```bash
.venv/bin/python -m pip install -e '.[test]'
```

Package metadata declares Python 3.10+ and NumPy 1.22+. The development pins
require Python 3.12+ because they use NumPy 2.5.4. The recorded Linux x86_64
environment is:

| Tool or library | Version |
| --- | --- |
| Python | 3.12.3 |
| NumPy | 2.5.4 |
| pytest | 9.2.0 |
| pip | 24.0 |

These describe the existing environment. Fresh-environment recreation from the
pins has not yet been verified. The requirements do not lock Python itself or
isolated build dependencies. Use matching Python/NumPy versions and the same RNG
call order when comparing seeded results.

## Quick start

Create an entity and a system that moves it each step:

<!-- run -->
```python
from simworld import Position, World

world = World(width=20, height=10, seed=7, dt=0.5)
walker = world.spawn(Position(2, 3), name="walker")

@world.system(stage="act")
def move(world):
    for entity, position in world.query(Position):
        position.x += 2 * world.dt

world.run(steps=4)
position = world.get(walker, Position)
print(f"Position: ({position.x}, {position.y}); tick: {world.tick}")
assert (position.x, position.y) == (6, 3)
assert world.tick == 4 and world.time == 2.0
```

An **entity** is an integer identity. A **component**, such as Position, stores
its data. A **system** is a function that changes that data. The scheduler calls
the registered system once per step here; four half-second steps move the walker
four units to the right.

Use `world.step()` for a single step or `world.run(steps)` for several. The world
advances its clock after a successful scheduled pass. Systems use the stages
`input`, `sense`, `decide`, `act`, `update` and `late`, in that order.

## Define your own components

Use `@component` to register a data class. `prop` adds field metadata, such as a
tooltip, for reflection and future tools:

<!-- run -->
```python
from simworld import World, component, prop

@component(category="example")
class DemoEnergy:
    amount: float = prop(10.0, tooltip="Energy available to this entity.")

world = World()
entity = world.spawn(DemoEnergy())

@world.system(stage="update")
def spend_energy(world):
    for entity, energy in world.query(DemoEnergy):
        energy.amount -= 1

world.run(steps=3)
assert world.get(entity, DemoEnergy).amount == 7
```

Queries return an entity id followed by its requested components. Components can
also be found by their registered names. Use `world.commands` to queue structural
changes during a system; the scheduler applies them after each system and at
stage boundaries. See the developer guide for registration, ownership and stale
entity behavior.

## Generate terrain and save an image

This independent example paints water blobs, spreads a food field, places
entities on passable terrain and writes a **160×96** PNG named `world.png` in the
current directory:

<!-- run -->
```python
from simworld import Appearance, Position, World
from simworld.render import save_frame
from simworld.worldgen import paint_blobs, random_positions

world = World(width=20, height=12, seed=7, modules=())
world.define_terrain("ground", 1, color=(60, 110, 50), char=".")
world.define_terrain("water", 2, passable=False, color=(35, 90, 185), char="~")
world.fill_terrain("ground")
paint_blobs(world, "water", count=3, radius=(1, 3))

food = world.define_field("food", max=10, diffusion=0.2, color=(240, 210, 40))
food.set(15, 3, 10)
food.diffuse(food.diffusion_rate, mask=world.terrains.mask("ground"))
for x, y in random_positions(world, 5):
    world.spawn(Position(x, y), Appearance(color=(255, 255, 255)))

path = save_frame(world, "world.png", scale=8)
assert path.is_file()
```

World coordinates use **`(x, y)`**; raw layer arrays use **`data[y, x]`**. The
rendered origin is at the top left, with y increasing downward. Field evolution
is explicit: defining decay, diffusion or regrowth metadata does not install an
automatic update system yet. PNG output needs only stdlib and NumPy, without
Pillow, pygame or Dear PyGui.

## Available features

| Area | Implemented behavior |
| --- | --- |
| Entities and components | Generation-checked ids, spawn/despawn, component registration/reflection/serialization, access and mutation, queries/counts, names and prefab templates |
| Scheduling | System registration, ordered stages, enable/disable flags, every-N execution, profiling, World step/run loops and deferred structural commands |
| Layers | Typed scalar/vector grids, bounds and clamping, add/take, reductions, bilinear sampling, gradients, window views, neighborhoods, masked diffusion and decay |
| Terrain | Name/id definitions, painting, costs/passability, numeric property grids, masks and metadata refresh |
| Spatial queries | Bucket indexing, nearby queries with component filters/distances, lifecycle updates and scheduled Position synchronization |
| World generation | Seeded value noise, terrain bands, ellipse painting and bounded passable-position sampling |
| Rendering | RGB arrays, ASCII maps, field overlays, entity markers, scaling and PNG encoding/file output |

Import World, Position, Appearance, component, prop and system from `simworld`.
Other types and helpers currently live in their own modules, such as
`simworld.layers`, `simworld.terrain`, `simworld.worldgen` and `simworld.render`.
The developer guide records the exact current API and its limits.

## Run the checks

Run the accumulated tests and check installed dependencies:

```bash
.venv/bin/python -m pytest tests -q -o addopts=''
.venv/bin/python -m pip --no-cache-dir check
```

To check only this README's examples:

```bash
.venv/bin/python -m pytest tests/test_readme.py
```

Python blocks marked with `<!-- run -->` execute independently in temporary
directories. The `clean_components` fixture restores process-global component
registrations between examples. The complete built-in `world` fixture is planned
for Step 071.

## Documentation

| Document | Use it for |
| --- | --- |
| [Developer guide](docs/developer-guide.md) | Architecture, runnable examples, API behavior, internal data flow and implementation limits |
| [ECS contracts](docs/ecs-contracts.md) | Entity ids, component data, ordering, scheduling and later integration requirements |
| [Grid contracts](docs/grid-contracts.md) | Coordinates, field evolution, terrain edits, spatial synchronization and the reproducible PNG milestone |
| [Implementation plan](plans/README.md) | The 194-step sequence, phase gates and execution rules |
| [Progress log](plans/progress.md) | Completed work, exact verification results and deferred checks |
| [Blueprint](BLUEPRINT.md) | The intended complete engine and editor; some described features are still planned |

## Repository layout

```text
simworld/         Engine implementation and public API
  modules/        Package reserved for built-in simulation modules
  editor/         Package reserved for the headless editor and GUI
tests/            Fixtures, behavior checks and executable README examples
docs/             Developer guide, contracts and milestone artifacts
plans/            Sequential implementation steps and progress evidence
BLUEPRINT.md      Specification for the intended complete project
pyproject.toml    Package metadata, dependencies, extras and pytest configuration
```

The core runtime uses stdlib and NumPy. It must remain independent of the editor,
Dear PyGui and pygame. Packaging declares `test`, `editor` and `viewer` extras;
only the test extra is installed in the recorded environment. Editor/viewer
execution and cross-platform GUI support remain future verification work.

## Development workflow

Work follows one numbered step at a time. **Step 044 — Define queued events and
handlers** in [Phase 3](plans/03-behavior.md) is next.

1. Read the next unchecked step, its blueprint sections and the progress log.
   Inspect repository guidance and git status, preserving existing work.
2. For new behavior, write a focused failing test, implement the scoped change
   and review/refactor it. Documentation and verification tasks use direct checks.
3. Run the step's acceptance checks and relevant regressions. Complete the full
   suite and stated exit gate at each phase boundary.
4. Record actual results, changed files and any skipped checks in the progress
   log, then check off the completed step.
5. Report the result and stop at that boundary. Continue with another step when
   requested.

The workflow does not require committing, pushing or publishing. The plan keeps
later features separate from the behavior currently available in this checkout.
