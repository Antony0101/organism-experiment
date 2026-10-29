# Phase 5: World persistence, plugins, configuration and determinism

Steps **082–101** (20 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§5.13, 5.16–5.17, 5.20, 7.1, 7.6, 9.3.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** World continuation survives save/load, plugins reload with rollback, and data-driven configs reproduce seeded worlds.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 082 — Encode layer arrays for JSON

- [ ] **Change:** Add serialization.py array encoding/decoding with dtype.str, full shape, zlib level three and base64.
- **Verify:** Scalar/vector layers preserve exact bytes/dtype/shape; malformed payloads fail clearly and decoded arrays are writable copies.
- **Blueprint:** §§5.16, 7.1.

### Step 083 — Serialize a complete world dictionary

- [ ] **Change:** Implement world_to_dict with v1 keys, allocator, insertion-ordered components, metadata, modules, flags, resources and RNG state.
- **Verify:** JSON encoding succeeds; Brain.policy is absent; large PCG64 integers remain integers; nonserializable user resources are skipped as documented.
- **Blueprint:** §§5.16, 7.1.

### Step 084 — Restore a world in dependency order

- [ ] **Change:** Implement world_from_dict with settings/modules/terrain/layers before entities and direct ordered store restoration.
- **Verify:** Roundtrip preserves allocator, names, layer metadata, module/system flags, RNG and store iteration order; unknown components include plugin guidance.
- **Blueprint:** §§5.16, 7.1.

### Step 085 — Add JSON and gzip file persistence

- [ ] **Change:** Implement save_world/load_world and World delegation, parent-directory creation and UTF-8 gzip by suffix.
- **Verify:** Plain and gzip files restore equally; wrong markers/versions, shape mismatch, missing files and malformed data fail clearly.
- **Blueprint:** §5.16.

### Step 086 — Prove exact simulation continuation

- [ ] **Change:** Add build/snapshot helpers and save-at-tick-25 continuation, stale-id and callable-brain tests.
- **Verify:** Original and loaded worlds match after further steps; registered callables roundtrip; anonymous callable brains fail to save.
- **Blueprint:** §§9.2–9.3, 5.16.

### Step 087 — Expose plugin definition helpers

- [ ] **Change:** Implement plugin.py current_world and define_terrain/layer/field/prefab forwarding under loading_into.
- **Verify:** Helpers work within plugin context and raise PluginError with guidance outside it; nested context cleanup survives failure.
- **Blueprint:** §5.13.

### Step 088 — Discover and execute plugin source files

- [ ] **Change:** Add load_plugins/_exec_plugin_file with sorted files, underscore skipping, module ownership and compile-from-source execution.
- **Verify:** Toxin-style files register component/layer/system and optional setup; same-size rapid edits do not use stale pyc; invalid directories fail clearly.
- **Blueprint:** §5.13.

### Step 089 — Verify plugin isolation and failures

- [ ] **Change:** Add plugin_names, plugin_dirs tracking, descriptions and chained PluginError handling.
- **Verify:** Two worlds receive their own systems/layers; components remain global; failed initial setup removes its module state and explains the source error.
- **Blueprint:** §5.13.

### Step 090 — Reload plugin registrations transactionally

- [ ] **Change:** Back up owned systems/handlers/actions, layers, COMPONENTS and module state; replace registrations and restore on failure.
- **Verify:** A failed reload keeps prior code/registry state and usable layers; success removes obsolete owned registrations and invalidates scheduler order cache.
- **Blueprint:** §5.13.

### Step 091 — Preserve live plugin data on reload

- [ ] **Change:** Migrate replaced component classes using shared fields; preserve compatible painted arrays, enabled flags and edited system orders.
- **Verify:** Existing entities retain values, new fields receive defaults, unchanged layer data survives, and non-overridden declared order can change.
- **Blueprint:** §5.13.

### Step 092 — Make plugin loading explicit for world saves

- [ ] **Change:** Complete world_from_dict plugins parameter and skip saved plugin module entries during ordinary module restoration.
- **Verify:** Loading without explicit directories executes no plugin code; explicit directories register components before data restoration; unsupported names show the plugin hint.
- **Blueprint:** §§5.13, 5.16.

### Step 093 — Validate configuration recipes

- [ ] **Change:** Add world_from_config dict/path handling, deep copying, known keys, defaults and clear ConfigError wrapping.
- **Verify:** Input dict stays unchanged; malformed JSON, unknown keys and bad module/terrain entries fail with useful context.
- **Blueprint:** §§5.17, 7.6.

### Step 094 — Apply config definitions in fixed order

- [ ] **Change:** Build settings, modules, plugin directories, terrains, layers, fields and prefabs in the documented sequence.
- **Verify:** Plugin-provided definitions exist before use; layer fills and module options work; default modules and explicit empty modules differ correctly.
- **Blueprint:** §5.17.

### Step 095 — Apply config terrain generation

- [ ] **Change:** Add ordered fill/noise/blobs/rects initialization through existing worldgen APIs.
- **Verify:** Fixed seed gives identical terrain and next RNG state; later operations override earlier ones; rectangular coordinates use [y,x].
- **Blueprint:** §5.17.

### Step 096 — Spawn configured prefab populations

- [ ] **Change:** Add counts/areas/passable_only and position override logic; write examples/config_world.json from §7.6.
- **Verify:** Position pins are respected, generated positions stay valid, nonposition prefabs work and the complete example loads deterministically.
- **Blueprint:** §§5.17, 7.6.

### Step 097 — Freeze the public engine API

- [ ] **Change:** Complete simworld/__init__.py re-exports and __version__ from §5.20.
- **Verify:** All listed names import; every engine error is exported; Parent remains available from components without adding it to __all__.
- **Blueprint:** §5.20.

### Step 098 — Prove same-seed and different-seed behavior

- [ ] **Change:** Add test_determinism.py using the §9.3 build/snapshot scenarios and entity-id comparison.
- **Verify:** Same-seed runs match; different seeds differ; action shuffle, spatial tie sorting and store order produce repeatable outcomes.
- **Blueprint:** §9.3, G5.

### Step 099 — Exercise persistence and reload together

- [ ] **Change:** Add integration scenarios for disabled modules/systems, plugin-owned components, prefab overrides and post-reload world saves.
- **Verify:** Save/load resumes identically after supported reloads; unsupported code/class omissions produce explicit errors rather than silent component loss.
- **Blueprint:** §§5.13, 5.16, 9.1.

### Step 100 — Audit persisted v1 contracts

- [ ] **Change:** Compare emitted world/config structures against §7, document supported omissions and inspect RNG/resource JSON conversion.
- **Verify:** Exact markers/version/keys and component insertion order are recorded; truncated editorial examples are never copied as runnable fixtures.
- **Blueprint:** §§7.1, 7.6.

### Step 101 — Verify the persistence milestone

- [ ] **Change:** Run complete suite, example-config load, deterministic continuation and plugin reload/failure checks; record commands/results.
- **Verify:** All engine persistence contracts pass; default save loading executes no plugins; future format changes require deliberate version handling.
- **Blueprint:** §8 Phase 5.

Next phase: [Executable documentation, examples, viewer and benchmarks](06-engine-delivery.md).
