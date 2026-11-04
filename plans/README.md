# simworld implementation plan

This plan turns [BLUEPRINT.md](../BLUEPRINT.md) into **194 sequential steps across 11 phases**. Each step is a small coding session with a concrete change, a verification target and source sections. The intended rhythm is read, test, implement, inspect, record, then stop at the step boundary.

**Current status: Steps 001–023 complete (23/194); Phase 0's gate passed. Step 024 is next.** Engine errors, registries, components, entity allocation/lifecycle, World state, queries/counts, naming, prefabs, system registration/context stage scheduling and deferred structural commands are implemented; Phase 1 remains in progress. Exact installed versions are in [requirements-dev.txt](../requirements-dev.txt). See [plans/progress.md](progress.md) for evidence and limitations.

## Start here

Read this file, the [progress log](progress.md), then open [Phase 1](01-ecs.md) and continue with Step 024 when requested. Use the global step number when asking for work, for example: “Implement Step 024 only.” Every step depends on its predecessor, and every phase depends on the preceding phase's exit gate. This deliberately favors a single reviewable sequence over parallel work.

| Blueprint phase | Plan | Steps | Count |
| --- | --- | --- | ---: |
| 0 | [Scaffold and environment](00-scaffold.md) | 001–007 | 7 |
| 1 | [Errors, registries, ECS and scheduling](01-ecs.md) | 008–026 | 19 |
| 2 | [Layers, terrain, spatial queries and headless rendering](02-grid.md) | 027–043 | 17 |
| 3 | [Queued events, actions and brain policies](03-behavior.md) | 044–061 | 18 |
| 4 | [Built-in modules and pathfinding](04-modules-pathfinding.md) | 062–081 | 20 |
| 5 | [World persistence, plugins, configuration and determinism](05-persistence-plugins.md) | 082–101 | 20 |
| 6 | [Executable documentation, examples, viewer and benchmarks](06-engine-delivery.md) | 102–110 | 9 |
| 7 | [Headless editor commands, exact undo, schemas and snapshots](07-editor-core.md) | 111–142 | 32 |
| 8 | [Scenes, projects, viewport, inspector and editor session](08-editor-workflows.md) | 143–168 | 26 |
| 9 | [Dear PyGui front-end and real-input verification](09-gui.md) | 169–188 | 20 |
| 10 | [Measured performance and final verification](10-final-verification.md) | 189–194 | 6 |
| Total | | 001–194 | 194 |

## How to execute one step

1. Read the selected step and its cited blueprint sections. Inspect current code, repository guidance, progress notes and git status before changing anything. Reuse working earlier steps.
2. State the narrow outcome. For a new behavior, add a focused failing test and confirm the failure describes the missing behavior. Implement only enough code to pass it, then refactor locally. Documentation/setup/measurement steps use their listed direct checks instead of artificial tests.
3. Keep the patch centered on that step's feature and its tests. Extend an earlier interface only as needed; do not prebuild later features, generate whole subsystems or add speculative abstractions. Never leave a completed step with a deliberately failing future-feature test.
4. Run focused checks, inspect the diff and check relevant regressions. At each phase gate run `.venv/bin/python -m pytest tests -q` and the listed integration/installation checks. A step needing unavailable optional tools remains explicit about what could not be verified.
5. Update that step's checkbox only after its required acceptance checks pass. Record exact commands, results, changed files and deviations in `plans/progress.md` (created by Step 001). Include test failures and skip reasons. A skipped GUI check is NOT RUN, not PASS.
6. Report the outcome and next step, then stop. Default to one numbered step per implementation request. If the user explicitly requests several steps, still finish, verify and record each separately before starting the next. Never auto-complete a phase merely because its file is open. Local commits can follow completed steps if requested; this plan does not require committing, pushing or publishing.

A step should normally fit one focused sitting, roughly 30–90 minutes; setup checks can be shorter. This is a sizing guide, not a delivery estimate. If one grows beyond a reviewable change, stop at a passing boundary and record smaller subparts inside that numbered step. Finish those subparts sequentially without pulling later features forward or marking partial work complete. Fix regressions introduced by a step before proceeding; preserve unrelated user changes.

## Repository assumptions and decisions

