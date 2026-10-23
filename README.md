# 2D Simulation Sandbox

A deterministic, fixed-step simulation framework and example game built with
Python 3.13 and `pygame-ce`. The Project Hub opens playable worlds, a Quick
Sandbox, Entity Studio, and Behavior Studio. Entities can combine declarative
appearance and state, an ordered stack of reusable behavior components, and an
optional custom Python script.

See the [developer guide](docs/DEVELOPER_GUIDE.md) for the architecture and
complete examples of adding an entity or selectable world.

## Setup

Python 3.13 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

Open the Project Hub:

```powershell
simulation-sandbox
# or
python -m sim_sandbox
```

List content or launch one directly:

```powershell
simulation-sandbox --list-worlds
simulation-sandbox --list-entities
simulation-sandbox --list-behaviors
simulation-sandbox --world wandering_plains --seed 42 --entities 1000
simulation-sandbox --world empty_sandbox --entities 25
```

Open the entity creation studio directly:

```powershell
simulation-sandbox --editor
simulation-sandbox --entity-editor
simulation-sandbox --behavior-editor
simulation-sandbox --sandbox my_entity --terrain compact --seed 42 --entities 25
```

`--editor` remains an alias for `--entity-editor`. Direct-launch options bypass
the Project Hub. Using `--seed` or `--entities` without a direct launch option
prefills world selection.
Seeds must be from `0` through `4,294,967,295`; populations must be from `0`
through `10,000`.

Bundled worlds:

| ID | Description | Defaults |
| --- | --- | --- |
| `wandering_plains` | 256×256 procedural map with wandering agents | seed 1, 1,000 agents |
| `empty_sandbox` | Compact 96×96 procedural map | seed 1, 0 agents |

## Controls

| Input | Action |
| --- | --- |
| W/A/S/D or arrow keys | Pan camera |
| On-screen direction buttons | Click or hold to pan |
| Middle-drag | Pan camera |
| Mouse wheel | Zoom around cursor |
| Left click an entity | Select, inspect, and follow it |
| Right click an entity | Remove it |
| F | Toggle follow for the selected entity |
| C | Clear selection |
| Space | Pause/resume simulation |
| Period (`.`) | Advance one tick while paused |
| 1 / 2 / 3 / 4 | Set 0.25× / 1× / 2× / 4× speed |
| R | Restart with the current launch options |
| N | Restart with the next seed |
| Escape | Open the pause menu |

The pause menu provides Resume, Restart, Main Hub, and Quit. Restarting,
returning home, and quitting cleanly close the current world.

## Tests and benchmark

```powershell
python -m pytest
simulation-benchmark --world wandering_plains --entities 10000 --ticks 300 --render-frames 120
simulation-benchmark --behavior-stack --entities 10000 --ticks 300 --render-frames 120
```

The benchmark defaults to `wandering_plains` with 10,000 agents. The second
command measures editable entities with Constant Velocity, Keep In Bounds, and
Spin components. It uses SDL's
dummy video driver and reports update/render averages and p95 measurements.

## Entity Studio

The integrated studio creates reusable projects under
`content/entities/<entity_id>/`. Design configures tags, declared state,
collision radius, shapes, colors, and PNG sprites. Behaviors attaches reusable
components in execution order. Code edits entity-specific callbacks; Preview
runs the complete draft in a deterministic test world.

On the first launch the library is empty. Click **Create First Entity**, enter a
lowercase ID such as `energy_orb` and a display name, then use this workflow:

1. **Design** changes the shape/sprite and declared state properties. The small
   appearance panel updates from the current form.
2. **Behaviors** searches the preset/custom library. Add components, reorder or
   enable them, and edit per-attachment parameters.
3. **Code** edits the optional entity-specific callbacks, which execute after
   attached component callbacks.
4. **Preview** automatically applies the current draft and starts it in the test
   world. Use Run, Pause, Step, Reset, Seed, Count, and Speed above the world.
5. **Save** validates and writes the project. **Apply** runs an unsaved draft
   without writing it to disk.

Use `Ctrl+S` to validate, save, and apply, or `F5` to apply an unsaved draft.
The preview provides pause, single-step, reset, speed, seed, and population
controls. Runtime and syntax errors are shown without closing the editor.

Editable Python runs in a child process during preview, so accidental crashes
and infinite loops do not freeze the editor. This is fault isolation, not a
security sandbox: entity scripts are trusted local Python code.

World factories can spawn a saved project through the registry:

```python
from sim_sandbox.game.entity_projects import EntityProjectRegistry

registry = EntityProjectRegistry("content/entities")
registry.configure_world(world)
world.spawn_project("my_entity", x, y)
```

## Behavior Studio

Open Behavior Studio with `simulation-sandbox --behavior-editor`. It ships 24
read-only presets spanning movement, terrain, state, lifecycle, interaction,
organism, and visual tasks. Inspect a built-in and use **Duplicate** to create
an editable project under `content/behaviors/<behavior_id>/`.

Behavior forms define typed configuration (`behavior.config`), private typed
runtime state (`behavior.state`), required entity properties, dependencies,
exclusive groups, and written capabilities. Code uses these callbacks:

```python
def init(behavior, entity, world):
    pass

def update(behavior, entity, world, dt):
    entity.x += behavior.config["speed"] * dt

def delete(behavior, entity, world):
    pass
```

Preview can generate a compatible circle host or use a saved entity. Fixture
rows add up to 50 saved entities or tagged markers for food, threat, target,
damage, sensor, and reproduction tests. Apply runs an unsaved draft in the
isolated worker.

Attachments initialize and update from top to bottom, followed by the entity's
custom script. Cleanup calls the custom script first and attachments in reverse
order. Missing requirements and exclusive-group conflicts block Apply/Save;
multiple position writers produce an order warning.

## Quick Sandbox

Quick Sandbox creates an ad-hoc Compact, Standard, or Large procedural world.
Add up to eight saved-entity population rows, with a combined limit of 10,000.
It is the fastest way to test content without writing a world package.

## Package overview

```text
src/sim_sandbox/
├── engine/          # Entity lifecycle, World, clock, camera, spatial hash
├── game/            # Terrain, entity/behavior projects, presets, and worlds
├── presentation/    # Project Hub, studios, gameplay, renderers, and screens
├── app.py           # Compatibility entry point
├── benchmark.py
└── __main__.py
```

The previous imports remain available. For example, both
`sim_sandbox.entity.Entity` and `sim_sandbox.engine.entity.Entity` refer to the
same class.
# organism-experiment
