# Phase 8: Scenes, projects, viewport, inspector and editor session

Steps **143–168** (26 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§6.8–6.12, 7.2–7.5, 8 Phase 8, 9.1.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** A complete edit/save/play/stop workflow runs through EditorSession tests, including the reproducible demo project.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 143 — Define scene envelopes and migrations

- [ ] **Change:** Add scene constants, new_world, scene_to_dict and migrate_scene, including plain-world wrapping and version rejection.
- **Verify:** New worlds have documented built-ins/land; malformed/newer formats fail; only explicit migrations advance older versions.
- **Blueprint:** §§6.8, 7.2.

### Step 144 — Restore scenes with schemas and plugin locations

- [ ] **Change:** Implement scene_from_dict/load_scene registering schemas first and resolving explicit plus scene-relative plugin dirs.
- **Verify:** User/plugin component data loads before inspection; system orders are reapplied; only overrides away from base_order are saved.
- **Blueprint:** §§6.8, 7.2.

### Step 145 — Support external compressed layer sidecars

- [ ] **Change:** Add embedded/sidecar array handling with stable layer keys and stale-sidecar cleanup.
- **Verify:** Both modes restore identical fingerprints/dtypes/order; missing files/keys and shape mismatches report SceneError; embedded resave removes stale sidecars.
- **Blueprint:** §§6.8, 7.2.

### Step 146 — Write scenes atomically and with gzip

- [ ] **Change:** Finish save_scene temporary-write/replace behavior, UTF-8 gzip and error conversion.
- **Verify:** Successful writes reload; failed writes do not replace the existing scene; plugin dirs are stored relative to the scene location.
- **Blueprint:** §§6.8, 7.2.

### Step 147 — Track recent scene paths

- [ ] **Change:** Add RecentFiles limits, newest-first uniqueness, existing-path filtering and tolerant user-config I/O.
- **Verify:** Tests use temporary config roots; unreadable/unwritable recents do not break scene operations; no real user settings are changed by tests.
- **Blueprint:** §§6.8, 7.4.

### Step 148 — Create and open project folders

- [ ] **Change:** Implement ProjectManager metadata, version checks, four directories, scene names/main scene and refusal to overwrite projects.
- **Verify:** Invalid path-like scene names fail; new/open roundtrips metadata; newer project versions produce explicit errors.
- **Blueprint:** §§6.9, 7.4.

### Step 149 — Persist project prefab files

- [ ] **Change:** Add prefab names/read/save/delete/load with component validation and scene-first precedence.
- **Verify:** Invalid prefab files fail clearly; project templates fill only absent scene names; prefab captures and mutable dictionaries remain independent.
- **Blueprint:** §§6.9, 7.4.

### Step 150 — Manage project schemas and plugin files

- [ ] **Change:** Add ordered schema/scene/prefab loading, plugin discovery/mtime tracking/reload and new-file template creation.
- **Verify:** Schemas/plugins exist before prefab validation; mtime inequality detects changes; templates never overwrite; same-size updated plugin source reloads.
- **Blueprint:** §6.9.

### Step 151 — Implement camera coordinate math

- [ ] **Change:** Add Camera transforms, pan, fit, resize, visible_rect and cursor-anchored zoom limits.
- **Verify:** World/screen roundtrips preserve y-down axes; zoom keeps the cursor world point fixed; tiny and rectangular views behave correctly.
- **Blueprint:** §6.10.

### Step 152 — Pick and drag entities in the viewport

- [ ] **Change:** Add Viewport cell/entity/rectangle picking and mergeable drag commands with grab offsets and position clamps.
- **Verify:** Nearest visible hit wins; moved entities are pickable after index sync; box results sort by id; drag undo returns exact state.
- **Blueprint:** §6.10.

### Step 153 — Render terrain and entities into the viewport

- [ ] **Change:** Add ViewportSettings, per-cell terrain composition/gather, background, grids, disk markers and selection ring.
- **Verify:** Render is uint8 RGBA with correct dimensions/alpha; undefined terrain is purple; tiny/empty views and zoom thresholds work.
- **Blueprint:** §6.10.

### Step 154 — Render scalar and vector overlays

- [ ] **Change:** Add Overlay, ramp LUTs and normalized scalar/vector-magnitude blending.
- **Verify:** Four ramps, explicit/automatic limits and opacity produce expected cells; outside pixels remain background and entity selection remains visible.
- **Blueprint:** §6.10.

### Step 155 — Build the entity inspector model

- [ ] **Change:** Add FieldWidget/ComponentPanel/EntityInspector, inspect_entity and entity_choices.
- **Verify:** Every registered component is inspectable; category sorting/defaults/choices are correct; runtime fields stay hidden; edits return validated commands.
- **Blueprint:** §6.11.

### Step 156 — Build world and prefab panel models

- [ ] **Change:** Add world_panel/prefab_panel and row command factories for layers, terrain, resources, settings, modules, systems and prefabs.
- **Verify:** Rows report actual execution order and omit terrain from ordinary layers; commands roundtrip; system reads/writes remain descriptive.
- **Blueprint:** §6.11.

### Step 157 — Introduce session state and notifications

- [ ] **Change:** Add EditorSession ownership, mode constants, subscriptions, dirty tokens/title and execute/run/transaction/undo/redo facades.
- **Verify:** Failed run logs instead of raising; direct execute raises; undo to the saved token clears dirty; topics and post-change invalidation are correct.
- **Blueprint:** §6.12.

### Step 158 — Manage selection through the session

- [ ] **Change:** Add select/toggle/clear/primary, additive behavior and dead-selection pruning.
- **Verify:** Selection ordering is deterministic; primary is last selected; entity deletion prunes selection and emits documented notifications.
- **Blueprint:** §6.12.

### Step 159 — Expose entity and world editing workflows

- [ ] **Change:** Add session create/delete/duplicate/rename/reparent/component/field, prefab and world-setting/module/system/terrain wrappers.
- **Verify:** Each facade uses existing commands, respects edit guard and produces expected history grouping; defaults place new entities at view center.
- **Blueprint:** §6.12.

### Step 160 — Paint continuous strokes through the session

- [ ] **Change:** Add active layer/terrain/tool/brush, begin/paint/end stroke and fill_region with half-cell interpolation and dab cap.
- **Verify:** Fast moves leave no gaps; one stroke is one undo; next stroke stays separate; invalid terrain/layer selections fail clearly.
- **Blueprint:** §6.12.

### Step 161 — Route viewport pointer interactions

- [ ] **Change:** Implement pointer_down/move/up for selection, shift toggles, drag, paint and prefab spawn.
- **Verify:** Empty clicks clear appropriately; drag preserves offset; spawn requires active prefab/inside world; paint/spawn cannot mutate play state.
- **Blueprint:** §6.12.

### Step 162 — Restore edit state after play and pause

- [ ] **Change:** Implement play/pause/stop/step_once around WorldSnapshot, ending active gestures before capture.
- **Verify:** Stop restores fingerprint, store order and RNG; edits while play/paused reject; undo history survives; step from edit enters paused play.
- **Blueprint:** §6.12.

### Step 163 — Advance simulation at bounded rates

- [ ] **Change:** Add speeds, accumulator, maximum-20-steps catchup with dropped excess and error-to-paused logging.
- **Verify:** advance(1.0) at normal speed runs at most 20 ticks; exceptions pause with trace context; unsupported speeds reject; repeated play/stop is exact.
- **Blueprint:** §6.12.

### Step 164 — Open and save scenes through the session

- [ ] **Change:** Add editor_meta/_apply_meta/_adopt/new_scene/open_scene/save_scene with camera/brush/overlay state and clean tokens.
- **Verify:** Save/open preserves intended state and clears history/selection appropriately; failed open logs/re-raises; scene I/O respects mode rules.
- **Blueprint:** §§6.8, 6.12.

### Step 165 — Open and save complete projects

- [ ] **Change:** Add session new_project/open_project, main-scene selection, schema persistence and save_prefab_to_project.
- **Verify:** Project schemas precede component use; first save sets main_scene; scene prefab precedence survives session operations.
- **Blueprint:** §§6.9, 6.12.

### Step 166 — Edit schemas and reload plugins through the session

- [ ] **Change:** Add schema commands, edit-only reload/changed-reload and class-change history clearing with warning.
- **Verify:** Successful reload keeps entities; failures retain old code and log; paused-play reload is forbidden; reload is never represented as undoable.
- **Blueprint:** §6.12.

### Step 167 — Generate the canonical editor demo project

- [ ] **Change:** Add build_demo_project.py using editor APIs, Territory schema, toxin plugin, three prefabs and 96x64 seed-seven scene with 62 positioned entities.
- **Verify:** Project opens cleanly; expected 55 Territory/5 Toxin populations and prefab names exist; play/stop restores exact state after regeneration.
- **Blueprint:** §§7.2, 7.4–7.5, 13.2.

### Step 168 — Verify the headless workflow milestone

- [ ] **Change:** Run full suite plus a session-only open/select/edit/paint/undo/save/play/stop scenario and demo tests.
- **Verify:** Scene/project/schema/prefab versions match §7; held layer references and cached paths restore; no workflow requires DPG.
- **Blueprint:** §8 Phase 8.

Next phase: [Dear PyGui front-end and real-input verification](09-gui.md).
