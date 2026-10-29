# Phase 10: Measured performance and final verification

Steps **189–194** (6 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§8 Phase 10, 10–11, 13.4.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Every final checklist line has PASS, FAIL or NOT RUN evidence; optimizations preserve state and RNG order.

All steps are planned and unstarted. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review.

### Step 189 — Capture repeatable performance baselines

- [ ] **Change:** Run benchmark/profile and viewport timings; record hardware/versions/commands. Before editing code, save full fingerprints, store order and RNG state for three seeds after 200 steps, plus a retrievable local copy of the measured source.
- **Verify:** out/ contains real pre-change timings and versioned state baselines for Step 192; measured reference numbers are context, never pass thresholds. The source copy excludes virtualenvs and user secrets.
- **Blueprint:** §10.

### Step 190 — Optimize one measured engine bottleneck

- [ ] **Change:** Select one profile-supported hot loop and make a small behavior-preserving change; if none is justified, record that conclusion instead.
- **Verify:** Focused/full tests stay unchanged; sequential action semantics, store order and RNG draw order are preserved; benchmark records effect/noise.
- **Blueprint:** §§10.1, 8 Phase 10.

### Step 191 — Optimize one measured viewport bottleneck

- [ ] **Change:** Inspect composition/gather/marker caching and frame/texture gating; change only a demonstrated remaining bottleneck if needed.
- **Verify:** Render/model and GUI smoke checks stay green; image/state behavior remains equal; real timing improvement or no-change decision is recorded.
- **Blueprint:** §§6.10, 10.2.

### Step 192 — Compare complete state before and after performance work

- [ ] **Change:** Run the pre-change and final implementations on at least three identical seeds for 200 steps and retain fingerprints, store order and RNG comparisons.
- **Verify:** Evidence proves matching outcomes on the same versions; comparisons use independently saved pre-change results, never two runs of only the new code.
- **Blueprint:** §§9.3, 10, 12.2 Phase 10.

### Step 193 — Run the final installation and verification checklist

- [ ] **Change:** Execute §13.4 fresh-install/core-only checks, full suite, README/demos, import/RNG audit, scenes/reload/undo checks and available real-GUI checks.
- **Verify:** Each checklist line has command/output plus PASS/FAIL/NOT RUN and reason; allow default_rng initialization while rejecting global random draws; all genuine failures are resolved before acceptance.
- **Blueprint:** §§2.3, 13.4.

### Step 194 — Publish the implementation handoff report locally

- [ ] **Change:** Write out/final_verification.md with checklist, versions, files changed, benchmark comparisons, deviations and known gaps; update plan checkboxes only from evidence.
- **Verify:** Report references real artifacts and observed skips; Brain cache/path wart and other §11 limits stay listed unless separately requested; no reference test count/platform result is claimed without running it.
- **Blueprint:** §§11, 13.4.

This is the final phase. Completion requires the evidence-backed checklist and an honest handoff report.
