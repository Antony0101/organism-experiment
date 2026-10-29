# Phase 6: Executable documentation, examples, viewer and benchmarks

Steps **102–110** (9 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§8 Phase 6, 9.4, 10, 13.1–13.2.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** The documented engine can be installed fresh, demonstrated headlessly and measured with a repeatable benchmark.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 102 — Document the minimal engine workflow

- [ ] **Change:** Expand README with self-contained import/world, components/query, layers/terrain and action/brain examples.
- **Verify:** Every new marked block executes independently through test_readme.py and writes artifacts only into its temporary directory.
- **Blueprint:** §9.4.

### Step 103 — Document extensions and persistence

- [ ] **Change:** Add independent module/plugin, config, save/load and rendering examples; raise the runnable-block threshold to at least eight.
- **Verify:** README tests exercise every block with clean_components; examples use only exported APIs and no prior-block state.
- **Blueprint:** §§5.20, 9.4.

### Step 104 — Complete the headless ecosystem CLI

- [ ] **Change:** Extend demo_water_mud.py with steps/out arguments, periodic population/energy/gene/food metrics and PNG frames.
- **Verify:** The documented 300-step command writes valid frames and reports actual measured state without fixed reference survivor claims.
- **Blueprint:** §13.2.

### Step 105 — Ship the toxin plugin example

- [ ] **Change:** Add examples/plugin_toxin/toxin.py and plugin_demo.py using the specified poisoned patch and victim prefab.
- **Verify:** The demo loads the plugin and prints observed survivor counts; starvation/poison behavior is explainable from the model.
- **Blueprint:** §13.1.

### Step 106 — Ship the data-only config demo

- [ ] **Change:** Add examples/config_demo.py using config_world.json and document recipe versus saved state.
- **Verify:** Running the script constructs and advances the configured world without embedding its setup logic in Python.
- **Blueprint:** §§5.17, 7.6.

### Step 107 — Add the optional pygame viewer

- [ ] **Change:** Add examples/viewer_pygame.py as a minimal live view over the public engine renderer.
- **Verify:** Core imports still work without pygame; with the viewer extra, manually start/quit the viewer and report display-dependent checks honestly.
- **Blueprint:** §§2.3, 5.19, 11.2.

### Step 108 — Build repeatable benchmark scenarios

- [ ] **Change:** Add benchmarks/bench.py demo/walkers/fields, warmup, step/repeat controls, medians and optional scheduler profile output.
- **Verify:** Defaults use 200x200, 1000 entities, 20 warmups, 200 measured steps and three repeats; report machine/versions and all three scenarios.
- **Blueprint:** §10.

### Step 109 — Verify a fresh engine installation

- [ ] **Change:** Install core-only and test configurations in fresh temporary virtualenvs; audit imports from outside the checkout.
- **Verify:** Core import requires only stdlib/NumPy; no engine import reaches editor/DPG/pygame; no new runtime dependency was introduced.
- **Blueprint:** §§2.3, 8 Phase 6.

### Step 110 — Verify the engine delivery milestone

- [ ] **Change:** Run the full suite, eight-plus README blocks, demos and benchmark; retain actual baseline output under out/.
- **Verify:** Engine §5 coverage is complete; document skipped optional viewer/display work and measured versions; do not claim reference timings.
- **Blueprint:** §§8 Phase 6, 10.

Next phase: [Headless editor commands, exact undo, schemas and snapshots](07-editor-core.md).
