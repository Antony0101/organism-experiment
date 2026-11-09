# ECS contracts for later phases

These contracts are established by Phase 1, Steps 008–026, for simworld 0.1.0.
Later work must preserve them when adding grids, events, modules, persistence and
the editor. Changes to these contracts require an explicit compatibility decision
and corresponding tests. The [developer guide](developer-guide.md) explains how
to use the APIs; this document records the boundaries future implementation must
respect. Verification evidence is in the [progress log](../plans/progress.md).

## Entity identity and lifecycle

An entity id is a Python integer encoded as `(generation << 32) | index`.
`INDEX_BITS` is 32 and `INDEX_MASK` is `(1 << 32) - 1`. Generations start at one;
zero is never a live id. The first allocation is 4294967296. Releasing and then
reallocating its slot produces 8589934592, leaving the original id stale.

Free slots are reused in last-in-first-out order. Liveness requires an allocated,
live slot whose generation matches the id. Ids belong to their world; the same
integer can identify unrelated entities in different worlds. Numeric values such
as floats and NumPy integers must not bypass the allocator's integer-id checks.

Spawn validates components and names before allocation. Despawn removes stored
components and both name mappings before releasing the slot. Empty entities are
valid and included by entities/count. Reserved command-buffer ids are also alive
before their components and names are attached.

Allocator snapshots use exactly these keys:

```json
{"generations": [1, 2], "alive": [true, false], "free": [1]}
```

Snapshot lists are independent copies, with free-list order preserved. These are
allocator snapshots, not complete world saves. Allocation undo/revive require a
caller maintaining LIFO history and restoring associated component/name state.

Evidence: [test_ecs.py](../tests/test_ecs.py),
[test_world.py](../tests/test_world.py), [test_commands.py](../tests/test_commands.py).

## Component registration and data format

COMPONENTS is process-global. Its records identify registered classes and reflected
fields; World component instances remain world-local unless callers explicitly
share objects. A class's default registered name is its Python class name. A new
class with the same module and qualified name may replace its registration;
a different logical class using the same name raises DuplicateNameError.

The component serializer returns a field dictionary with no envelope or implicit
component name. For example, serializing Appearance yields:

```json
{"color": [255, 255, 255], "size": 1}
```

Names are supplied separately when reconstructing components or defining prefabs.
Only reflected fields marked serialize=True are emitted. Supported NumPy scalars
become native values, tuple/list values become lists, and dictionary keys become
strings. Unsupported values raise SerializationError. The serializer accepts
component instances; a registered name or class is not an instance.

Reconstruction rejects unknown fields and uses constructor defaults for omitted
fields. Lists become tuples when the reflected default is a tuple. Types and
min/max metadata do not impose runtime validation. Nonserialized required fields,
init=False fields and nested objects require care; see the guide's serialization
limits. This component format does not yet define a world file format, schema
migration or version marker. Those belong to Phase 5.

The decorator must reflect newly declared fields on component subclasses, including
factory defaults, without altering the parent's metadata. An explicitly decorated
dataclass retains its own options. Frozen inheritance must still follow Python's
dataclass rules; callers can explicitly decorate the subclass with matching options.

Evidence: [test_registry.py](../tests/test_registry.py),
[test_components.py](../tests/test_components.py),
[test_core_components.py](../tests/test_core_components.py),
[test_prefabs.py](../tests/test_prefabs.py).

## Store and query ordering

Stores retain the layout `component_name -> entity_id -> instance` and dictionary
insertion order. Query results contain `(entity, component, ...)` in the requested
component order. Iteration starts from the smallest included store; equal sizes
choose the first argument. Its items are snapshotted when query is called, and
base membership is checked again before yielding. Other stores and exclusions
are read during iteration. Exclusion means having any excluded type.

The snapshot retains component references, not deep copies. Do not silently change
this into an entity-id sort, a snapshot taken at first iteration, or a full state
copy. Entity listing uses allocator slot order, which is a separate ordering.
Preserve store order when future editor commands implement exact undo.

Evidence: [test_world.py](../tests/test_world.py).

## Scheduling and commands

The default stages are fixed in this order:

```text
input -> sense -> decide -> act -> update -> late
```

Systems within each stage sort by `(order, registration sequence)`. Custom stages
can be inserted explicitly. Enable flags and every-N tick eligibility control
execution; reads/writes remain descriptive metadata. Cache invalidation is required
when membership or ordering changes. Registration makes world-owned copies of
system definitions through World.add_system.

The scheduler applies structural commands after each executed system and at each
stage boundary, including empty stages. Command callbacks enqueue their new work
for a subsequent round. Apply returns the number of successful operations;
StaleEntityError is skipped and counted cumulatively by default, or re-raised when
strict is enabled. Other errors propagate. Application is not transactional and
failed detached rounds are not replayed. Recursive queue rounds are bounded by
max_rounds, default 100.

World.step owns clock advancement: after success, tick increases by one and time
by the selected dt. Temporary dt overrides are restored even on failure. Scheduler
execution alone does not advance the clock. Run callbacks receive the world after
a completed step and literal False stops the loop. Profiling includes each
system's following command application. All simulation randomness uses world.rng;
reproducibility also requires consistent call order and compatible versions.

Evidence: [test_systems.py](../tests/test_systems.py),
[test_commands.py](../tests/test_commands.py), [test_run.py](../tests/test_run.py).

## Later service integration

| Later work | Integration point and contract to preserve |
| --- | --- |
| Phase 2 layers and terrain | Add World services while retaining current constructor validation and the ability to run a minimal World |
| Phase 2 spatial queries | Extend spawn, deferred _finish_spawn, add/remove and despawn as needed; preserve id, naming and store invariants; synchronize direct Position edits at defined points |
| Phase 3 events | Dispatch at the end of each scheduler stage immediately before its existing boundary command flush |
| Phase 3 actions and brains | Add core systems to the established stages; extend World.register to their actual metadata types when implemented |
| Phase 3 death handling | Add kill/_dying with that service and clear its per-step guard at the appropriate successful-step boundary |
| Phase 4 modules | Supply module_enabled and module origin context; preserve independent system definitions and enabled/every gates |
| Phase 5 persistence and plugins | Preserve component dictionaries, allocator generations/free order, names, store order and RNG state; introduce complete versioned world formats there |
| Editor phases | Use common World APIs and explicit LIFO history; restore stores/names as well as allocation when undoing edits |

The core currently imports neither the editor nor GUI libraries. A minimal World
can spawn, query and step without layers, actions, brains or simulation modules.
Event dispatch, the complete built-in world fixture, GUI execution and performance
benchmarks are later acceptance checks, not requirements of this ECS milestone.

## Verification environment

The milestone is checked locally with Python 3.12.3, NumPy 2.5.4 and pytest 9.2.0.
The pinned development requirements require Python 3.12 or newer because of that
NumPy pin. Package metadata declares Python >=3.10 with broader dependency ranges;
that minimum is not a claim of testing on every supported interpreter.

Run the milestone checks from the repository root:

```bash
.venv/bin/python -m pytest tests/test_ecs.py tests/test_commands.py -o addopts='' -q
.venv/bin/python -m pytest tests -o addopts='' -q
.venv/bin/python -m pip --no-cache-dir check
```

Passing these checks establishes the tested Phase 1 contracts. It does not certify
future services, GUI availability, cross-version determinism or fresh installation
on other platforms.
