# Phase 7: Headless editor commands, exact undo, schemas and snapshots

Steps **111–142** (32 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§6.1–6.4, 6.6–6.7, 6.13, 9.2.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Every editor command roundtrips exact fingerprints and store order; snapshots restore in place; no headless editor module imports DPG.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 111 — Define editor errors and widget descriptions

- [ ] **Change:** Add editor/errors.py and fields.py type normalization, widget-kind mapping, precedence and custom registration.
- **Verify:** Explicit widget metadata beats choices and types; unknown types fall back to JSON; headless imports require no DPG.
- **Blueprint:** §§6.1–6.2.

### Step 112 — Validate editable field values

- [ ] **Change:** Implement coerce_value for finite numeric, bool, text, tuple/vector/color, entity, choice, list and JSON values.
- **Verify:** Bad lengths/types/bounds reject before mutation; clamp preserves requested types; booleans are not accepted as floats.
- **Blueprint:** §6.2.

### Step 113 — Fingerprint full world state

- [ ] **Change:** Implement world_fingerprint in editor/state.py including arrays, allocator, metadata, resources, RNG and flags.
- **Verify:** Equivalent state compares canonically regardless of dictionary ordering; a layer-byte/RNG/setting change is detected; runtime Brain.policy is excluded.
- **Blueprint:** §6.6.

### Step 114 — Build exact-state editor test helpers

- [ ] **Change:** Add store_order and tests/editor_helpers.py state/roundtrip plus the small demo builder before implementing commands.
- **Verify:** Tests distinguish equal fingerprints with different store order; roundtrip checks changed do, exact undo, identical redo and second undo.
- **Blueprint:** §§6.6, 9.2.

### Step 115 — Introduce the basic command stack

- [ ] **Change:** Define Command and CommandStack execute/undo/redo, labels, history limit and redo invalidation.
- **Verify:** A tiny test command proves LIFO and repeatable redo; no-op commands do not enter history; failure does not create a successful history entry.
- **Blueprint:** §6.3.

### Step 116 — Merge edits and track clean-state tokens

- [ ] **Change:** Add merge_key/type gating, seal, revision and versioned top-command tokens.
- **Verify:** A merged slider edit stays one undo but changes the token; undo back to a saved token is clean; sealed interactions stay separate.
- **Blueprint:** §6.3.

### Step 117 — Compose commands and roll back transactions

- [ ] **Change:** Implement Composite and nested transaction grouping with reverse rollback on failure.
- **Verify:** Partial composite failure restores state/order; nested groups become one undo; failed groups leave prior history intact.
- **Blueprint:** §6.3.

### Step 118 — Prepare exact lifecycle restoration helpers

- [ ] **Change:** Add _insert_at/_pop_with_index and component put/take helpers preserving Position indexing.
- **Verify:** Removing/reinserting middle-store entries restores order and instance identity; spatial results agree before/after helper operations.
- **Blueprint:** §6.3.

### Step 119 — Create entities undoably

- [ ] **Change:** Implement CreateEntity for instances/mappings and exact allocator rollback on undo.
- **Verify:** Fresh/recycled ids, names and mutable templates roundtrip; invalid tuple-list specs reject; next spawn receives the correct id after undo.
- **Blueprint:** §6.3.

### Step 120 — Delete entities undoably

- [ ] **Change:** Implement DeleteEntity capturing component instances, individual store positions and names.
- **Verify:** Deleting a middle entity then undo restores exact fingerprint, store order, id generation and nearby results.
- **Blueprint:** §6.3.

### Step 121 — Duplicate and rename entities

- [ ] **Change:** Implement DuplicateEntity offsets/unique names and mergeable RenameEntity.
- **Verify:** Duplicate mutable components are independent; names gain deterministic suffixes; duplicate failures and rename no-ops leave state unchanged.
- **Blueprint:** §6.3.

### Step 122 — Model hierarchy relationships

- [ ] **Change:** Add hierarchy.py display names, root/parent/child maps, traversals, filtering, cycle detection and unique_name.
- **Verify:** Dead/self parents appear as roots; malformed cycles terminate; children follow entity-index order; filters return documented tree behavior.
- **Blueprint:** §6.4.

### Step 123 — Reparent and delete hierarchy branches

- [ ] **Change:** Add ReparentEntity and delete_entity_command for recursive deletion or reparenting children to the grandparent.
- **Verify:** Cycles/dead parents reject; both delete modes undo exactly across Parent store positions; each operation is a single history entry.
- **Blueprint:** §§6.3–6.4.

### Step 124 — Add and remove entity components

- [ ] **Change:** Implement AddComponent/RemoveComponent validation and exact instance/store-position restoration.
- **Verify:** Missing/already-present errors are atomic; Position edits synchronize spatial state; component removal/undo restores the same instance.
- **Blueprint:** §6.3.

### Step 125 — Edit component fields undoably

- [ ] **Change:** Implement SetFields/SetField construction-time coercion, deep copies, no-op/merge and Position synchronization.
- **Verify:** Multi-field failure is atomic; merged edits retain oldest old/latest new; Brain policy-cache limitation remains explicitly documented.
- **Blueprint:** §6.3, G16.

### Step 126 — Define brushes and clipped cell footprints

- [ ] **Change:** Add Brush validation and brush_cells circle/square center-based inclusion.
- **Verify:** Radius bounds, world clipping, cell-containing-center and circle versus square masks pass asymmetric-grid cases.
- **Blueprint:** §6.3.

### Step 127 — Paint layers with reversible sparse diffs

- [ ] **Change:** Implement PaintLayer changed-cell storage, modes, dtype rounding/clipping and stroke-id merging.
- **Verify:** Overlapping dabs keep oldest old/latest new values; a stroke is one exact undo; terrain names resolve and edits invalidate paths.
- **Blueprint:** §6.3.

### Step 128 — Fill regions and define layers

- [ ] **Change:** Add FillLayerRegion and DefineLayer/field with exact undo metadata/data handling.
- **Verify:** Rectangles use half-open clipped bounds; empty fills are no-ops; field creation validates prerequisites and undoes cleanly.
- **Blueprint:** §6.3.

### Step 129 — Edit layer properties

- [ ] **Change:** Implement SetLayerProperty including dotted props, numeric/color validation and merging.
- **Verify:** Invalid property edits leave state unchanged; each supported property roundtrips; changed min/max metadata follows the specified behavior.
- **Blueprint:** §6.3.

### Step 130 — Define and edit terrains undoably

- [ ] **Change:** Add DefineTerrain/EditTerrain with prior-definition restoration and creation-time terrain-layer cleanup.
- **Verify:** Define/redefine/undo restores LUTs, properties and layer presence; passability/cost changes invalidate path caches immediately.
- **Blueprint:** §6.3.

### Step 131 — Edit world settings and user resources

- [ ] **Change:** Add SetWorldSetting/SetResourceValue with protected names, reseeding and spatial rebuild behavior.
- **Verify:** Undo restores prior RNG state, dt resource and cell_size index; dimensions/protected resources reject; extra values roundtrip.
- **Blueprint:** §6.3.

### Step 132 — Control modules and the execution schedule

- [ ] **Change:** Add SetModuleEnabled/SetSystemEnabled/SetSystemOrder including cache invalidation and no-op handling.
- **Verify:** Changed order changes actual execution; undo restores it; module toggles gate systems, handlers and actions consistently.
- **Blueprint:** §6.3, G13.

### Step 133 — Edit and spawn prefabs

- [ ] **Change:** Add DefinePrefab/DefinePrefabFromEntity/DeletePrefab/SpawnPrefab through existing lifecycle helpers.
- **Verify:** Captured prefabs omit Parent; invalid specs are atomic; positioned spawns and overrides preserve exact allocator state on undo.
- **Blueprint:** §6.3.

### Step 134 — Validate user-authored schemas

- [ ] **Change:** Add FieldSchema/ComponentSchema parsing, identifier/type/default/range/choice rules and format/version handling.
- **Verify:** All eight field types and unknown-key/name collisions are exercised; schema JSON roundtrips; invalid defaults fail clearly.
- **Blueprint:** §§6.7, 7.5.

### Step 135 — Build and persist generated component classes

- [ ] **Change:** Add SchemaStore class construction/registration, ownership checks, version changes, directory/list load/save and stale-file cleanup.
- **Verify:** Real slotted components use simworld_user_components; identical definitions keep versions; changed definitions bump; Python-owned names cannot be replaced.
- **Blueprint:** §6.7.

### Step 136 — Undo schema definition and removal

- [ ] **Change:** Add DefineComponentSchema/RemoveComponentSchema with shared-valid-field migration and registry/class/instance restoration.
- **Verify:** Existing instances gain defaults or retain valid values; undo restores exact previous classes/data/order; global registry fixture prevents cross-test leaks.
- **Blueprint:** §6.7.

### Step 137 — Capture complete play snapshots

- [ ] **Change:** Implement WorldSnapshot.capture with copied stores, allocator, layer state, settings/resources/RNG, flags and action counters.
- **Verify:** Capturing changes nothing; later mutations cannot alter saved values; documented uncopyable-resource references are handled explicitly.
- **Blueprint:** §6.6.

### Step 138 — Restore snapshots into existing worlds

- [ ] **Change:** Implement restore preserving live store/layer/compatible ndarray identities, restoring queues/counters and rebuilding spatial/path state.
- **Verify:** Simulation-created entities/layers/resources disappear; fingerprint/store order/RNG match capture; retained layer references still observe restored data.
- **Blueprint:** §6.6.

### Step 139 — Provide bounded structured editor logs

- [ ] **Change:** Add LogEntry/LogModel levels, formatting, filters, subscribers, error count and plugin errors.
- **Verify:** Four documented behavior groups pass; limit truncates oldest entries; invalid levels fail; no GUI or wall-clock values enter world state.
- **Blueprint:** §6.13.

### Step 140 — Expose the headless editor API

- [ ] **Change:** Export implemented commands/models/helpers from editor/__init__.py without loading future front-end modules.
- **Verify:** Headless imports succeed without DPG/pygame; exported command names match the blueprint; future APIs are added only when implemented.
- **Blueprint:** §§2.3, 6.

### Step 141 — Audit command coverage and failure atomicity

- [ ] **Change:** Cross-check every concrete entity/world/schema command against roundtrip, merge, no-op and failure tests; close uncovered cases.
- **Verify:** Each command has relevant exact-state coverage; snapshot restore also handles terrain changes and cached paths; intentional Brain cache limitation is listed.
- **Blueprint:** §§6.3, 6.6, 9.1–9.2.

### Step 142 — Verify the editor-core milestone

- [ ] **Change:** Run the complete accumulated suite and inspect headless import boundaries; record command coverage and any deviations.
- **Verify:** Exact undo/redo and snapshot checks pass; no editor operation needs a display; no untested commands are reported as finished.
- **Blueprint:** §8 Phase 7.

Next phase: [Scenes, projects, viewport, inspector and editor session](08-editor-workflows.md).
