# Phase 2: Layers, terrain, spatial queries and headless rendering

Steps **027–043** (17 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§5.5–5.7, 5.14, 5.18–5.19, 8 Phase 2.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Grid operations, mass conservation, terrain semantics, spatial comparisons and valid PNG output pass.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 027 — Allocate typed grid layers

- [ ] **Change:** Add Layer metadata and LayerStore with scalar and trailing vector shapes in layers.py.
- **Verify:** Arrays have shape (height, width, *shape), requested dtype/default and helpful UnknownLayerError behavior.
- **Blueprint:** §5.5.

### Step 028 — Read and write world cells

- [ ] **Change:** Implement bounds, coordinate flooring, tuple/position access, get/set and raw NumPy indexing.
- **Verify:** Asymmetric-grid tests distinguish (x,y) from [y,x]; defaults handle out-of-bounds reads; float-only clamping is exact.
- **Blueprint:** §5.5.

### Step 029 — Implement bounded layer arithmetic

- [ ] **Change:** Add add/take/fill/clamp/total/mean and reject negative take amounts.
- **Verify:** Taking ten from a cell holding two returns two, then zero; min floors and actual applied deltas are respected.
- **Blueprint:** §5.5, G4.

### Step 030 — Sample and inspect neighborhoods

- [ ] **Change:** Add bilinear sample, gradient, window and neighbour enumeration.
- **Verify:** Cell-center sampling, edges, clipped window origins and diagonal selection pass small hand-calculated cases.
- **Blueprint:** §5.5.

### Step 031 — Diffuse and decay fields

- [ ] **Change:** Implement masked pairwise diffusion and exponential decay with stable-rate validation.
- **Verify:** Diffusion conserves mass, cannot cross the mask/border, and rejects unstable rates; split decay intervals agree within tolerance.
- **Blueprint:** §5.5.

### Step 032 — Define terrain identities

- [ ] **Change:** Add Terrain and TerrainRegistry definition/undefinition, RGB validation, id uniqueness and int16 terrain-layer creation.
- **Verify:** Same name/id updates; conflicting ids/names fail; passable terrain requires positive cost; ensure_layer preserves existing data.
- **Blueprint:** §5.6.

### Step 033 — Build terrain lookup grids

- [ ] **Change:** Implement cost/passability LUTs, arbitrary property grids, named masks and cached property invalidation.
- **Verify:** Known and undefined ids follow §5.6; redefining properties clears cached results; at() errors for unknown ids.
- **Blueprint:** §5.6.

### Step 034 — Expose World grid APIs

- [ ] **Change:** Add define_layer/define_field, terrain access/mutation and _paths_changed as a cache-invalidation hook for the future finder.
- **Verify:** Field regrowth metadata validates max/property prerequisites; replacement rules are explicit; terrain API edits call the invalidation hook.
- **Blueprint:** §§5.6–5.7, 5.12.

### Step 035 — Build the spatial hash

- [ ] **Change:** Add bucket insert/remove/clear/sync and radius query in spatial.py.
- **Verify:** Crossing buckets and removing Position clears stale entries; radius results match brute force and sort by (distance, entity).
- **Blueprint:** §5.14.

### Step 036 — Connect spatial indexing to World

- [ ] **Change:** Wire entity lifecycle, sync_spatial and nearby inputs/filters plus sense/late synchronization systems.
- **Verify:** Spawn/despawn updates are immediate; manual movement requires sync; entity-id queries exclude self and tie order stays deterministic.
- **Blueprint:** §§3.4, 5.7, 5.14.

### Step 037 — Generate seeded value noise

- [ ] **Change:** Add value_noise with octave interpolation and normalization using an explicitly supplied generator.
- **Verify:** Output shape/range and same-seed equality hold on rectangular and tiny grids; no module-level random draws occur.
- **Blueprint:** §5.18.

### Step 038 — Paint procedural terrain

- [ ] **Change:** Add terrain_from_noise and paint_blobs using world.rng and path-change notification.
- **Verify:** Every cell receives a defined band including extrema; repeated seeds reproduce terrain and subsequent RNG state.
- **Blueprint:** §5.18.

### Step 039 — Sample valid spawn positions

- [ ] **Change:** Add random_positions area bounds, passability filtering, Python float outputs and bounded rejection attempts.
- **Verify:** Positions stay in the chosen area; blocked regions fail after the documented attempt budget; same seed repeats positions.
- **Blueprint:** §5.18.

### Step 040 — Compose engine RGB and ASCII output

- [ ] **Change:** Add terrain/field blending, entity squares, scaling and ASCII symbols in render.py.
- **Verify:** Rectangular output shape/dtype, field opacity, Appearance fallback and entity toggles match hand-built worlds.
- **Blueprint:** §5.19.

### Step 041 — Encode dependency-free PNGs

- [ ] **Change:** Implement encode_png/save_png/save_frame using struct/zlib/CRC and the public rendering functions.
- **Verify:** A 20x20 frame has valid PNG signature, dimensions, chunk CRCs and decompressed scanlines without Pillow.
- **Blueprint:** §5.19.

### Step 042 — Exercise integrated grid behavior

- [ ] **Change:** Extend test_layers.py and terrain/spatial/render scenarios across World APIs and module-free worlds.
- **Verify:** Replacing layers and modifying terrain preserve documented metadata; spatial queries still match brute force after lifecycle changes.
- **Blueprint:** §§5.5–5.7, 9.1.

### Step 043 — Verify the grid milestone

- [ ] **Change:** Run the accumulated suite and save a small headless PNG; record the coordinate convention and deferred pathfinder integration.
- **Verify:** Grid, diffusion and spatial checks pass; inspect the generated image; no optional GUI dependency is imported.
- **Blueprint:** §8 Phase 2.

Next phase: [Queued events, actions and brain policies](03-behavior.md).
