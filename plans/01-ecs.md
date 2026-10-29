# Phase 1: Errors, registries, ECS and scheduling

Steps **008–026** (19 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§3.4, 5.0–5.4, 5.7–5.8, 5.21, 9.1–9.2.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Entity lifecycle, deterministic queries, deferred commands and scheduler contracts pass the complete accumulated suite.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 008 — Build actionable engine errors

- [ ] **Change:** Add errors.py with the documented inheritance tree and unknown-name suggestions; cover representative error text in test_ecs.py.
- **Verify:** Unknown names list known values and close matches; stale, duplicate and missing-component errors retain their built-in exception ancestry.
- **Blueprint:** §5.1.

### Step 009 — Implement the generic name registry

- [ ] **Change:** Add Registry registration, replacement, removal, lookup and ordered names/items access in registry.py.
- **Verify:** Duplicate rejection, explicit replacement and specialized unknown-name errors pass focused tests.
- **Blueprint:** §5.2.

### Step 010 — Describe and register data components

- [ ] **Change:** Implement prop, FieldInfo, ComponentInfo and @component, including slotted dataclasses and module/qualname duplicate rules; activate clean_components.
- **Verify:** Metadata/default factories survive; reload of the same logical class succeeds; a different class using its name fails without leaking registry state.
- **Blueprint:** §§5.2, 9.2.

### Step 011 — Serialize one component at a time

- [ ] **Change:** Add component_name, component_to_dict and component_from_dict with registered-name validation and JSON conversion.
- **Verify:** Tuple defaults, NumPy scalars, omitted nonserialized fields, unknown fields and unsupported objects match the specified success/error behavior.
- **Blueprint:** §5.2.

### Step 012 — Add the three core data components

- [ ] **Change:** Define Position, Appearance and Parent in components.py with their documented metadata.
- **Verify:** Registry inspection exposes color/entity widgets and defaults; Position accepts numeric inputs without forcing a single Python numeric type.
- **Blueprint:** §5.4.

### Step 013 — Allocate generation-safe entity ids

- [ ] **Change:** Implement EntityAllocator allocation, release, liveness checks and precise stale-id diagnostics.
- **Verify:** Id zero is invalid; generations start at one; LIFO slot reuse bumps generation; invalid inputs are rejected safely.
- **Blueprint:** §5.3.

### Step 014 — Make allocation reversible and serializable

- [ ] **Change:** Add revive, rollback_alloc and allocator to_dict/from_dict; keep undo strictly LIFO.
- **Verify:** Fresh and recycled allocations undo exactly; allocator roundtrips preserve generations, free-list order and stale ids.
- **Blueprint:** §5.3.

### Step 015 — Introduce minimal World state

- [ ] **Change:** Add WorldSettings, seeded rng, clock/resources, allocator and ordered component stores in world.py, without importing future subsystems.
- **Verify:** Defaults match §5.7; unknown settings fail clearly; same-seed generators produce the same sequence and mutable defaults are independent.
- **Blueprint:** §5.7.

### Step 016 — Implement entity creation and deletion

- [ ] **Change:** Add spawn/despawn and component-store cleanup; validate duplicate components and names before allocating.
- **Verify:** Failed spawn consumes no id; deletion cleans every store and name map; stale deletion raises.
- **Blueprint:** §5.7.

### Step 017 — Implement component access and mutation

- [ ] **Change:** Add add/remove/get/try_get/has/components_of through registered component names or classes.
- **Verify:** Missing versus stale errors are distinct; try_get returns None and has returns False for dead entities.
- **Blueprint:** §5.7.

### Step 018 — Implement deterministic queries and counts

- [ ] **Change:** Add smallest-store query snapshots, exclusions, entity listing and count.
- **Verify:** Tuple argument order is preserved; smallest-store insertion order drives iteration; removing entities during iteration is safe; query without components fails.
- **Blueprint:** §5.7.

### Step 019 — Implement entity naming

- [ ] **Change:** Add set_name/entity/name_of with both name maps and uniqueness checks.
- **Verify:** Rename, removal, duplicate-name failure and lookup keep both maps consistent and leave failed edits unchanged.
- **Blueprint:** §5.7.

### Step 020 — Implement prefab templates and overrides

- [ ] **Change:** Add define_prefab/spawn_prefab with deep copies, nested/dotted overrides, component replacements and None removal.
- **Verify:** Invalid definitions fail immediately; sibling spawns share no mutable values; missing prefabs give helpful errors.
- **Blueprint:** §5.7.

### Step 021 — Define systems and registration context

- [ ] **Change:** Add loading_into/active_world, SystemDef and @system metadata with a World registration surface for systems.
- **Verify:** Decorators register into an active world only; nested contexts unwind on errors; outside a context explicit registration is required.
- **Blueprint:** §§5.2, 5.8.

### Step 022 — Schedule systems in stable stages

- [ ] **Change:** Implement Scheduler stage management, ordered caching, enable flags, every-N gating and profiling.
- **Verify:** Default stages and (order, registration sequence) ties are exact; edited membership/order invalidates the cache; reads/writes stay descriptive.
- **Blueprint:** §§3.4, 5.8.

### Step 023 — Defer structural entity commands

- [ ] **Change:** Implement CommandBuffer spawn/prefab reservation, despawn/add/remove/defer and queue-ordered apply rounds.
- **Verify:** Reserved ids are alive but absent from component queries until applied; subsequent queued operations can target them; recursive defers are bounded.
- **Blueprint:** §5.3.

### Step 024 — Handle stale queued targets

- [ ] **Change:** Add skipped accounting and strict mode; cover repeated despawns and operations queued by applied operations.
- **Verify:** Default mode skips and counts stale targets; strict mode raises; non-stale exceptions propagate without being mislabeled.
- **Blueprint:** §5.3.

### Step 025 — Connect scheduled steps and run loops

- [ ] **Change:** Wire World system decorators/register/enable APIs, step/run and per-system command flushing; leave event-stage dispatch for Phase 3.
- **Verify:** Systems see prior-system structural edits; tick/time advance once; dt overrides are temporary; callback False stops run.
- **Blueprint:** §§3.4, 5.7–5.8.

### Step 026 — Verify the ECS milestone

- [ ] **Change:** Run test_ecs.py, test_commands.py and the complete suite; document the frozen ids, component data format and stage order.
- **Verify:** All accumulated tests pass; no layers/actions/editor code is required; later service integration points are documented.
- **Blueprint:** §8 Phase 1.

Next phase: [Layers, terrain, spatial queries and headless rendering](02-grid.md).