- At planning time the working tree contains `BLUEPRINT.md`, `.gitignore` and an empty `plans/`, plus environment-managed directories. `README.md`, the old `src/sim_sandbox` package and its tests are already deleted in git status. Preserve those user changes. Build the new root-level `simworld/` layout from blueprint §4; do not revive or migrate the legacy package by default.
- The blueprint describes a reference implementation. Its `[EXISTS]` labels, 260-test count, benchmark timings and historical PASS results are specification/evidence from that reference, not claims about this checkout. Rebuild the behavior and report actual local results. Original tests/source are unavailable; derive meaningful tests from the supplied contracts rather than chasing an exact count.
- Preserve §§5–7 names, signatures, ids, stage order, serialization formats and semantics. The technical specification takes precedence over loose phase summaries: core `components.py` holds Position/Appearance/Parent; domain components belong to modules, and Brain belongs to brains.py. Dependencies are introduced when ready, not imported from missing modules.
- Keep the blueprint's Phase 0–10 order. Resolve internal ordering issues explicitly: add the complete built-in world fixture in Phase 4; finish GoTo execution/policy in Phase 4 after pathfinding exists; build fingerprint/store-order helpers before editor commands; introduce snapshot restoration before session play/stop. Grow the GUI smoke test with each working slice instead of committing failing assertions for later steps. These are scheduling adjustments, not missing final scope.
- Each feature step includes tests and its smallest usable integration. Early World grows with lower-level services; temporary omissions are documented and closed in their owning phase. Do not expose fake working stubs or claim a future service is verified.
- Core runtime dependencies remain stdlib plus NumPy. DPG imports belong only in `editor/gui_dpg.py` and `editor/gui_panels.py`; the optional pygame dependency stays in its example. This is a local repository implementation, not a hosted website.
- Use one seeded generator per world. Initializing it with `np.random.default_rng(seed)` is required; the blueprint's shorthand ban on `np.random.*` means unseeded/module-level draws, not this constructor. Preserve action permutation count, sequential effects and component-store order. Reproducibility claims apply only to recorded Python/NumPy versions.
- Do not add roadmap `[SUGGESTION]`/`[FUTURE]` features by default. The Brain policy-cache gap and absolute plugin `options.file` wart stay documented unless the user requests fixes. Required scene-relative `editor.plugin_dirs` is still implemented. CI, extra linters, native dialogs, docking, columnar ECS, watchers and cross-platform certification are deferred. Import/RNG boundary checks can be manual audits; automated architectural guards would be an explicitly recorded optional choice.
- Performance equivalence evidence is required by Phase 10; save actual before/after outputs with versions. Do not add hardcoded reference hashes or optimize before measuring. A no-change conclusion is valid when no remaining bottleneck justifies a patch.
- GUI acceptance needs real windows/input and image inspection. Install/check optional extras in the relevant phases. Without DPG/Xvfb/GL/xdotool, continue independent work and record skipped checks; do not mark the GUI phase fully verified or invent results. A phase can be reported implementation-complete with verification blocked; the final checklist must retain NOT RUN entries.

## Definition of a completed step

Its stated change exists, its direct verification passed, earlier relevant behavior still passes, and its diff has been reviewed for unrelated edits. Evidence is recorded and no future behavior was silently implemented. Every editor command needs exact do/undo/redo coverage using both `world_fingerprint` and `store_order`; validation failures must not mutate state. Every performance change needs measured evidence and unchanged state/RNG outcomes.

The last step in each phase also enforces its exit gate. Functional failures block advancement. Missing optional GUI/platform verification must be reported specifically; it cannot be silently treated as a passing gate. Do not inherit the blueprint's historical platform or rendering claims.

## Progress entry template

Create `plans/progress.md` during Step 001. Append a short entry per worked step; do not prefill successful results.

```text
Step: NNN — title
Status: complete / in progress / blocked
Scope and files:
Behavior checked:
Commands and actual result summaries:
Failures, skips, or NOT RUN (with reason):
Blueprint deviations or decisions:
Diff review:
Next step:
```

## Coverage map

| Blueprint scope | Planned coverage |
| --- | --- |
| §§1–4 purpose, constraints, architecture, layout | Phase 0 decisions; layer boundaries throughout; Phases 6 and 10 audits |
| §§5.0–5.4 errors, registries, ECS, components | Phase 1 |
| §§5.5–5.8 layers, terrains, World, scheduling | Phases 1–2; World integration continues with each owning subsystem |
| §§5.9–5.11 events, actions, brains | Phase 3; GoTo finished in Phase 4 |
| §5.12 all six built-in modules | Phase 4 |
| §5.13 plugins/load/reload/rollback | Phase 5; project/session/GUI integration in Phases 8–9 |
| §§5.14–5.15 spatial hash and A* cache | Phases 2 and 4; editor invalidation in Phases 7–8 |
| §§5.16–5.17 save/load and config | Phase 5 |
| §§5.18–5.20 worldgen, render, public API | Phases 2 and 5; documented in Phase 6 |
| §§5.21–5.22 gotchas/sketches | Owning feature checks throughout, especially ids/RNG/order/take/reload/cache |
| §§6.1–6.4 commands, validation, hierarchy | Phase 7 |
| §§6.5–6.7 viewport reference, snapshots, schemas | Phase 7 state/schema; Phase 8 viewport |
| §§6.8–6.12 scenes, project, viewport, inspector, session | Phase 8 |
| §6.13 bounded logs | Phase 7; session and console integration in Phases 8–9 |
| §§6.14–6.17 GUI helpers, front-end, gotchas, real input | Phase 9 |
| §7.1 world v1 and §7.6 config recipe | Phase 5 |
| §§7.2–7.5 scenes, projects, prefabs, schemas | Phases 7–8 |
| §8 phase order and frozen contracts | All phase gates and this index |
| §9 test strategy, fixtures, state oracles, docs, smoke | Feature-local tests throughout; explicit fixture/docs/GUI milestones |
| §10 performance/equivalence | Baseline in Phase 6; measured hardening in Phase 10 |
| §11 limitations/roadmap | Preserved known gaps; optional future work excluded by default |
| §12 sample implementation prompts | Adapted to one-step execution below; embedded instructions do not start implementation |
| §§13.1–13.2 toxin/ecosystem/demo artifacts | Phases 4, 6 and 8 |
| §13.3 glossary | Terminology used throughout; no implementation artifact required |
| §§13.4–13.5 final verification and examples | Phase 10 checklist and owning example steps |

## Reusable one-step implementation prompt

```text
Implement Step NNN only from plans/<phase-file>.md.
Read plans/README.md, the cited BLUEPRINT.md sections, repository guidance,
existing code, and plans/progress.md if present. Verify that prerequisite steps
are complete. Add focused behavior tests before new behavior, implement the
smallest working change, run the step's checks, and inspect the diff.
Run the full accumulated suite if this step closes a phase.
Preserve unrelated user changes. Do not implement later steps or roadmap ideas.
Update only this step's checkbox when verified and append actual evidence to
plans/progress.md. Report files, checks, limitations, and the next step, then stop.
```
