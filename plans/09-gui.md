# Phase 9: Dear PyGui front-end and real-input verification

Steps **169–188** (20 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§6.14–6.17, 8 Phase 9, 9.5–9.7.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** GUI helpers pass headlessly; a real-window smoke and real-input capture harness report their actual results and unverified paths.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 169 — Parse and format GUI field values

- [ ] **Change:** Add gui_model format_value/parse_text_value, color conversion and RGBA texture normalization.
- **Verify:** Sequence/JSON formats roundtrip; garbage yields ValidationError; colors use 0–255 and textures are contiguous flat float32 in 0–1.
- **Blueprint:** §§6.14, 9.5.

### Step 170 — Model layout and panel invalidation

- [ ] **Change:** Add compute_layout, DirtyFlags, bounded/filterable hierarchy_rows, clamp_int and shortcut table.
- **Verify:** Headless tests cover three documented sizes plus minimum clamp, positive in-window panels, topic mapping and unique shortcut descriptions.
- **Blueprint:** §6.14.

### Step 171 — Gate viewport frames and texture resizing

- [ ] **Change:** Add FrameGate requests, play-rate limit and stable-size settling.
- **Verify:** Static views do not redraw unnecessarily; play caps rendering; tiny resize requests are ignored; stable sizes settle after the documented interval.
- **Blueprint:** §6.14.

### Step 172 — Create the subprocess GUI smoke test

- [ ] **Change:** Add test_editor_gui_smoke.py subprocess/display infrastructure and a minimal DPG context/window probe; expand application assertions as Steps 173–187 introduce their behavior.
- **Verify:** The window probe passes on a capable environment; unavailable DPG/X/GL produces an explicit skip. Add the full 65-frame play/stop assertions before their implementation, within the owning step, keeping completed steps green.
- **Blueprint:** §§6.17, 9.6.

### Step 173 — Own the GUI application lifecycle

- [ ] **Change:** Add gui_dpg optional-import error and EditorApp context/setup/run/shutdown, viewport/theme/font startup and guarded callbacks.
- **Verify:** A minimal window opens/closes cleanly; missing extra gives the specified install advice; no dpg call precedes context creation.
- **Blueprint:** §§2.3, 6.15–6.16.

### Step 174 — Build the fixed editor window layout

- [ ] **Change:** Add menu/window containers, documented item tags and proportional resize placement using compute_layout.
- **Verify:** Shell tags exist; toolbar/status remain visible with min_size=(20,20); viewport starts at the documented screen origin.
- **Blueprint:** §§6.15–6.16.

### Step 175 — Upload viewport images and settle resizing

- [ ] **Change:** Add dynamic texture ownership, initial 16x16 placeholder, rgba_to_texture upload and first-real-size camera fit.
- **Verify:** Smoke texture grows beyond 100 pixels; resized texture is replaced safely; opening view contains the world.
- **Blueprint:** §§6.15–6.16.

### Step 176 — Implement the frame refresh loop

- [ ] **Change:** Wire session.advance, pointer polling hooks, dirty panel refresh, 0.25-second play throttling and FrameGate rendering.
- **Verify:** Frame order matches the model contract; idle rendering settles; play ticks advance without rebuilding all panels each frame.
- **Blueprint:** §6.15.

### Step 177 — Wire simulation and history controls

- [ ] **Change:** Build toolbar and Sim/Edit menu controls for play/pause/stop/step/speed, tools, undo/redo and frame-world.
- **Verify:** Buttons call session APIs; mode/tick/history labels refresh; stop restores state and invalid edits log a readable message.
- **Blueprint:** §6.15.

### Step 178 — Build selectable and draggable hierarchy rows

- [ ] **Change:** Implement bounded/filterable hierarchy UI, select/double-click rename, duplicate/delete/unparent and entity drag/drop payloads.
- **Verify:** Row interactions use session methods; reparent reads target user data correctly; cycles log errors; drag reparent can undo exactly.
- **Blueprint:** §§6.15–6.16.

### Step 179 — Build terrain and brush palette controls

- [ ] **Change:** Add terrain selection, active layer/overlay controls, brush shape/mode/radius/value and fill action.
- **Verify:** Controls update session tools; painting honors selected terrain/layer and brush; fill is undoable and blocked outside edit mode.
- **Blueprint:** §6.15.

### Step 180 — Render and commit inspector widgets

- [ ] **Change:** Add gui_panels InspectorView using FieldWidget kinds and validated commands; preserve focused/active input values during refresh.
- **Verify:** Widget kinds follow §6.11; edits reach session commands; typing is not overwritten; field errors enter the console.
- **Blueprint:** §§6.11, 6.15.

### Step 181 — Render world and prefab panels

- [ ] **Change:** Add WorldView/Prefab views for layers, terrain, settings/resources, scheduling, module toggles and prefab spawn/capture.
- **Verify:** Panel actions use model command factories/session APIs; actual system order and enabled states refresh after undo/redo.
- **Blueprint:** §§6.11, 6.15.

### Step 182 — Build scene and project dialogs

- [ ] **Change:** Add File menu path prompts, new/open/save/save-as/recent/project actions, sidecar toggle and dirty-change confirmation.
- **Verify:** Dialog actions route through session; cancel preserves state; failed Open is logged; path text/Browse behavior stays within the blueprint.
- **Blueprint:** §§6.15, 11.2.

### Step 183 — Build component schema dialogs

- [ ] **Change:** Add SchemaDialog field rows, supported types/defaults/choices and Apply/Delete through session schema operations.
- **Verify:** Invalid schemas display validation errors; model definitions/migrations remain the source of truth; Apply/Delete can be undone in edit mode.
- **Blueprint:** §§6.7, 6.15.

### Step 184 — Build plugin and help menu actions

- [ ] **Change:** Wire reload changed/single plugin, new plugin file, keyboard help and About.
- **Verify:** Reload respects edit-only guard and failure rollback; new files never overwrite; menu failures are guarded and logged.
- **Blueprint:** §6.15.

### Step 185 — Poll pointer and dispatch keyboard input

- [ ] **Change:** Implement pan/zoom/select/drag/paint/spawn polling and shortcuts with viewport/typing/modifier guards.
- **Verify:** Middle/Space pan, cursor zoom and shift selection work; text focus blocks destructive letter/Delete shortcuts; press/release spans frames in input checks.
- **Blueprint:** §§6.14–6.16.

### Step 186 — Display logs and application status

- [ ] **Change:** Add bounded colored/filterable console replay/auto-scroll, title/dirty state, hover cells and frame/status metrics.
- **Verify:** Preexisting logs appear on startup; callback errors remain visible; console stays bounded; status/title follow session state.
- **Blueprint:** §6.15.

### Step 187 — Expose editor launch entry points

- [ ] **Change:** Add editor/__main__.py, open_target and main argument parsing for project/scene, --size and --font-size; verify the existing console script.
- **Verify:** Both python -m simworld.editor and simworld-editor open supported targets; headless import stays DPG-free; smoke assertions pass or record justified skips.
- **Blueprint:** §§2.1, 6.15.

### Step 188 — Verify GUI workflows with real input

- [ ] **Change:** Add/run editor_capture.py with Xvfb/xdotool, held input across frames, screenshots and generated PASS/FAIL results for the §6.17 interactions.
- **Verify:** Inspect screenshots and run full suite; report actual smoke/harness results and every unexercised path, including inspector typing/dialogs/menu clicks and other platforms.
- **Blueprint:** §§6.17, 8 Phase 9, 9.6–9.7.

Next phase: [Measured performance and final verification](10-final-verification.md).
