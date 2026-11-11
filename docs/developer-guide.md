# simworld developer guide

This guide explains how the current engine works and how to extend it. It covers
package version **0.1.0**, with implementation **Steps 001–029 complete**, as of
**11 November 2026**. The step number matters: the package version alone does not
identify which parts of the blueprint have been built. Phase 1 has passed its
verification gate; the [ECS contracts](ecs-contracts.md) record frozen behavior
and integration requirements for later phases.

You can create entities, attach data, query that data, define reusable templates,
register systems, schedule their execution, and queue structural changes. The
engine exposes `World.step()` and `World.run()` to execute systems, apply queued
commands between systems, and advance the simulation clock.

Start with the walkthrough, then follow the sections on the parts you want to
understand. Each Python code block is a complete example that can run in a fresh
Python process with this package installed.

## Contents

- [Setup and a complete walkthrough](#setup-and-a-complete-walkthrough)
- [Architecture and source map](#architecture-and-source-map)
- [Components and their metadata](#components-and-their-metadata)
- [Registries and component serialization](#registries-and-component-serialization)
- [Entity identity and allocation](#entity-identity-and-allocation)
- [Typed grid allocation](#typed-grid-allocation)
- [World state and ownership](#world-state-and-ownership)
- [Entity and component operations](#entity-and-component-operations)
- [Queries and iteration](#queries-and-iteration)
- [Names and prefabs](#names-and-prefabs)
- [System registration](#system-registration)
- [Scheduler execution](#scheduler-execution)
- [Deferred commands](#deferred-commands)
- [Errors and debugging](#errors-and-debugging)
- [Testing and extending the engine](#testing-and-extending-the-engine)
- [Python patterns used in this code](#python-patterns-used-in-this-code)
- [Current implementation boundary](#current-implementation-boundary)

## Setup and a complete walkthrough

The package declares Python 3.10 or newer and NumPy. The pinned development
requirements require Python 3.12 or newer because NumPy 2.5.4 requires it. The
recorded environment uses Python 3.12.3, NumPy 2.5.4, and pytest 9.2.0. Using a
Python 3.12+ interpreter, prepare a new environment from the repository root with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

The requirements include an editable installation. Editing a Python file under
`simworld/` therefore changes what the environment imports without reinstalling
the package. If `.venv` already exists, use its interpreter directly.

Here is a small simulation using only implemented features:

```python
from simworld import Appearance, Position, World, component, prop, system

@component(category="example")
class Velocity:
    x: float = prop(1.0, tooltip="Horizontal distance per unit of time.")
    y: float = 0.0

world = World(width=20, height=20, seed=42, dt=0.5)
walker = world.spawn(Position(2, 3), Velocity(4, 0), name="walker")

@system(stage="act", reads=("Velocity",), writes=("Position",))
def move(world):
    for entity, position, velocity in world.query(Position, Velocity):
        position.x += velocity.x * world.dt
        position.y += velocity.y * world.dt
        if not world.has(entity, Appearance):
            world.commands.add(entity, Appearance(size=2))

world.register(move)
world.step()

# The system changes fields and its queued addition is applied before it finishes
# its scheduled turn. The clock advances after the whole pass succeeds.
assert world.get(walker, Position).x == 4
assert world.get(walker, Appearance).size == 2
assert world.commands.apply() == 0
assert world.tick == 1 and world.time == 0.5
```

`walker` is an integer identifying an entity. `Position` and `Velocity` instances
hold that entity's data. `move` supplies behavior. The world stores the data and
the scheduler calls the behavior. The command buffer delays the addition of a
component until `apply()`.

Use `world.run(steps)` for repeated steps. Direct `world.scheduler.run_step()`
executes and flushes commands at the current tick, while leaving time and tick
unchanged. World.step owns clock advancement.

## Architecture and source map

ECS means **entity, component, system**. An entity provides identity, a component
provides data, and a system provides behavior that operates on matching entities.
For example, an entity with Position and Velocity can be moved by a movement
system. Another entity may have Position and Appearance without any Velocity.
There is no requirement to define one large class containing every possible
property and behavior of a simulated object.

The ownership relationships are:

```text
Process
  COMPONENTS registry: names -> class definitions and field metadata
  active registration stack: temporary destinations for system decorators

World
  settings and resources
  allocator: live slots and generations
  component stores: component name -> entity id -> component instance
  entity names and prefab templates
  scheduler: system definitions and execution order
  command buffer: pending mutations and callbacks
```

Component definitions are shared across worlds through the global registry.
Entity data, names, prefabs, scheduled system definitions, and pending commands
belong to each world. This distinction explains why registering a component makes
its type available everywhere while spawning an entity affects one world.

| Source | Responsibility |
| --- | --- |
| [simworld/__init__.py](../simworld/__init__.py) | Convenient public imports |
| [simworld/errors.py](../simworld/errors.py) | Exception types and helpful lookup diagnostics |
| [simworld/registry.py](../simworld/registry.py) | Named registries, component decorators, field metadata, component serialization, active registration contexts |
| [simworld/layers.py](../simworld/layers.py) | Typed NumPy grid allocation, layer metadata and named layer storage |
| [simworld/components.py](../simworld/components.py) | Position, Appearance, and Parent data types |
| [simworld/ecs.py](../simworld/ecs.py) | Entity ids, slot allocation, allocator undo/serialization, command buffer |
| [simworld/world.py](../simworld/world.py) | World state and entity, component, name, prefab, and system registration APIs |
| [simworld/systems.py](../simworld/systems.py) | System metadata, decorator, and scheduler |
| [tests](../tests) | Executable behavior contracts |
| [plans](../plans/README.md) | Sequential implementation plan and progress evidence |

`simworld/modules/` and `simworld/editor/` are package placeholders. Domain
modules and the editor are future work. A Python module simply means an importable
file such as `simworld.ecs`; the planned simulation module mechanism will group
simulation features and has not been implemented yet.

The package root exports World, WorldSettings, Position, Appearance, component,
prop, COMPONENTS, system, DEFAULT_STAGES, entity id decoding helpers, and the
engine exceptions. Import Parent from `simworld.components`; import
EntityAllocator and CommandBuffer from `simworld.ecs`; import SystemDef and
Scheduler from `simworld.systems`. Serialization and context helpers are available
from `simworld.registry`. Import Layer and LayerStore from `simworld.layers`.

## Components and their metadata

A component instance describes one aspect of an entity. The built-in types are:

| Component | Fields and defaults | Current meaning |
| --- | --- | --- |
| Position | `x=0.0`, `y=0.0` | Coordinates; no automatic movement or bounds enforcement |
| Appearance | `color=(255, 255, 255)`, `size=1` | Display data; rendering is not implemented |
| Parent | `entity=0` | Optional parent reference; no hierarchy enforcement or cascading deletion |

### What the component decorator does

`@component` runs when Python defines the class. It selects a registered name,
checks for collisions, converts an ordinary class into a dataclass with slots,
examines its fields, and registers a ComponentInfo record. It attaches the
registered name to the class as `__component_name__` and returns the class.

A dataclass supplies generated methods such as initialization, representation,
and equality. Slots give its instances declared storage locations and normally
prevent adding arbitrary new attributes. If the supplied class has its own dataclass
definition, the decorator preserves it; existing frozen or non-slotted behavior
stays in effect. A subclass that only inherits dataclass metadata is processed
so its new fields, defaults and factories are included. Frozen inheritance must
still follow Python dataclass rules; explicitly decorate such subclasses with
the appropriate options before applying @component.

Both `@component` and `@component(name="CustomName", category="example")` work.
A name already owned by a different logical class raises DuplicateNameError.
The same pair of `__module__` and `__qualname__` may register again, supporting
replacement of metadata when a class is redefined. Existing instances are not
migrated to the replacement class.

### Why prop exists

`prop()` wraps `dataclasses.field()`. It describes a field's default and carries
metadata that other tools can inspect. The instantiated component still contains
an ordinary value such as a number or list.

```python
from simworld import COMPONENTS, component, prop

@component(category="example")
class Health:
    value: float = prop(100.0, min=0, max=100, tooltip="Remaining health.")
    tags: list[str] = prop(default_factory=list)
    cache: object = prop(None, serialize=False, init=False)

first, second = Health(), Health()
first.tags.append("injured")
assert second.tags == []

info = COMPONENTS.get("Health")
assert info.cls is Health
assert info.fields[0].name == "value"
assert info.fields[0].min == 0
assert info.fields[2].serialize is False

# Metadata describes a limit; it does not enforce the limit.
first.value = -10
assert first.value == -10
```

| prop argument | Effect |
| --- | --- |
| `default` | Value used when the constructor argument is omitted |
| `default_factory` | Callable invoked to create a default value for each instance |
| `min`, `max` | Recorded range hints; no runtime clamping or validation |
| `tooltip` | Recorded explanatory text |
| `serialize` | Whether component_to_dict includes this field |
| `init` | Whether the generated constructor accepts this field |
| Extra keywords | Arbitrary metadata, such as `widget="color"` |

Use `default_factory=list` or `default_factory=dict` for mutable containers.
Passing `list` passes the function; passing `list()` creates a list immediately.
Defaults and factories cannot both be specified. Reflection also invokes a
factory once during component registration to obtain a sample default for
FieldInfo, so factories should be inexpensive and avoid external side effects.

Type annotations describe intended types; ordinary dataclasses do not enforce
them. `Position(1, 2)` retains integer values. A required field remains required
by its constructor even though its reflected FieldInfo.default is recorded as
None. That metadata value alone cannot distinguish a required field from a field
whose actual default is None.

## Registries and component serialization

A Registry is an ordered dictionary with explicit duplicate handling and useful
errors. `Registry[T]` describes the type of its stored values to type checkers;
it does not validate those values at runtime.

`register(name, item)` returns the stored item and rejects duplicates unless
`replace=True`. `get(name)` raises the configured unknown-name exception on a
miss. `unregister(name)` returns the removed item or None. `names()` returns a new
list, while `items()` exposes a live view of the dictionary. Iterating a registry
produces its names in insertion order.

COMPONENTS stores ComponentInfo records. Each record contains a name, class,
category, documentation string, and a list of FieldInfo records. FieldInfo stores
the field name, a textual type description, default, range hints, tooltip,
serialization flag, and metadata dictionary. This is reflection: the engine
examines a class so that tools can work with components without hardcoding their
individual fields.

`component_name()` resolves a registered string, class, or instance to its
registered name. Supplying an unknown string raises UnknownComponentError;
supplying an unregistered object raises NotAComponentError.

### Converting component data

```python
from simworld import Appearance
from simworld.registry import component_from_dict, component_to_dict

original = Appearance(color=(20, 40, 60), size=3)
data = component_to_dict(original)
assert data == {"color": [20, 40, 60], "size": 3}
restored = component_from_dict("Appearance", data)
assert restored == original
assert isinstance(restored.color, tuple)
assert component_from_dict("Appearance").size == 1
```

`component_to_dict()` requires a component instance; registered names and classes
are rejected with NotAComponentError. It returns field data without a component-name wrapper. It
omits fields marked `serialize=False`, converts tuples to lists, converts NumPy
scalars to native values, converts dictionary keys to strings, and recursively
handles supported containers and dataclass instances. It calls a component's
`_check_serializable()` hook first if present. Unsupported values, such as ordinary
opaque objects or NumPy arrays, raise SerializationError.

The result is data suitable for ordinary JSON workflows, not a JSON string.
Nested dataclass conversion includes their fields directly; it does not apply a
second component metadata policy to those nested objects. Non-finite floats are
not rejected here, so strict JSON interoperability may require extra validation.

`component_from_dict()` rejects unknown fields and invokes the registered class
constructor. Missing fields use constructor defaults. A list becomes a tuple
when that field's reflected default is a tuple. There is no general recursive
reconstruction of nested classes or annotation-driven type validation. Constructor
TypeError exceptions are wrapped as SerializationError.

A nonserialized field needs a suitable default if omitted data must reconstruct
successfully. An `init=False` field is not a constructor parameter; serializing
and then passing it back can fail, so runtime-only fields commonly use both
`init=False` and `serialize=False`. Input containers are not generally deep-copied
by component_from_dict; prefab construction provides its own copying boundary.

## Entity identity and allocation

An Entity is an integer, not an object containing components. Its lower 32 bits
hold the **slot index**, and its remaining higher bits hold the **generation**:

```text
entity = (generation << 32) | index
index = entity & ((1 << 32) - 1)
generation = entity >> 32
```

`INDEX_BITS` is 32. `INDEX_MASK` is `4294967295`, a binary value with its lowest
32 bits set. Masking extracts the index; shifting right extracts the generation.
Python integers are not restricted here to a fixed 64-bit storage type.

The allocator maintains three lists:

| List | Example | Purpose |
| --- | --- | --- |
| `generations` | `[1, 2, 1]` | Current generation for each allocated slot |
| `alive` | `[True, False, True]` | Whether each slot currently has a live entity |
| `free` | `[1]` | Released slot indices available for reuse |

The same index addresses corresponding entries in generations and alive. The
free list is a stack: the last released slot is reused first. New slots start
with generation 1. Releasing a slot marks it dead, increases its generation, and
pushes its index onto free.

```python
from simworld import World, entity_generation, entity_index

world = World()
old = world.spawn()
assert old == 4294967296
assert entity_index(old) == 0 and entity_generation(old) == 1

world.despawn(old)
new = world.spawn()
assert new == 8589934592
assert entity_index(new) == 0 and entity_generation(new) == 2
assert not world.is_alive(old)
assert world.is_alive(new)
```

The generation stops an old reference from silently referring to a new entity
that reused the same slot. Zero is invalid. `is_alive()` also rejects booleans,
non-integers, negative values, out-of-range slots, and mismatched generations.
The bit-decoding helpers themselves simply perform bit operations; they do not
validate liveness.

Ids are local to a world. Two worlds can produce the same integer id for unrelated
entities. Keep the world and its ids together; passing an id from another world
cannot reliably be detected by the id alone.

### Allocation undo and snapshots

EntityAllocator has low-level methods intended for later editor work.
`revive(e)` reverses the most recent compatible release, restoring the old
generation. `rollback_alloc(e)` reverses an allocation without incrementing its
generation. Both require correct last-in-first-out use; their checks are not a
complete history of every world operation.

These methods only change allocation state. They do not restore components,
names, or pending commands. Calling them directly during ordinary world mutation
can leave those structures inconsistent.

`to_dict()` copies generations, alive, and free into a dictionary. `from_dict()`
restores those lists without sharing them with the input. It assumes valid
allocator data; it is neither a full world snapshot nor an untrusted-data schema
validator.

## Typed grid allocation

A layer stores one grid of values over a rectangular area. Components describe
individual entities; a layer describes cells, such as a numeric value at every
position. Layer and LayerStore work directly through `simworld.layers`, including coordinate
reads/writes and raw NumPy indexing.
World integration is scheduled for Step 034; World does not yet have layers or
define_layer/define_field methods.

```python
import numpy as np
from simworld.layers import Layer, LayerStore

heat = Layer("heat", width=5, height=2, dtype=np.float32, default=1.5,
             min=0, max=10, color=(255, 80, 20), kind="field")
assert heat.data.shape == (2, 5)
assert heat.data.dtype == np.dtype(np.float32)
assert heat.is_float
assert heat.data[1, 4] == 1.5  # Row y=1, column x=4.

velocity = Layer("velocity", 5, 2, dtype=np.float32, default=(1, -1), shape=(2,))
assert velocity.data.shape == (2, 5, 2)
np.testing.assert_array_equal(velocity.data[0, 0], [1, -1])
layers = LayerStore(heat=heat, velocity=velocity)
assert layers["heat"] is heat
```

A scalar layer has data shape `(height, width)`. The shape option gives extra
cell dimensions: shape=(2,) stores a pair per cell, while shape=(2, 3) gives
array shape `(height, width, 2, 3)`. NumPy broadcasts the default into all cells
and applies the requested dtype through np.full. Invalid shapes, dtypes or
incompatible defaults raise NumPy's normal errors. Array allocation is independent
between layers, and numeric cells occupy separate locations in each array.

Metadata includes name, width, height, dtype, default, shape, min/max, decay_rate,
diffusion_rate, color, tooltip, kind and props. The constructor uses decay and
diffusion arguments to populate the corresponding rate attributes. Dtype is
normalized to np.dtype; shape and a supplied color are stored as tuples. Props
receives a shallow dictionary copy, so its top-level keys are independent while
nested mutable values may remain shared. The default attribute retains the
supplied value; numeric grid data is allocated separately. is_float tests whether
the dtype is a real floating-point type; integer and boolean layers return False.

Initial allocation does not clamp or evolve the array. Cell set now uses the
configured min/max on float layers, as do add, fill and explicit clamp.
Bounded arithmetic is implemented; diffusion and decay arrive in Step 031.

### Reading and writing cells

Coordinate APIs take `(x, y)` and floor each coordinate to a cell index. Cell
(i, j) covers positions `[i, i+1)` by `[j, j+1)`. A slightly negative coordinate
therefore lies outside the grid; it does not truncate to zero or wrap around.
`in_bounds(x, y)` tests the half-open world bounds, from zero up to width/height.

```python
from simworld import OutOfBoundsError, Position
from simworld.layers import Layer

food = Layer("food", width=5, height=2, min=0, max=10)
food.set(4.8, 1.3, 20)          # Floors to x=4, y=1, then clamps to 10.
assert food.get(4, 1) == 10
food.set(Position(2.5, 0.1), 3)
assert food.get((2, 0)) == 3
assert food.in_bounds(4.999, 1.999)
assert not food.in_bounds(-0.01, 0)
assert food.get(-0.01, 0, default=None) is None
try:
    food.get(5, 0)
except OutOfBoundsError:
    pass
else:
    raise AssertionError("The right edge is outside the grid.")

food[1, 4] = 20               # Raw [y, x] assignment bypasses clamping.
assert food.get(4, 1) == 20
assert food[-1, -1] == 20     # NumPy negative indexing still works here.
```

Get accepts separate coordinates, a two-item pair, or an object with x/y
attributes. Set accepts `set(x, y, value)`, `set(pair, value)` or
`set(position, value)`. It returns None. Out-of-bounds reads and writes raise
OutOfBoundsError with the layer name, cell indices and dimensions. Passing an
explicit keyword default to get returns that exact object outside the bounds,
including None or zero. It does not substitute for malformed or non-finite
coordinates: coordinate unpacking and flooring retain their normal Python errors.

Scalar get returns the stored value through NumPy's item operation, normally a
native Python number or boolean. Vector/matrix get returns the cell array as a
view; editing it changes the stored data. Float set clamps each value to any
configured lower/upper limit before assignment. Integer and boolean layers use
NumPy assignment conversion without range clamping. Neither get nor allocation
repairs values already written outside limits through raw indexing.

Brackets delegate directly to data: `layer[y, x]`, slices, trailing cell dimensions,
views, broadcasting and negative indices follow NumPy semantics. Bracket access
performs no coordinate flooring or layer-level bounds/clamp policy; invalid array
indices raise NumPy's IndexError. World-facing coordinates and raw array indexing
therefore have distinct conventions.

### Bounded arithmetic and grid summaries

Add and take operate on scalar quantities and accept the same coordinate forms
as set: `(x, y, amount)`, `(pair, amount)` or `(position, amount)`. They return
Python floats describing the actual stored change, including dtype conversion
and rounding. Vector/matrix cells raise SimWorldError before mutation; their
individual values can be changed through set or raw indexing.

Add returns a signed delta. A negative amount subtracts; a positive amount adds.
Float-layer min/max limits apply through set, so an addition can be only partly
applied. Integer and boolean layers retain NumPy conversion without those float
limits. A change too small for the storage dtype can produce a zero delta.

Take rejects negative requests with SimWorldError. It removes at most what is
available above min, or above zero when min is None. Its return value describes
what the caller actually received, rather than what it requested. Integer cells
remove whole units: fractional requests and available amounts are rounded down
to avoid exceeding the request or crossing the floor. Floating-point results
reflect the stored dtype's precision and should be compared with a tolerance.

```python
from simworld.layers import Layer

food = Layer("food", 2, 1, default=2, min=0, max=5)
assert food.take(0, 0, 10) == 2.0
assert food.take(0, 0, 10) == 0.0
assert food.add((1, 0), 10) == 3.0  # The other cell grows from 2 to its cap of 5.
assert food.add(1, 0, -10) == -5.0
assert food.total() == 0.0

food.fill(3)
assert food.total() == 6.0 and food.mean() == 3.0
food[0, 0] = 9                   # Raw writes may exceed limits.
food.clamp()
assert food.get(0, 0) == 5
assert food.total() == 8.0
```

Take enforces only its removal floor. It does not repair a cell already below
that floor, and it does not apply max to a raw value above the cap. That avoids
creating resources or removing more than requested while correcting unrelated
state. Use clamp explicitly to repair out-of-range float data.

Fill broadcasts its value into the existing array, then calls clamp. Clamp applies
configured float min/max limits in place, including vector/matrix elements;
it does nothing when there are no limits or the dtype is not floating-point.
Both preserve the array object and existing views, and return None. Fill does not
change default metadata. Total and mean reduce every array dimension, including
trailing cell dimensions, and return Python floats. They use NumPy's normal
reduction behavior, including overflow rules and empty-array warnings/results.

LayerStore preserves ordinary dictionary insertion, lookup and replacement
behavior. A missing bracket lookup raises UnknownLayerError with known names and
close matches, without inserting the missing name. Like a normal dict, get returns
None or its supplied fallback for an absent name. It does not validate inserted
values or allocate layers automatically.

## World state and ownership

World is the object that connects the engine's services. Its constructor validates
setting names, creates WorldSettings and resources, initializes empty entity
stores and name maps, and creates its scheduler and command buffer.

| Setting | Default | Current use |
| --- | --- | --- |
| width, height | 64, 64 | Retained World dimensions; standalone Layer grids are not yet attached to World |
| seed | 0 | Initializes the world's NumPy generator |
| dt | 1.0 | Initial simulation time increment stored in resources |
| cell_size | 8.0 | Retained for later spatial/rendering work |
| energy_component | `"Energy"` | Retained configuration for later behavior |
| default_speed | 1.0 | Retained configuration for later behavior |
| shuffle_actions | True | Retained configuration for later action processing |
| extra | New empty dictionary | Application configuration |

Unknown setting names raise TypeError. The constructor does not generally check
ranges or enforce annotations. Passing nonempty `modules` raises
NotImplementedError.

Resources hold values shared across systems: time starts at `0.0`, tick at `0`,
dt at the supplied value, rng is `np.random.default_rng(seed)`, and settings
references `world.settings`. Applications can add their own resource keys.

`world.width` and `world.height` read settings. `world.dt`, `world.time`,
`world.tick`, and `world.rng` read resources. Changing `world.settings.dt` after
construction does not update `world.resources["dt"]`; runtime code reads the
latter through `world.dt`. Similarly, changing the stored seed does not recreate
the generator. The `extra` dictionary receives a shallow copy at construction,
so nested mutable objects can remain shared with the caller.

Use `world.rng` for simulation randomness. Repeating the same sequence of calls
with the same seed and compatible versions supports reproducible results.
The seed alone cannot compensate for changing execution order or the number of
random draws.

### How components are stored

Conceptually, `_stores` looks like this:

```text
"Position"   -> {entity_a: Position(...), entity_b: Position(...)}
"Appearance" -> {entity_a: Appearance(...)}
```

This layout groups instances by component type. A query can iterate a relevant
store instead of scanning every entity. An empty entity exists only in the
allocator until components are attached.

Spawn and add retain the exact component instances supplied by the caller.
Get and query return those same objects. Mutating `world.get(e, Position).x`
therefore changes stored data immediately. Passing the same mutable component
instance to two entities deliberately shares that object; create a fresh instance
when independent values are needed.

`components_of(e)` creates a new dictionary but its values remain references to
the original components. In contrast, `world.prefabs` returns a deep copy of its
template data. Leading underscores identify internal state; use public mutation
methods to preserve relationships between allocation, stores, and names.

## Entity and component operations

| Operation | Behavior |
| --- | --- |
| `spawn(*components, name=None)` | Validate, allocate a new entity, attach data and optional name; return id |
| `despawn(e)` | Remove all stored components and the name, then release the slot |
| `add(e, *components)` | Attach or replace component instances on an existing live entity |
| `remove(e, *components)` | Remove specified registered component types; absence is harmless |
| `get(e, component)` | Return the instance or raise a lookup-related error |
| `try_get(e, component)` | Return None for a dead entity or absent component |
| `has(e, *components)` | Test whether a live entity has every requested type |
| `components_of(e)` | Return a new name-to-instance mapping |
| `entities()` | Return live ids in allocator slot order |
| `count()` | Count all live entities, including empty and reserved ones |

Spawn creates identity; add changes the data attached to an existing identity.
Spawn/add require instances, such as `Position(2, 3)`. Lookup and removal accept
registered names, classes, or instances as type selectors.

Spawn rejects duplicate component types and duplicate names before allocating.
Add validates its full argument list before attaching anything; if the same type
appears multiple times in a valid call, the last instance wins. Remove validates
all requested type names before removing anything.

Get distinguishes a live entity missing a component (MissingComponentError) from
an invalid or stale id (StaleEntityError). It resolves the component first, so an
unknown component name can fail before entity validation. Non-integer keys are
rejected before the store lookup, even if they compare equal to a live id.
Try_get and has check
liveness first: dead ids return None or False even if the requested component is
unknown. On live entities, unknown component names still raise errors.

```python
from simworld import Appearance, Position, World

world = World()
entity = world.spawn(Position(1, 2))
world.add(entity, Appearance(size=4))
world.add(entity, Position(8, 9))  # Replace the existing Position.
assert world.get(entity, "Position") == Position(8, 9)
assert world.has(entity, Position, Appearance)
world.remove(entity, Appearance)
assert world.try_get(entity, Appearance) is None
world.remove(entity, Appearance)  # Already absent; harmless.
world.despawn(entity)
assert world.try_get(entity, Position) is None
```

## Queries and iteration

`query(Position, Appearance)` yields tuples of
`(entity_id, position_instance, appearance_instance)`. Every requested component
must be present. Tuple layout follows argument order, even when the engine chooses
a different component store as its iteration source.

`without=(Appearance,)` excludes any entity having Appearance. Multiple exclusions
exclude an entity if it has any of those types. Query requires at least one
included component. `entities()` is the way to list all live entities.

```python
from simworld import Appearance, Position, World

world = World()
first = world.spawn(Position(1, 1))
second = world.spawn(Position(2, 2), Appearance())
third = world.spawn(Position(3, 3), Appearance())

assert [e for e, p in world.query(Position, without=(Appearance,))] == [first]
assert world.count(Position, Appearance) == 2

rows = world.query(Position)  # Capture the base store now.
world.spawn(Position(4, 4))   # Not part of that captured base store.
world.despawn(third)         # Removed before its row is yielded.
assert [e for e, p in rows] == [first, second]
```

### How query chooses its work

Query resolves all requested type names, chooses the smallest included store,
and copies its `(entity, component)` pairs into a list at the time of the query
call. Equal store sizes choose the first argument. It then checks each candidate
against the other stores and the exclusions while iterating. Before yielding, it
checks that the entity still belongs to the base store.

Iteration order is the chosen store's dictionary insertion order. It is not a
sort by numeric id and may change when the smallest store changes. `entities()`
has a separate order: allocator slot order.

The copied pairs protect against dictionary-size changes during iteration, but
this is not a full state snapshot. Component objects remain mutable references.
Other stores and exclusions are consulted during iteration. Replacing a base
component after creating the query can leave the query holding the old instance;
replacing a component in another store can be observed when that row is examined.
Use deferred structural commands when code benefits from a clear mutation boundary.

With a base store of size B and K requested component types, the main work is
roughly B times K membership/value checks plus exclusions; the base snapshot also
uses memory proportional to B. This describes the algorithm, not a performance
benchmark. Query can create empty internal stores for known requested types.

`count(*components, without=...)` counts query matches. With no included component
arguments, count returns the allocator's live count and currently ignores without.
`has(e)` with no component arguments returns True for a live entity.

## Names and prefabs

### Entity names

Names are optional strings unique within a world. Empty strings are valid names;
None means unnamed. `_names` maps names to ids, while `_entity_names` maps ids back
to names. The public APIs keep both directions consistent.

`set_name(e, name)` assigns or changes a name. Passing None removes it. Assigning
the existing name is a no-op; trying to use another entity's name fails before
changing either map. `entity(name)` resolves a name or raises UnknownNameError
with known names and suggestions. `name_of(e)` returns None for an unnamed live
entity and raises for a stale id. Despawn releases the name for reuse.

### Prefab templates

A prefab is a named recipe for components. It lets several entities start with
similar values while giving each its own component data.

```python
from simworld import Appearance, Position, World

world = World()
world.define_prefab("walker", {
    Position: {"x": 1, "y": 2},
    Appearance: {"color": (20, 150, 50), "size": 2},
})

first = world.spawn_prefab("walker", entity_name="first")
second = world.spawn_prefab(
    "walker", entity_name="second",
    Position={"x": 9},
    **{"Appearance.size": 4},
)
assert world.get(first, Position) == Position(1, 2)
assert world.get(second, Position) == Position(9, 2)
assert world.get(second, Appearance).size == 4
assert world.get(first, Position) is not world.get(second, Position)

invisible = world.spawn_prefab("walker", Appearance=None)
assert not world.has(invisible, Appearance)
```

Define_prefab accepts a mapping from registered component selectors to mappings
of field values. It copies the input and constructs components to validate each
entry before publishing the template. Redefining a prefab replaces the old one
only after successful validation.

Spawning deep-copies the template, applies overrides in supplied order, constructs
the resulting components, and calls spawn. An override mapping merges fields at
the component level. A dotted key such as `"Position.x"` updates one field. A
matching component instance replaces that component after being deep-copied.
None removes a component from the recipe. An override can introduce a registered
component that was absent from the original template.

Dotted paths support `Component.field`; they do not traverse arbitrary nested
objects. Merging fields replaces supplied field values; it does not recursively
merge dictionaries inside a field. Construction and override errors occur before
ordinary prefab spawning allocates an id. Missing template names raise
UnknownPrefabError.

## System registration

A system is a callable taking a World. It can query entities, mutate component
values, use resources, and queue changes. The `@system` decorator creates a
SystemDef and attaches it to the function as `__sim_system__`. It returns the
original function, so calling that function directly remains possible.

| SystemDef field | Meaning |
| --- | --- |
| name, fn | Registered name and callable |
| stage, order | Stage membership and ordering within that stage |
| reads, writes | Descriptive tuples; no access enforcement or dependency solver |
| module | Optional origin tag for future module integration |
| enabled | Whether execution is permitted |
| every | Tick interval; default 1 |
| doc | Stripped function documentation |
| seq | Sequence assigned on scheduler registration |
| base_order | Initial order retained as metadata |

Outside an active loading context, decoration alone does not place a system in a
world. `world.register(*objects)` accepts decorated functions or SystemDef values,
registers them, and returns the world. `world.add_system(value, **overrides)` also
accepts plain functions and returns the registered SystemDef.

Add_system makes a dataclass copy before registration, so changing one world's
enabled/order metadata does not alter another world's copy or the decorator's
original definition. The function itself remains shared; state captured by its
closure can therefore still be shared. Overrides adjust fields on the copy.
The scheduler assigns seq, and an active `_current_module` supplies module origin.
Use `@world.system(...)` to decorate and register directly into a particular
world; this bound form requires parentheses and accepts the same scheduling
options as @system. It temporarily routes registration into that world even
inside another loading context, then restores the outer context.
`world.enable_system(name, enabled=True)` and `world.disable_system(name)` delegate
to the scheduler and raise UnknownSystemError for an unknown system.
Duplicate system names are rejected. Multi-object register calls are sequential,
not transactional: earlier registrations remain if a later one fails.

### Active loading contexts

```python
from simworld import World, system
from simworld.registry import active_world, loading_into

world = World()
assert active_world() is None
with loading_into(world):
    assert active_world() is world

    @system(stage="input")
    def mark_input(world):
        world.resources["input_seen"] = True

assert active_world() is None
assert world.scheduler.get("mark_input").fn is mark_input
world.scheduler.run_step()
assert world.resources["input_seen"] is True
```

`loading_into(world)` pushes the world onto a shared stack. A system decorator
checks `active_world()` and registers into the topmost world if one exists.
Nested contexts temporarily change the destination; the finally block pops the
stack even on exceptions. Exiting a failed context restores the destination but
does not undo registrations that already succeeded. The stack is process-global,
not isolated by thread or asynchronous task.

## Scheduler execution

The default stage order is:

```text
input -> sense -> decide -> act -> update -> late
```

Stage order takes precedence over numeric order. Within one stage, smaller order
values run first. Equal values use registration sequence. For example, an input
system with order 100 runs before an update system with order -100.

| Scheduler method | Behavior |
| --- | --- |
| `add_stage(name, after=None, before=None)` | Append a stage or insert it beside an existing stage; anchors are keyword-only |
| `add(definition, replace=False)` | Register a SystemDef; assign a fresh sequence |
| `get(name)` | Retrieve the stored definition |
| `remove(name)` | Remove a definition and invalidate ordering |
| `set_enabled(name, enabled)` | Change enabled state using bool conversion |
| `ordered()` | Return all definitions in stage/order/sequence order, including disabled ones |
| `run_step()` | Run eligible definitions and flush commands at the current tick without advancing it |

Add_stage rejects duplicate stage names, unknown anchors, and supplying both
before and after. Add rejects unknown stages and duplicate names unless explicit
replacement is requested. Replacement receives a new registration sequence.
Direct Scheduler.add stores the supplied definition itself; use World.add_system
when you want its copying behavior.

### Ordering cache and execution gates

The scheduler caches sorted lists for each stage in `_sorted`. Add, replace,
remove, and add_stage clear that cache. Direct changes to a definition's order or
stage require explicit cache invalidation. Directly editing the stages list or
systems dictionary also bypasses normal management, so prefer scheduler methods.

```python
from simworld import World

world = World()
calls = []
world.add_system(lambda w: calls.append("first"), name="first", order=1)
world.add_system(lambda w: calls.append("second"), name="second", order=2)
world.scheduler.run_step()
assert calls == ["first", "second"]

world.scheduler.get("second").order = 0
world.scheduler._sorted = None  # Required for this direct metadata edit.
world.scheduler.set_enabled("first", False)
calls.clear()
world.scheduler.run_step()
assert calls == ["second"]
```

For each ordered system, run_step checks enabled, an optional module-enabled
callback, and every. When `every > 1`, execution requires
`world.tick % every == 0`. Thus every=2 runs at ticks 0, 2, 4, and so on. The code
does not validate a positive interval; values at or below 1 bypass this gate.
Use positive integer intervals in application code.

Module gating is conditional on the world having a module_enabled method. The
current World has no module installation API or that method, so module tags alone
do not suppress execution.

Ordered builds a list for the pass. Registering another system during execution
does not add it to the already-created list; removing a system likewise does not
remove its existing reference from that list. Changes to enabled can still affect
a referenced definition before its turn. Schedule structural edits between passes
when predictable membership is needed.

### Timing and failure behavior

Set `scheduler.profile = True` to accumulate execution duration in seconds under
`scheduler.timings[name]`. The timer uses perf_counter and measures the system
function and its following command-buffer application. A finally block records
duration even if the function or its command application raises. Timings
accumulate across passes and can be cleared with `scheduler.timings.clear()`.
Stage-boundary and manual command application are outside those per-system timers.

A system or command-application exception propagates and stops the pass; prior
mutations are not rolled back. After each eligible system returns, run_step
applies its commands before invoking the next system. It also flushes at the end
of every stage, including empty stages, so pending commands are applied even with
no systems registered. Direct field edits and applied structural changes are
visible to later systems. Run_step does not advance time/tick or dispatch events;
event dispatch will be inserted before stage-boundary flushing in Phase 3.

### World steps and run loops

`world.step(dt=None)` executes one scheduler pass. All systems in that pass see
its current tick and time; after successful completion, time increases by the
selected dt and tick increases by one. A supplied dt overrides the resource only
for that step. The prior value is restored in finally, including when a system or
command raises. A zero override is valid: the tick advances while time stays fixed.
WorldSettings.dt remains unchanged.

`world.run(steps, dt=None, callback=None)` calls step repeatedly and returns the
same World. If supplied, callback receives that world after each completed step,
with its clock advanced and the ordinary dt restored. Returning the literal False
stops the loop; other values, including None and 0, continue. Zero or negative
steps execute no passes, following Python range behavior.

```python
from simworld import Position, World

world = World(dt=0.5)
entity = world.spawn(Position())

@world.system(stage="act")
def move(w):
    w.get(entity, Position).x += w.dt

def stop_at_three(w):
    return w.tick < 3

assert world.run(10, dt=0.25, callback=stop_at_three) is world
assert world.tick == 3 and world.time == 0.75
assert world.get(entity, Position).x == 0.75
assert world.dt == world.settings.dt == 0.5
world.disable_system("move")
world.step()
assert world.tick == 4 and world.time == 1.25
assert world.get(entity, Position).x == 0.75
```

A failed scheduler pass leaves time and tick unchanged but retains earlier
mutations. It is not an atomic transaction. A callback failure happens after a
successful step, so that step's clock advancement remains and later steps do not
run. Exceptions propagate to the caller. The clock increment uses the dt selected
at entry; changing the dt resource inside a system does not change that increment,
and the original resource value is restored on exit. Nested step/run calls on the
same world are not a supported simulation pattern.

## Deferred commands

A structural change creates or deletes an entity, or changes which component types
are attached to it. The command buffer records these operations so application
code can choose when to apply them. Changing `position.x` is an immediate field
edit and needs no buffer.

| Command | What happens when queued |
| --- | --- |
| `spawn(*components, name=None)` | Reserve a live id now; queue component/name attachment; return id |
| `spawn_prefab(prefab, entity_name=None, **overrides)` | Build independent prefab components now, then reserve/queue spawn; entity_name is keyword-only |
| `despawn(e)` | Queue deletion |
| `add(e, *components)` | Queue attachment/replacement |
| `remove(e, *components)` | Queue removal |
| `defer(fn)` | Queue a callback receiving the world |
| `apply(world=None, max_rounds=100)` | Execute queued operations and return the number successfully applied, excluding stale skips |

Apply defaults to the buffer's owning world. The explicit world argument is an
integration hook; pass the same owning world. Reservations always use the owning
allocator, and applying them to another world can target unrelated matching ids.

### A reserved entity is already alive

```python
from simworld import Appearance, Position, World

world = World()
entity = world.commands.spawn(Position(5, 6), name="pending")
world.commands.add(entity, Appearance(size=2))

assert world.is_alive(entity)
assert entity in world.entities()
assert world.count() == 1
assert world.components_of(entity) == {}
assert world.name_of(entity) is None
assert list(world.query(Position)) == []

assert world.commands.apply() == 2
assert world.get(entity, Position) == Position(5, 6)
assert world.get(entity, Appearance).size == 2
assert world.entity("pending") == entity
assert world.commands.apply() == 0
```

Reservation lets subsequent commands reference the id without waiting for spawn
application. An untouched reservation has no components, so component queries do
not find it. Since it is alive, direct world operations can still affect it before
application; keeping related changes in the buffer makes the ordering explicit.

Ordinary queued spawn retains the supplied component references. Mutating those
objects before apply changes what will be attached. Queued prefab spawn instead
builds copied components immediately; later template edits do not change that
queued spawn. Prefab construction errors occur before its reservation.

Queued names are assigned at apply time and are not separately reserved. Name
conflicts are therefore discovered during application. `_finish_spawn()` checks
the id and validates the complete component/name set before attaching data.

### Queue rounds

The buffer stores operation records in `_ops`. Apply takes the current list and
replaces `_ops` with a new empty list before executing the captured operations.
Callbacks that enqueue more commands put them in the new list. The current round
finishes first, then the next list becomes the next round.

```python
from simworld import World

world = World()
seen = []

def first(world):
    seen.append("first")
    world.commands.defer(lambda w: seen.append("third"))

world.commands.defer(first)
world.commands.defer(lambda w: seen.append("second"))
assert world.commands.apply() == 3
assert seen == ["first", "second", "third"]
```

This is queue order across rounds. It is not recursive execution of the new
callback at the moment it is enqueued. A callback can queue another spawn and
then further operations on its reserved id, all for the next round.

If work keeps generating more work, apply raises RuntimeError after max_rounds.
The limit counts rounds, not individual commands. The default is 100. The next
unprocessed round remains pending when the round limit is reached.

### Exceptions and partial progress

By default, apply catches StaleEntityError for each operation, increments
`commands.skipped`, and continues to later operations and rounds. For example,
two systems may both request deletion of the same entity: the first deletion
succeeds, and the second is skipped. An old id cannot mutate a replacement entity
that reused its slot with a newer generation.

```python
from simworld import Position, World

world = World()
entity = world.spawn(Position())
world.commands.despawn(entity)
world.commands.despawn(entity)
assert world.commands.apply() == 1
assert world.commands.skipped == 1
assert not world.is_alive(entity)

# The return value counts successes in this call; skipped is cumulative.
assert world.commands.apply() == 0
assert world.commands.skipped == 1
```

Each buffer starts with `skipped=0` and `strict=False`. Skipped counts accumulate
across apply calls, including empty calls. Assign `commands.skipped = 0` when an
explicit reset is needed. Set `commands.strict = True` to re-raise the original
StaleEntityError and stop application; a strict-mode failure does not increment
skipped. Other buffers' settings and counters are independent.

```python
from simworld import StaleEntityError, World

world = World()
entity = world.spawn()
world.despawn(entity)
world.commands.strict = True
world.commands.despawn(entity)
try:
    world.commands.apply()
except StaleEntityError:
    pass
else:
    raise AssertionError("Strict mode must report the stale target.")
assert world.commands.skipped == 0
```

The same handling applies to StaleEntityError raised inside a deferred callback.
The callback's earlier side effects remain, and anything it already queued still
belongs to the next round. In default mode, that callback counts as one skipped
operation. MissingComponentError, DuplicateNameError, and other non-stale
exceptions propagate in both modes; they do not increment skipped.

Application is not transactional. Successful earlier operations remain applied.
Because the current round was detached from `_ops`, the unexecuted remainder of
that detached round is not retried after an exception. Operations already queued
into the next round remain pending. A failed spawn leaves its reservation alive;
the engine does not automatically release that id or undo earlier work.

These rules also apply to propagated exceptions from callbacks. A callback is
arbitrary code and can mutate state before it raises. Callers that catch application
errors must inspect the resulting state rather than assuming the buffer represents
a retryable transaction.

## Errors and debugging

Engine exceptions derive from SimWorldError. Several also derive from a useful
built-in category:

| Exception | Built-in category | Typical cause |
| --- | --- | --- |
| UnknownNameError and specialized subclasses | LookupError | Unregistered component, prefab, system, or missing entity name |
| StaleEntityError | LookupError | Released, invalid, or never-allocated id |
| MissingComponentError | LookupError | Live entity lacks a requested component |
| DuplicateNameError | ValueError | Conflicting entity/system name or registration |
| NotAComponentError | TypeError | An API expecting component data receives an invalid value |
| SerializationError | Exception through SimWorldError | Unsupported data or failed reconstruction |

UnknownNameError formats known names and up to three close matches. Subclasses
such as UnknownComponentError set a `kind` class attribute to change the wording.
Their short definitions reuse the base class's formatting behavior. Unknown
scheduler stages currently use UnknownSystemError with kind set to `"stage"`.
Some future subsystem errors are already defined; their existence does not imply
those subsystems are available. Ordinary TypeError, ValueError, RuntimeError, and
NotImplementedError are also used where appropriate.

When an entity is missing, first check is_alive. If it is alive, inspect
components_of and name_of. A reserved entity can be alive with no components;
check whether commands have been applied. If the id is stale, compare its index
and generation with a newly allocated id rather than treating the integer as a
permanent slot number.

When a system does not run, check that it is actually registered, that its enabled
flag is true, and that the current tick satisfies every. Inspect
`[definition.name for definition in world.scheduler.ordered()]` for order. If
ordering appears unchanged after a direct metadata edit, invalidate the cache.
If a component exists but a query excludes it, check all required types and the
without argument, then consider when the query snapshot was created.

## Testing and extending the engine

Run the existing suite from the repository root:

```bash
.venv/bin/python -m pytest tests -o addopts='' -q
```

Use a focused file when changing one subsystem:

```bash
.venv/bin/python -m pytest tests/test_commands.py -o addopts='' -q
```

| Test file | Contracts to read before changing related code |
| --- | --- |
| [test_ecs.py](../tests/test_ecs.py) | Error behavior, allocation, stale ids, undo, allocator serialization |
| [test_registry.py](../tests/test_registry.py) | Ordered registration, duplicates, lookup and removal |
| [test_components.py](../tests/test_components.py) | Component reflection, factories, redefinition and serialization |
| [test_layers.py](../tests/test_layers.py) | Scalar/vector allocation, dtype/defaults, coordinate access, bounded arithmetic, reductions, raw indexing and missing layer lookups |
| [test_core_components.py](../tests/test_core_components.py) | Built-in component defaults and metadata |
| [test_world.py](../tests/test_world.py) | Construction, lifecycle, ownership, queries and naming |
| [test_prefabs.py](../tests/test_prefabs.py) | Validation, copies and override semantics |
| [test_systems.py](../tests/test_systems.py) | Registration context, ordering, cache, gating and profiling |
| [test_commands.py](../tests/test_commands.py) | Reservations, ordered mutation, callback rounds and bounds, stale skips, strict mode and exception propagation |
| [test_run.py](../tests/test_run.py) | Bound registration, World clock/run loops, callbacks, temporary dt, command visibility and profiling |
| [test_readme.py](../tests/test_readme.py) | Marked runnable examples in the root README |

The clean_components fixture in [conftest.py](../tests/conftest.py) snapshots
COMPONENTS and restores registrations after a requesting test. Use it for tests
that register custom components, including tests that intentionally raise. World
instances alone do not isolate this process-global registry.

The README test runner covers the root README, not this guide. The guide's Python
examples are designed to run independently; validate them in separate processes
when editing examples so component registrations cannot contaminate other blocks.

### A practical extension workflow

For a new kind of data, define a component with a small set of fields and choose
factory defaults for mutable values. Check metadata through COMPONENTS if tools
will consume it. Add serialization coverage when the data needs to be encoded.

For behavior, write a function accepting World, query the required components,
and use world.rng for random choices. Choose a stage and order explicitly where
ordering matters. Register the function and verify it through the scheduler;
calling the function directly does not test registration or execution gates.

For structural mutation during behavior, queue commands and let the scheduler
apply them after the system returns. Test the state before and after application,
especially when later commands refer to a reserved entity. When calling a system
function directly outside the scheduler, apply commands explicitly.

For engine changes, follow the [plan execution rules](../plans/README.md): select
the next step, read its blueprint contract, write a meaningful failing test,
implement the scoped change, run relevant checks, and record evidence. Preserve
id encoding, component names/data formats, query ordering, and stage ordering
unless a deliberate contract change is requested. Do not advance a plan checkbox
just because related documentation has been written.

### Packaging files

[pyproject.toml](../pyproject.toml) declares the build backend, package metadata,
Python requirement, dependencies, optional extras, package list, entry point, and
pytest configuration. It uses TOML syntax. The currently declared editor entry
point points to a future module and cannot launch yet.

`simworld.egg-info/` contains generated installation metadata such as PKG-INFO.
Make package metadata changes in pyproject.toml rather than editing generated
files. [requirements-dev.txt](../requirements-dev.txt) records installed development
versions; it does not lock the Python interpreter or every isolated-build dependency.

## Python patterns used in this code

These patterns recur across the implementation. Understanding them makes the
engine easier to read without memorizing individual methods.

| Pattern | Meaning in this project |
| --- | --- |
| `import dataclasses as dc` | dc is a short alias for the standard dataclasses module |
| `@dc.dataclass` | Transform a class declaration into a class with generated data-oriented methods |
| `dc.field(...)` | Create a field configuration object; `dc.Field` is its type |
| `dc.MISSING` | Sentinel meaning no default or factory was supplied; distinct from an explicit None |
| `dc.field(default_factory=dict)` | Create a separate dictionary for each instance |
| `dc.replace(definition, **overrides)` | Create a shallow dataclass copy with selected fields changed |
| `t.TypeVar("T")` | A type-checking placeholder connecting a generic registry's stored and returned types |
| `t.Any` | A value whose static type is unconstrained |
| `from __future__ import annotations` | Postpone annotation evaluation, allowing forward references |
| `if t.TYPE_CHECKING:` | Imports visible to type checkers but skipped during normal runtime |
| `*components` in a parameter list | Collect positional arguments into a tuple |
| Bare `*` in a parameter list | Require later parameters to be supplied by keyword |
| `**overrides` | Collect extra keyword arguments into a dictionary |
| `*values` or `**mapping` in a call | Unpack positional values or keyword arguments |
| `@contextmanager` with yield/finally | Implement a with-block's setup and guaranteed cleanup |

A dictionary assigned at class scope, such as `a = {}`, is a class attribute and
is shared through instances unless shadowed. `self.a = {}` inside __init__ creates
an instance attribute. A dataclass default factory produces a new value during
each generated initialization; direct mutable list/dict defaults are rejected by
dataclasses.

`self._stores.setdefault(name, {})[entity] = comp` means: obtain the dictionary
already stored under name, or insert an empty one if absent, then assign comp
under the entity id in that dictionary.

Set subtraction, as in `settings.keys() - valid`, means keys that appear on the
left but not on the right. The constructor uses it to find unrecognized options.
The expression `_ACTIVE[-1] if _ACTIVE else None` returns the last active world
when the stack is nonempty and otherwise returns None.

`@system` and `@component` are functions applied to definitions. Their nested
`decorate` functions support both bare usage and usage with options. They return
a function or class for Python to bind to the original name; registration is an
additional effect of applying the decorator.

## Current implementation boundary

The implementation contains the ECS foundations and layer allocation, cell access and arithmetic through Step 029. The following
boundaries are part of the current API behavior:

| Area | Current state | Planned work |
| --- | --- | --- |
| Command errors | Stale operations are skipped and counted by default; strict mode raises; other errors propagate | Implemented in Step 024 |
| Scheduler integration | World stepping/running, per-system and stage-boundary command flushing, clock advancement | Implemented in Step 025; event dispatch remains Phase 3 |
| ECS milestone | Phase 1 gate passed; contracts documented | Step 026 complete; Phase 2 starts at Step 027 |
| Layers | Standalone allocation, coordinate access, bounded arithmetic, bulk limits and summaries | Steps 027–029 complete; sampling is Step 030 and World integration is Step 034 |
| Terrain, spatial queries, rendering | Not implemented | Later Phase 2 steps |
| Events, actions, brains | Not implemented | Phase 3 |
| Simulation modules and pathfinding | Not implemented; nonempty modules rejected | Phase 4 |
| Full world persistence, plugins, configuration loading | Not implemented; component and allocator conversion already exist | Phase 5 |
| Editor and GUI | Package placeholders only | Later editor phases |

For exact remaining tasks, use [Phase 2](../plans/02-grid.md) and the
[plan index](../plans/README.md). [BLUEPRINT.md](../BLUEPRINT.md) describes the
intended complete engine; [progress.md](../plans/progress.md) records what has
actually been implemented and checked in this repository.
