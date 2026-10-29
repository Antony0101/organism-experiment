# Phase 4: Built-in modules and pathfinding

Steps **062–081** (20 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§5.12, 5.15, 8 Phase 4, 9.1, 13.2.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** All built-ins and GoTo are implemented; A* agrees with an independent shortest-path oracle; the demo runs 1000 steps.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 062 — Define extension modules

- [ ] **Change:** Add Module, FunctionModule, ModuleState, MODULES, @module and resolve_module in modules/base.py.
- **Verify:** Names/classes/instances resolve; function setup receives options; unknown modules produce helpful errors.
- **Blueprint:** §5.12.

### Step 063 — Load modules into individual worlds

- [ ] **Change:** Implement World.use, requires resolution, ownership, enable/options APIs and failure cleanup.
- **Verify:** Dependencies load before setup; repeat use ignores new options; setup failure removes its ModuleState; disabling gates owned systems/handlers/actions.
- **Blueprint:** §§5.7, 5.12.

### Step 064 — Provide terrain and movement modules

- [ ] **Change:** Add built-in terrain setup and movement.Mover with declared dependencies and field metadata.
- **Verify:** Both modules are idempotent; Mover speed and energy_per_unit integrate with existing movement without becoming core requirements.
- **Blueprint:** §5.12.

### Step 065 — Update fields with the resources module

- [ ] **Change:** Add update_fields in decay/regrow/diffuse/clamp order and stable diffusion substeps.
- **Verify:** Fertility-based regrowth, regrow prerequisites, masks and large dt match formulas and conserve mass where applicable.
- **Blueprint:** §5.12.

### Step 066 — Add metabolic energy and food conversion

- [ ] **Change:** Define Energy/Metabolism, basal_burn and eat_consumed.
- **Verify:** Diet uses actual consumed quantity; max energy clamps; starvation emits died then removes the entity through commands.
- **Blueprint:** §5.12.

### Step 067 — Apply attack effects through metabolism

- [ ] **Change:** Add attacked handling for damage, steal and killed death causes.
- **Verify:** Range failures cause no effects; successful attacks update both energies, respect max and avoid repeated death events.
- **Blueprint:** §§5.10, 5.12.

### Step 068 — Add age-based mortality

- [ ] **Change:** Define Age and the ageing update system with immortal lifespan zero.
- **Verify:** Age advances by dt; lifespan deaths carry old_age; disabled ageing freezes its effects.
- **Blueprint:** §5.12.

### Step 069 — Define reproductive state and eligibility

- [ ] **Change:** Add Reproduction/Genome, timers, threshold/cooldown checks, action cost and pending-population accounting.
- **Verify:** Eligibility and affordability are distinct; simultaneous deferred offspring cannot exceed max_population; disabled module rejects actions.
- **Blueprint:** §5.12.

### Step 070 — Create and mutate offspring

- [ ] **Change:** Implement reproduction handler, deep-copy inheritance, gene application/clamping, position jitter and born event.
- **Verify:** Child defaults/resets, cost plus offspring energy, passability, mutation bounds and copied stateful policies match the specification.
- **Blueprint:** §5.12, G17.

### Step 071 — Connect automatic reproduction and built-in exports

- [ ] **Change:** Add auto_reproduce and BUILTIN_MODULES order; complete the §9.2 world fixture and assert module toggling behavior.
- **Verify:** Automatic births respect cooldown/cap; all documented system names/stages are stable; fixture terrains/options match the blueprint.
- **Blueprint:** §§3.4, 5.12, 9.2.

### Step 072 — Implement the grid path cost model

- [ ] **Change:** Add Cell, PathStats, terrain_grids, path_cost and passability/cost normalization.
- **Verify:** Orthogonal/diagonal costs average endpoint terrain costs; no-terrain grids and costs below one are handled consistently.
- **Blueprint:** §5.15.

### Step 073 — Implement deterministic A-star

- [ ] **Change:** Add heap search, cheapest-cell-scaled octile heuristic, no-corner-cutting and max_nodes.
- **Verify:** Blocked goal/outside/unreachable return None; impassable start can escape; same-cell and tie behavior are deterministic.
- **Blueprint:** §5.15.

### Step 074 — Prove path optimality independently

- [ ] **Change:** Add brute-force Dijkstra comparisons on small seeded random grids and hand-built corner/cheap-terrain cases.
- **Verify:** A* cost equals the independent oracle within tolerance across diagonal modes; oracle does not reuse A* search logic.
- **Blueprint:** §§5.15, 9.1.

### Step 075 — Cache successful and failed paths

- [ ] **Change:** Implement PathFinder LRU, path suffix reuse, per-goal lookup, failed-pair bounds and stats.
- **Verify:** Repeated/suffix requests hit cache; failed requests avoid new searches; cache eviction and shared-path immutability are covered.
- **Blueprint:** §5.15.

### Step 076 — Invalidate paths after terrain changes

- [ ] **Change:** Add per-world weak service, tick/checksum synchronization and explicit invalidation hooks.
- **Verify:** API edits invalidate immediately; raw terrain writes invalidate next tick; terrain redefinition clears grids, success and failure caches.
- **Blueprint:** §5.15, G10.

### Step 077 — Implement GoTo action execution

- [ ] **Change:** Register go_to handler, next_target and World.find_path against the cached service.
- **Verify:** Entities walk around walls toward cell centers then exact goals; no-path/arrived rejections and movement energy costs are correct.
- **Blueprint:** §§5.10, 5.15.

### Step 078 — Implement stateful GoTo brains

- [ ] **Change:** Add GoToBrain arrival threshold, no-path retry timing and moving/idle/arrived/no_path states.
- **Verify:** Retry suppresses repeated searches until the target tick; no Position returns None; seeded GoTo worlds match.
- **Blueprint:** §§5.11, 5.15.

### Step 079 — Complete module introspection and ownership

- [ ] **Change:** Finish World.describe_data/describe and registration metadata across systems, events and actions.
- **Verify:** Introspection lists ordered systems, fields, counts, modules and prefabs; two worlds keep per-world registration and enable flags independent.
- **Blueprint:** §§5.7, 5.12.

### Step 080 — Build and exercise the ecosystem demo

- [ ] **Change:** Add examples/demo_water_mud.py build_world from §13.2 and a headless 1000-step exercise with population capped.
- **Verify:** Run completes; positions remain bounded, energy and fields remain finite, and core modules know no nutrient/water domain names.
- **Blueprint:** §13.2, §8 Phase 4.

### Step 081 — Verify the modules and pathfinding milestone

- [ ] **Change:** Run the complete suite including pathfinding oracle, reproduction cap and module-disable regressions; record the demo command/output.
- **Verify:** GoTo deferrals from Phase 3 are closed; names/stages and built-in order are frozen; no large-scale pathfinding performance claim is made.
- **Blueprint:** §8 Phase 4.

Next phase: [World persistence, plugins, configuration and determinism](05-persistence-plugins.md).
