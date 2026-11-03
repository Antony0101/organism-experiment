# Implementation progress

## Step 001 — Record the rebuild baseline

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 002 — Create the packaging skeleton.

### Scope and files

Recorded the repository and tool baseline before implementing the new package. Created this file, checked Step 001 in `plans/00-scaffold.md`, and updated the plan index/current-phase status to reflect progress. No package, dependencies, virtualenv, tests or example files were created. Steps 002–194 remain unstarted.

### Repository baseline

- Workspace: `/home/caspa/projects/personal/organism_experiment`.
- Git HEAD: `56e06f18939ec602d6ca376ce630695ceb550689`.
- Root entries: `.agents/`, `.aws/`, `.codex/`, `.git/`, `.gitignore`, `BLUEPRINT.md`, `plans/`.
- Before this step: **80 tracked files already deleted**, no staged changes, and untracked `BLUEPRINT.md` plus 12 plan documents. `.gitignore` is the only tracked ordinary project file present.
- The deleted files belong to the prior `sim_sandbox` implementation. They are pre-existing user changes; none are restored or migrated by this step.
- `README.md`, `pyproject.toml`, `src/`, `tests/`, and the new `simworld/` package are absent. An IDE tab does not establish that its file exists on disk.
- No applicable `AGENTS.md` was found in the workspace or checked ancestor directories (`/`, `/home`, `/home/caspa`, `/home/caspa/projects`, `/home/caspa/projects/personal`). Environment-managed directories were left untouched.

The following status snapshot was captured **before** this step's writes using `git status --porcelain=v1 --untracked-files=all`. ` D` denotes a working-tree deletion; `??` denotes an untracked file. This snapshot distinguishes existing changes from the three documentation files changed by this step.

```text
 D README.md
 D content/behaviors/README.md
 D content/entities/README.md
 D content/entities/i22/behavior.py
 D content/entities/i22/entity.json
 D docs/DEVELOPER_GUIDE.md
 D pyproject.toml
 D src/sim_sandbox/__init__.py
 D src/sim_sandbox/__main__.py
 D src/sim_sandbox/agents.py
 D src/sim_sandbox/app.py
 D src/sim_sandbox/benchmark.py
 D src/sim_sandbox/camera.py
 D src/sim_sandbox/clock.py
 D src/sim_sandbox/engine/__init__.py
 D src/sim_sandbox/engine/camera.py
 D src/sim_sandbox/engine/clock.py
 D src/sim_sandbox/engine/entity.py
 D src/sim_sandbox/engine/spatial.py
 D src/sim_sandbox/engine/world.py
 D src/sim_sandbox/entity.py
 D src/sim_sandbox/game/__init__.py
 D src/sim_sandbox/game/behavior_projects/__init__.py
 D src/sim_sandbox/game/behavior_projects/builtins.py
 D src/sim_sandbox/game/behavior_projects/model.py
 D src/sim_sandbox/game/behavior_projects/registry.py
 D src/sim_sandbox/game/behavior_projects/runtime.py
 D src/sim_sandbox/game/entities/__init__.py
 D src/sim_sandbox/game/entities/simple_entity.py
 D src/sim_sandbox/game/entities/wandering_agent.py
 D src/sim_sandbox/game/entity_projects/__init__.py
 D src/sim_sandbox/game/entity_projects/model.py
 D src/sim_sandbox/game/entity_projects/registry.py
 D src/sim_sandbox/game/entity_projects/runtime.py
 D src/sim_sandbox/game/project_types.py
 D src/sim_sandbox/game/quick_sandbox.py
 D src/sim_sandbox/game/terrain.py
 D src/sim_sandbox/game/world_definition.py
 D src/sim_sandbox/game/worlds/__init__.py
 D src/sim_sandbox/game/worlds/discovery.py
 D src/sim_sandbox/game/worlds/empty_sandbox/__init__.py
 D src/sim_sandbox/game/worlds/empty_sandbox/definition.py
 D src/sim_sandbox/game/worlds/wandering_plains/__init__.py
 D src/sim_sandbox/game/worlds/wandering_plains/definition.py
 D src/sim_sandbox/presentation/__init__.py
 D src/sim_sandbox/presentation/app.py
 D src/sim_sandbox/presentation/editor/__init__.py
 D src/sim_sandbox/presentation/editor/code_editor.py
 D src/sim_sandbox/presentation/editor/preview.py
 D src/sim_sandbox/presentation/editor/rendering.py
 D src/sim_sandbox/presentation/rendering.py
 D src/sim_sandbox/presentation/screens/__init__.py
 D src/sim_sandbox/presentation/screens/behavior_editor.py
 D src/sim_sandbox/presentation/screens/entity_editor.py
 D src/sim_sandbox/presentation/screens/gameplay.py
 D src/sim_sandbox/presentation/screens/pause_menu.py
 D src/sim_sandbox/presentation/screens/project_hub.py
 D src/sim_sandbox/presentation/screens/quick_sandbox.py
 D src/sim_sandbox/presentation/screens/world_selection.py
 D src/sim_sandbox/presentation/user_state.py
 D src/sim_sandbox/rendering.py
 D src/sim_sandbox/spatial.py
 D src/sim_sandbox/terrain.py
 D src/sim_sandbox/world.py
 D tests/conftest.py
 D tests/test_behavior_components.py
 D tests/test_clock_camera.py
 D tests/test_determinism_agents.py
 D tests/test_entity_editor_screen.py
 D tests/test_entity_preview.py
 D tests/test_entity_projects.py
 D tests/test_lifecycle.py
 D tests/test_project_hub_and_studio.py
 D tests/test_screen_flow.py
 D tests/test_simple_entity.py
 D tests/test_smoke.py
 D tests/test_spatial.py
 D tests/test_terrain.py
 D tests/test_world_definitions.py
 D tests/test_world_discovery.py
?? BLUEPRINT.md
?? plans/00-scaffold.md
?? plans/01-ecs.md
?? plans/02-grid.md
?? plans/03-behavior.md
?? plans/04-modules-pathfinding.md
?? plans/05-persistence-plugins.md
?? plans/06-engine-delivery.md
?? plans/07-editor-core.md
?? plans/08-editor-workflows.md
?? plans/09-gui.md
?? plans/10-final-verification.md
?? plans/README.md
```

### Available tools and packages

These are observations from the default `/usr/bin/python3` interpreter, not a pinned project environment.

| Item | Observed result |
| --- | --- |
| OS/kernel/architecture | Linux, `5.15.167.4-microsoft-standard-WSL2`, `x86_64` |
| `python3` | `/usr/bin/python3`, Python 3.12.3 |
| `python` | Not found on PATH |
| `pip`, `pip3` | Not found on PATH |
| `python3 -m pip --version` | Failed: `/usr/bin/python3: No module named pip` |
| stdlib `venv` module | Discoverable; environment creation/ensurepip not exercised |
| setuptools distribution | 68.1.2 |
| NumPy, pytest, dearpygui, pygame | No installed distribution found for this interpreter |
| Xvfb, xvfb-run, xdotool, ffmpeg, glxinfo | Not found on PATH |
| `DISPLAY` | `:0` |
| `WAYLAND_DISPLAY` | `wayland-0` |

Python 3.12.3 meets the declared Python >=3.10 minimum, but differs from the reference environment. Display variables alone do not prove connectivity, a working OpenGL context or usable GUI input. Dependency bootstrapping and project environment creation belong to Step 003; no installation was attempted here.

### Planned package layout

Use blueprint §4's root-level `simworld/` package in this existing repository. The blueprint's outer `simworld/` is its repository name; do not create an additional nested repository or revive `src/sim_sandbox/`.

```text
organism_experiment/
  BLUEPRINT.md
  plans/                         # Plan and implementation evidence
  pyproject.toml                 # Future packaging, NumPy runtime and optional extras
  README.md                      # Future executable usage examples
  simworld/
    __init__.py                  # Engine public API
    errors.py, registry.py, ecs.py, components.py
    layers.py, terrain.py, world.py, systems.py, events.py
    actions.py, brains.py, spatial.py, pathfinding.py
    serialization.py, config.py, worldgen.py, render.py, plugin.py
    modules/
      __init__.py, base.py
      terrain.py, resources.py, movement.py
      metabolism.py, reproduction.py, ageing.py
    editor/
      __init__.py, __main__.py
      errors.py, fields.py, commands.py, commands_world.py, hierarchy.py
      state.py, schema.py, scenes.py, project.py, viewport.py
      inspector.py, session.py, log.py, gui_model.py
      gui_dpg.py, gui_panels.py
  tests/
  examples/                      # Includes demo project and plugin examples
  benchmarks/bench.py
  out/                           # Generated verification and benchmark evidence
```

This tree is a destination, not created by Step 001. Step 002 adds only its prescribed packaging skeleton; feature modules arrive in their owning steps.

### Architectural baseline

- General-purpose 2D grid engine: generic layers, ECS data components, validated actions/brains and extensible modules/plugins. No 3D, networking, threading or domain-specific nutrient/hunger logic in core.
- Core imports only stdlib and NumPy; optional pygame remains in its example. Headless editor models import no Dear PyGui; only `gui_dpg.py` and `gui_panels.py` import it.
- Layers use `data[y, x]`; world positions use `(x, y)`. Entity ids are `(generation << 32) | index`, with generations starting at one.
- A single seeded generator per world controls randomness. Store insertion order and sequential shuffled action effects are part of reproducibility.
- Engine APIs underpin the editor. User edits use undoable commands; play/stop restores captured state exactly. Preserve blueprint §§5–7 contracts as implementation progresses.

### Commands and observed outcomes

- `pwd`: confirmed the workspace above.
- `rg --files -g AGENTS.md -g '!node_modules' -g '!.venv'`: no matches (exit 1); ancestor `AGENTS.md` checks also found none.
- `git status --short` and `git status --porcelain=v1 --untracked-files=all`: captured existing deletions and untracked blueprint/plans above.
- `git rev-parse HEAD`: recorded the HEAD above.
- `git diff --name-only --diff-filter=D`: counted 80 existing deletions.
- Read `plans/README.md`, `plans/00-scaffold.md`, blueprint §§1–4 and §8 Phase 0 to establish scope/layout.
- `for tool in python python3 pip pip3 Xvfb xvfb-run xdotool ffmpeg glxinfo; do if command -v "$tool" >/dev/null 2>&1; then command -v "$tool"; else printf '%s: not found\n' "$tool"; fi; done`: only `python3` found.
- `python3 --version`: `Python 3.12.3`.
- `python3 -m pip --version`: failed with `No module named pip`; recorded as a setup limitation, not a passing check.
- Python stdlib inspection with `platform`, `os.environ`, `importlib.util.find_spec('venv')` and `importlib.metadata.version`: produced the OS/display/module/distribution observations above without importing a GUI toolkit.
- A Python stdlib baseline capture stored git status, deleted paths and SHA-256 hashes of all 14 ordinary project files in `/tmp/simworld-step001-baseline.json` before edits. `.git`, `.agents`, `.aws` and `.codex` contents were excluded.

### Failures, skips and deviations

No implementation tests or installs ran: the package/test skeleton does not exist and pytest/pip are missing. No GUI/display/OpenGL probe ran. No deviations from Step 001; the small status-text updates keep the plan accurate. This step uses direct inventory/content-preservation checks, as specified for setup/documentation work.

### Verification and diff review

Verification compares the saved pre-edit hashes/status/deletion list against the final workspace, allowing changes only to this progress file, `plans/00-scaffold.md` and `plans/README.md`. The command and observed result are recorded below after running that check.

Ran `python3 /tmp/verify_simworld_step001.py` (temporary stdlib-only verification script comparing the pre-edit snapshot with the final files):

```text
PASS: only plans/progress.md, plans/00-scaffold.md and plans/README.md changed.
PASS: all 80 pre-existing deletions remain; no staged changes or recovered files.
PASS: exactly Step 001 checked; 193 steps unchecked; no package/environment/test scaffold created.
PASS: reviewed documentation has no trailing whitespace.
```

Reviewed the documentation changes against the pre-edit content: the index/current-phase text now reflects Step 001 completion, the only checked step is 001, and this log records the observed baseline and future package destination. Next action, when requested: Step 002 only.

## Step 002 — Create the packaging skeleton

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 003 — Create and record the development environment.

### Scope and files

- Added `pyproject.toml` exactly as specified in blueprint §2.1: setuptools backend, Python >=3.10, NumPy-only runtime dependency, viewer/editor/test extras, three explicitly listed packages, pytest configuration and the future `simworld-editor` entry point.
- Added minimal `simworld/__init__.py` with an empty `__all__`, plus `simworld/modules/__init__.py` and the headless `simworld/editor/__init__.py`. These import no dependencies or future feature modules.
- Added root `README.md` with exactly one self-contained marked Python block (`import simworld`), an honest skeleton-status description and links to the plan/progress.
- Checked Step 002 and updated current status in `plans/00-scaffold.md` and `plans/README.md`.

`README.md` and `pyproject.toml` were absent at the Step 001 baseline. Their new contents implement the authorized simworld skeleton; they do not restore the old sim_sandbox files. The other 78 pre-existing tracked deletions remain untouched.

### Commands and observed outcomes

- Read Step 002, prior progress and blueprint §2.1; checked git status and applicable repository guidance before editing. No applicable `AGENTS.md` was found.
- Captured pre-edit content hashes and deleted paths using a stdlib Python script in `/tmp/simworld-step002-baseline.json`.
- Ran a `python3 -B -` verification script using `tomllib`/`re` to compare the complete TOML text against the blueprint code block, assert runtime/extras/entry-point declarations, import all three packages, check the checkout module path/empty root `__all__`, and execute the sole README block. Actual output:

```text
PASS: pyproject.toml exactly matches BLUEPRINT.md §2.1; runtime/extras/entry point verified.
PASS: all three declared packages import from the checkout; root __all__ is empty.
PASS: README contains exactly one marked, executable import example.
```

- `git diff --check`: passed without output.
- `git diff --stat -- README.md pyproject.toml`: inspected the new skeleton's tracked-file differences from the legacy HEAD. New package files were also inspected directly; tracked-file diff output alone does not include untracked package files.

### Limitations and deviations

No deviations. No dependencies installed, virtualenv created or pytest tests added/run: those belong to Steps 003–005. This packaging/setup step used direct checks rather than new tests that duplicate static metadata. Import verification covers the checkout only; installed-package checks are pending. The declared editor entry point intentionally targets a future module and cannot launch a window yet.

### Verification and diff review

The final scope check compares pre-edit hashes and git deletion paths, permits only the five skeleton files and three plan/progress files, verifies that all remaining legacy deletions remain absent, and confirms exactly Steps 001–002 are checked. Its actual output is recorded below after execution.

Ran `python3 -B /tmp/verify_simworld_step002.py` (temporary stdlib-only verification script):

```text
PASS: only five skeleton files and three plan/progress files changed.
PASS: all 78 remaining legacy deletions preserved; no staged changes.
PASS: exactly Steps 001-002 checked; 192 steps unstarted; no virtualenv/tests created.
PASS: changed files have valid Markdown links and no trailing whitespace.
```

Reviewed the five skeleton files and status-only plan edits. All additions stay within Step 002. Next action, when requested: Step 003 only.

## Step 003 — Create and record the development environment

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 004 — Execute the first documentation example.

### Scope and files

- Created the ignored `.venv/` using the available Python 3.12.3 and installed this checkout with its `test` extra in editable mode. `include-system-site-packages = false` keeps it isolated from system packages.
- Added [requirements-dev.txt](../requirements-dev.txt) with the actual Python/platform, exact installed package pins (including pip and transitive test dependencies), local editable `-e .[test]`, and recreation commands. Build-isolation dependencies continue to follow `pyproject.toml`; these pins describe the installed environment, not a cross-platform lockfile.
- Updated only Step 003's checkbox/current-phase and plan index, plus this log. Left `pyproject.toml`, package code, root README and all legacy deletions unchanged.

### Installed versions

| Item | Version |
| --- | --- |
| Python | 3.12.3 |
| NumPy | 2.5.4 |
| pytest | 9.2.0 |
| pip | 24.0 |
| iniconfig | 2.3.1 |
| packaging | 26.3 |
| pluggy | 1.7.0 |
| Pygments | 2.21.0 |
| simworld | 0.1.0 (editable local checkout) |

Python and pytest differ from the reference versions; all satisfy declared requirements. These are locally verified versions, not inferred from the blueprint. Dear PyGui and pygame remain uninstalled; no GUI extra was requested by this step.

### Commands and observed outcomes

- `python3 --version`: `Python 3.12.3`.
- `python3 -m ensurepip --version`: `pip 24.0`; the bootstrap module is available.
- `python3 -m venv .venv`: succeeded; `.venv/bin/python -m pip --version` confirmed pip 24.0 inside `.venv`.
- Initial `.venv/bin/python -m pip install --disable-pip-version-check -e '.[test]'`: failed while downloading build dependencies because DNS was unavailable in the restricted network. No version availability conclusion was drawn from that failure.
- Retried with network access using `.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -e '.[test]'`: succeeded. Actual final output:

```text
Successfully built simworld
Installing collected packages: pygments, pluggy, packaging, numpy, iniconfig, simworld, pytest
Successfully installed iniconfig-2.3.1 numpy-2.5.4 packaging-26.3 pluggy-1.7.0 pygments-2.21.0 pytest-9.2.0 simworld-0.1.0
```

- `.venv/bin/python -m pip check`: `No broken requirements found.`
- `.venv/bin/python -m pip freeze --all`: listed the installed versions above. Pip rendered the editable project as a legacy git remote URL, so the development requirements intentionally use the local `-e .[test]` instead. No git source was fetched.
- `.venv/bin/python -m pytest --version`: `pytest 9.2.0`.
- A stdlib metadata check initially failed when run at the repository root: it selected generated `simworld.egg-info`, which lacks `direct_url.json`. Re-running from `/tmp` selected installed distribution metadata and confirmed `dir_info.editable = true`, the local file URL and an isolated virtualenv.
- From `/tmp`, ran `/home/caspa/projects/personal/organism_experiment/.venv/bin/python -B -` to import `numpy`, `pytest` and all three declared packages, assert the source path and inspect versions. Output:

```text
PASS: editable packages, NumPy and pytest import from outside the checkout.
NumPy: 2.5.4
pytest: 9.2.0
PASS: installed simworld 0.1.0 metadata confirms an editable local checkout in an isolated .venv.
```

The last PASS line came from the separate corrected installed-metadata check, also run from `/tmp`.

### Limitations and decisions

No feature implementation or test files were added. The pytest runner is available, but the suite does not exist until subsequent steps, so no suite pass is claimed. Recreating from the new pins in another fresh environment remains unverified here; the later fresh-install milestone covers that. System Python and global packages were not modified. The transient read-only default pip-cache warning was avoided on the successful install with `--no-cache-dir`.

### Verification and diff review

The final checks compare installed versions against every requirements pin, validate virtualenv isolation/local editable installation, verify ignored generated files, and compare the saved pre-edit content hashes/deleted paths. Only `requirements-dev.txt` and the three plan/progress files may change outside ignored installation artifacts; all 78 legacy deletions must remain. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step003.py` (temporary stdlib-only verification script), followed by `.venv/bin/python -m pip --no-cache-dir check` and `git diff --check`:

```text
PASS: all 7 installed dependency/tool versions match requirements-dev.txt; .venv is isolated.
PASS: only requirements-dev.txt and three plan/progress files changed; generated environment/metadata are ignored.
PASS: all 78 legacy deletions preserved; no staged changes.
PASS: exactly Steps 001-003 complete; no future tests/features added; changed links/whitespace valid.
No broken requirements found.
```

`git diff --check` passed without output. Reviewed the requirements file and plan/progress edits; the blueprint package metadata and package implementation are unchanged. Next action, when requested: Step 004 only.

## Step 004 — Execute the first documentation example

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 005 — Establish isolated test fixtures.

### Scope and files

- Added `tests/__init__.py` and `tests/test_readme.py` following blueprint §9.4. The tests require at least one marked Python block and execute each block with a new namespace in its own pytest temporary directory. Tracebacks identify the README block number.
- Kept the initial threshold at one; Phase 6 raises it to eight. The `clean_components` fixture is deliberately deferred to Step 005, so this step imports no unimplemented registry/World modules.
- Updated the Step 004 checkbox, phase/index status and this log. No engine code or dependencies changed.
- This turn began at clean git HEAD `02d5a92` (`starting point`); earlier changes, including legacy deletions, had already been committed. Preservation checks use this turn's baseline rather than treating historical deletions as current working-tree changes.

### Commands and observed outcomes

- Read the current plan/progress, README and blueprint §9.4; checked repository/ancestor guidance and git status. No applicable `AGENTS.md` was found. `.venv/bin/python -m pytest --version` reported `pytest 9.2.0`.
- `.venv/bin/python -m pytest tests/test_readme.py -q`: both tests passed (`.. [100%]`; the combined quiet settings suppress the summary).
- Used a temporary Python probe to append a marked block raising `RuntimeError("intentional Step 004 failure probe")` and run `.venv/bin/python -m pytest tests/test_readme.py -o addopts='' -q`. The subprocess exited 1 as expected: **1 failed, 2 passed in 0.03s**. Its traceback identified `README block 1:1`. A `finally` block restored the original README bytes and verified exact restoration.
- Used a second temporary probe to append two marked blocks. Each asserted the same relative filename was absent, then wrote it; the second also asserted a variable from the first was absent. The same pytest command exited 0: **4 passed in 0.02s**. This demonstrates directory and namespace isolation. No probe file appeared in the repository, and README bytes were restored again.
- `.venv/bin/python -m pytest tests -o addopts='' -q` after restoration: **2 passed in 0.01s**.

### Limitations and decisions

No deviations from Step 004. Temporary failure/isolation probes were removed and not saved as README examples. Component-registry cleanup will be introduced by Step 005; the current sole example only imports the skeleton. No fixtures, feature implementation or Phase 0 completion claim were added here.

### Verification and diff review

Final verification compares pre-edit hashes, limits changes to the two new test files and three plan/progress files, checks README restoration, confirms exactly Steps 001–004 are checked, and checks links/whitespace. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step004.py` (temporary stdlib-only scope verifier):

```text
PASS: only two test files and three plan/progress files changed.
PASS: README restored exactly; no probe artifacts, unrelated deletions or staged changes.
PASS: exactly Steps 001-004 complete; fixture work remains deferred; links/whitespace valid.
```

`git diff --check` passed without output. Reviewed the new test files directly alongside the tracked plan diff; the untracked test files are not included in `git diff --stat`. Next action, when requested: Step 005 only.

## Step 005 — Establish isolated test fixtures

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 006 — Document the incremental working agreement.

### Scope and files

- Added `tests/conftest.py` with a function-scoped `clean_components` fixture. It imports the registry only at fixture setup, snapshots registrations and restores them in `finally`, removing additions and restoring replaced/removed entries.
- Until `simworld.registry` exists, cleanup is a no-op. Only that precise missing-module case is allowed: failures caused by missing dependencies within a registry are re-raised.
- Connected every runnable README block to `clean_components` as specified by blueprint §9.4.
- Added three focused cases in `tests/test_fixtures.py`: successful-test cleanup, failed-test cleanup, and propagation of an internal import failure. A temporary module/registry test double exercises the documented registry interface without implementing engine features.
- Updated Step 005 completion/index and this log. Preserved the uncommitted Step 004 files/edits present at the start of this turn.

### Deferred fixture

The complete `world` fixture from blueprint §9.2 remains deferred to **Step 071 (Phase 4)**, which explicitly completes the fixture after World, all six built-ins and terrain APIs exist. `tests/conftest.py` records that dependency; it imports no World or built-in module at collection time. No fake world fixture is exposed in the meantime.

### Commands and observed outcomes

- Baseline `.venv/bin/python -m pytest tests -o addopts='' -q`: **2 passed in 0.01s**.
- Added regression tests and README fixture use first. The same suite command failed as expected with **1 error in 0.10s**, reporting `ModuleNotFoundError: No module named 'tests.conftest'` before the fixture was implemented.
- After implementation, `.venv/bin/python -m pytest tests -o addopts='' -q`: **5 passed in 0.03s**. Cleanup restores original object registrations after normal completion and an intentional test-body exception; unrelated import errors propagate.
- `.venv/bin/python -m pytest tests --collect-only -o addopts='' -q`: **5 tests collected in 0.01s**, without requiring missing World or registry modules.

### Limitations and decisions

No deviations from Step 005. Real component/decorator integration awaits the actual registry; current restoration tests use a module test double, not a functioning engine registry. The README test also passes in the real scaffold where the registry is absent. No runtime code, dependencies or future fixtures were added.

### Verification and diff review

Final verification compares this turn's pre-edit content hashes, allows only the three fixture/README test files and three plan/progress files, and checks that exactly Steps 001–005 are complete. It also verifies collection/execution left the unimplemented engine absent and validates changed Markdown links/whitespace. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step005.py` (temporary stdlib-only scope verifier):

```text
PASS: only three fixture/README test files and three plan/progress files changed from this turn baseline.
PASS: existing unrelated files preserved; no staged changes, deletions or future engine modules added.
PASS: exactly Steps 001-005 complete; 189 steps unchecked; links/whitespace valid.
```

`git diff --check` passed without output. Reviewed the fixture, focused tests, README fixture dependency and status-only plan changes. Next action, when requested: Step 006 only.

## Step 006 — Document the incremental working agreement

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 007 — Verify the scaffold milestone.

### Scope and working agreement

Expanded root `README.md` with virtualenv creation, pinned development installation and editable test-extra commands; full/focused test and dependency-check commands; locally observed versions; package/import boundaries; current scaffold limitations; and the numbered one-step execution procedure. Updated completion status in `plans/00-scaffold.md` and `plans/README.md`, plus this log. Existing uncommitted test/plan changes were preserved.

The contributor workflow is: read the next unchecked step and cited blueprint sections, inspect status, implement only that step with focused tests when appropriate, verify and review it, record actual evidence/deviations here, check completion only after acceptance, report the next step and stop. Full accumulated tests and each phase exit gate are required at phase boundaries. Preserve unrelated changes and keep optional roadmap features separate.

### Commands and observed outcomes

Ran the README's verification commands against the existing Step 003 environment:

| Command | Observed result |
| --- | --- |
| `.venv/bin/python -m pytest tests` | **5 passed in 0.02s** |
| `.venv/bin/python -m pip --no-cache-dir check` | **No broken requirements found.** |
| `.venv/bin/python -m pytest tests/test_readme.py` | **2 passed in 0.02s** |

A Python metadata query confirmed the README's recorded versions: Python **3.12.3**, NumPy **2.5.4**, pytest **9.2.0**, pip **24.0**. The README retains exactly one marked Python import example; setup/verification shell fences are documentation, not Python examples.

### Current limitations and deferred work

Phase 0's final milestone remains **Step 007**, not completed by this documentation task. The engine/public simulation API and editor front-end are unimplemented. Component cleanup permits the absent registry until it exists; the complete `world` fixture remains deferred to Step 071. GUI extras are not installed, and GUI/OpenGL/cross-platform behavior remains unverified.

No fresh environment was created and no dependencies were reinstalled here. The documented pinned recreation path has not been exercised in a separate fresh environment. Commands and versions reflect the existing working environment; the README distinguishes those observations from future reproducibility claims.

### Verification and diff review

No deviations from Step 006. This documentation-only change needs direct checks rather than new tests. Final review checks that only root README and the three plan/progress documents changed, links resolve, only Steps 001–006 are checked and all earlier source/tests/dependencies remain byte-for-byte intact. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step006.py` (temporary stdlib-only scope verifier):

```text
PASS: only README.md and three plan/progress documents changed; existing source/tests/dependencies preserved.
PASS: exactly Steps 001-006 complete; Step 007 pending; one marked README Python example retained.
PASS: documentation links resolve; no trailing whitespace, staged changes or deletions.
```

`git diff --check` passed without output. Reviewed the root README diff and plan/progress edits against the pre-edit snapshot. A contributor can now find the next step, verification commands and current limitations directly in the repository. Next action, when requested: Step 007 only.

## Step 007 — Verify the scaffold milestone

**Status:** complete. **Date:** 2026-10-29. **Phase 0 exit gate:** passed. **Next:** Step 008 — Build actionable engine errors (Phase 1).

### Scope and files

Reinstalled the local package in editable mode with its declared test extra, ran the complete current suite and dependency check, checked installed imports outside the checkout, and audited the scaffold against the blueprint. Updated only root `README.md`, `plans/README.md`, `plans/00-scaffold.md` and this progress log outside ignored installation artifacts. Existing uncommitted tests/documentation were preserved. Pip refreshed ignored `.venv/` installation files and generated `simworld.egg-info/` metadata.

No feature code, dependency pins or test cases changed. This milestone verifies the scaffold; it does not implement Phase 1.

### Commands and actual results

1. `.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -e '.[test]'` with package-index access: build-isolation setup and editable build succeeded. Existing dependency versions already satisfied requirements. Final installation output:

   ```text
   Successfully built simworld
   Installing collected packages: simworld
     Attempting uninstall: simworld
       Found existing installation: simworld 0.1.0
       Uninstalling simworld-0.1.0:
         Successfully uninstalled simworld-0.1.0
   Successfully installed simworld-0.1.0
   ```

2. `.venv/bin/python -m pytest tests -q`: five passing dots, no failures; the double quiet setting suppresses pytest's summary. After updating README status, ran `.venv/bin/python -m pytest tests -o addopts='' -q` to exercise the final documentation and capture the exact summary: **5 passed in 0.02s**.
3. `.venv/bin/python -m pip --no-cache-dir check`: **No broken requirements found.**
4. From `/tmp`, ran `/home/caspa/projects/personal/organism_experiment/.venv/bin/python -I -B -` to import all three declared packages, check their source paths, inspect installed `direct_url.json`, verify virtualenv isolation and confirm GUI packages are absent. Actual output:

   ```text
   PASS: all three editable packages import from /tmp in Python isolated mode.
   PASS: local editable metadata confirmed; headless imports work without Dear PyGui/pygame.
   Python: 3.12.3
   numpy: 2.5.4
   pytest: 9.2.0
   pip: 24.0
   ```

5. A stdlib audit compared `pyproject.toml` verbatim with blueprint §2.1, matched every requirements pin to the installed version, checked the three package initializers, test package/fixtures and sole README example, and confirmed no other runtime Python modules exist:

   ```text
   PASS: blueprint packaging, exact dependency pins and Phase 0 file boundaries verified.
   ```

6. `.venv/bin/python --version` and `.venv/bin/python -m pip --no-cache-dir list --format=freeze`: Python **3.12.3**, NumPy **2.5.4**, pytest **9.2.0**, pip **24.0**, iniconfig **2.3.1**, packaging **26.3**, pluggy **1.7.0**, Pygments **2.21.0**, editable simworld **0.1.0**. Versions remain recorded in README and `requirements-dev.txt`.
7. `command -v` checks: **Xvfb, xvfb-run, xdotool, ffmpeg and glxinfo not found**. No optional GUI checks ran.

### Phase 0 acceptance

| Requirement | Result |
| --- | --- |
| Blueprint packaging and three importable package skeletons | PASS |
| Editable installation with test dependencies | PASS |
| Full current suite, including runnable README example and cleanup cases | PASS — 5 passed |
| Imports outside the checkout in isolated Python mode | PASS |
| Dependency consistency and actual versions recorded | PASS |
| No later-phase runtime implementation added | PASS |

The complete §9.2 `world` fixture is deferred to Step 071, as already decided in the plan and Step 005; the scaffold's lazy component fixture is present. This is the documented scheduling adjustment from the blueprint's broad Phase 0 fixture wording, not an implemented World claim. The suite has five tests because it includes cleanup regression cases; reference counts are not acceptance targets.

### Unverified work and limitations

The install check reused the existing `.venv`; fresh-environment recreation from pinned requirements is **NOT RUN** here and remains documented as such. GUI/viewer extras and windows, OpenGL, other operating systems, simulation behavior and the future editor command are unverified or unimplemented. These are not requirements of this scaffold gate. No dependency or implementation failure remains from the checks that ran.

### Verification and diff review

The final scope check compares pre-edit hashes, preserves prior changes, allows only the four documentation/status files above, checks all seven Phase 0 boxes and confirms all 187 later steps remain unstarted. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step007.py` (temporary stdlib-only scope verifier):

```text
PASS: only four documentation/status files changed; prior source/tests/pins and unrelated work preserved.
PASS: all seven Phase 0 steps complete; all 187 later steps unchecked; no Phase 1 runtime code added.
PASS: Markdown links/whitespace valid; no staged changes or deletions.
```

`git diff --check` passed without output. Reviewed the documentation/status changes and the pre-edit hash comparison. Phase 0 is complete within its planned scope. Next action, when requested: Step 008 only.

## Step 008 — Build actionable engine errors

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 009 — Implement the generic name registry. **Phase 1:** in progress.

### Scope and files

- Added `simworld/errors.py` with all 20 documented exception classes, stdlib-only imports, module `__all__` and the specified built-in exception ancestry. Unknown-name subclasses supply their kind; callers can override the kind and append a hint.
- `UnknownNameError` consumes known names once, converts them to strings for comparison, uses `difflib.get_close_matches(..., n=3)`, lists available names and handles an empty registry explicitly. Plain error subclasses preserve caller-supplied messages for later engine operations.
- Updated `simworld/__init__.py` to explicitly re-export errors, as required by §5.1. The initially empty scaffold API now exposes only the implemented errors; no future runtime API is exported.
- Added focused cases in `tests/test_ecs.py` for inheritance, all unknown-name kinds, suggestions, known values, override/hint, empty and non-string/generator inputs, unrelated names, supplied diagnostics and exports.
- Updated root README and the Phase 1/index status, plus this log. The turn began with a clean working tree; no existing uncommitted work needed alteration.

### Commands and observed outcomes

- Read Step 008 and blueprint §5.1, checked repository status and applicable guidance, and saved pre-edit file hashes. No applicable `AGENTS.md` was found.
- Added tests first. `.venv/bin/python -m pytest tests/test_ecs.py -o addopts='' -q` failed as expected before implementation: **1 error in 0.12s**, reporting `ImportError: cannot import name 'errors' from 'simworld'`.
- After implementing the error module and public exports, `.venv/bin/python -m pytest tests -o addopts='' -q`: **40 passed in 0.08s** (35 error cases and the five existing scaffold cases).

### Limitations and decisions

No deviations from Step 008. Stale/missing/duplicate exceptions currently carry diagnostics supplied by their caller; actual allocator/World diagnostics belong to later steps. Registries, components and World do not exist yet. No dependency changes, ECS behavior or later-step features were added.

### Verification and diff review

Final review compares pre-edit hashes, allows only the error module, root exports, ECS error tests and four documentation/status files, confirms exactly Steps 001–008 are complete, and checks that registry/World remain absent. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step008.py` (temporary stdlib-only scope verifier):

```text
PASS: only error implementation/exports/tests and four documentation/status files changed.
PASS: Steps 001-008 complete; all 186 later steps unchecked; registry/World absent.
PASS: unrelated files preserved; links/whitespace valid; no staged changes or deletions.
```

`git diff --check` passed without output. Reviewed exception definitions, lookup message construction, public exports, focused tests and the status-only documentation changes. Next action, when requested: Step 009 only.

## Step 009 — Implement the generic name registry

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 010 — Describe and register data components. **Phase 1:** in progress.

### Scope and files

- Added `simworld/registry.py` with generic `Registry`, instance-local ordered storage, duplicate-name errors, explicit replacement, optional removal, configured unknown-name errors, containment/iteration/length, snapshot `names()` and live `items()` views. Registration returns the supplied object; replacement preserves its key position.
- Added the empty, process-global `COMPONENTS` registry with `UnknownComponentError`. This small integration is necessary now: creating the registry module makes the existing lazy `clean_components` fixture import it. No component metadata, decorators or component classes were implemented early; its value annotation remains `Any` until metadata exists.
- Added 13 focused cases in `tests/test_registry.py`, including duplicate failure atomicity, replacement/removal order, false-valued entries, independent registries, configured errors and real `COMPONENTS` cleanup after success/failure. Existing fixture tests remain intact.
- Updated the root README, Phase 1/index status and this log. Preserved all pre-existing Step 008 changes; root exports and the error implementation remain unchanged.

### Commands and observed outcomes

- Read Step 009, blueprint §5.2 and existing fixtures/errors, checked status/guidance, and saved pre-edit hashes. No applicable `AGENTS.md` was found.
- Added the tests first. `.venv/bin/python -m pytest tests/test_registry.py -o addopts='' -q` failed as expected: **1 error in 0.13s**, with `ModuleNotFoundError: No module named 'simworld.registry'`.
- After implementation, `.venv/bin/python -m pytest tests -o addopts='' -q`: **53 passed in 0.09s**. This includes all 40 prior cases plus 13 new registry cases and verifies the existing README fixture works against the real registry.

### Limitations and decisions

No generic-registry contract deviations. The empty `COMPONENTS` container is introduced one step before its metadata/decorators so this completed step keeps the existing suite working. The cleanup fixture itself did not need modification. `Registry` is available from `simworld.registry`; package-root API completion remains incremental. Components, serialization, active-world context and World are still unimplemented.

### Verification and diff review

Final review compares this turn's pre-edit hashes, permits only the registry module/tests plus four documentation/status files, verifies exactly Steps 001–009 are checked and confirms no component/World feature implementation was introduced. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step009.py` (temporary stdlib-only scope verifier):

```text
PASS: only registry implementation/tests and four documentation/status files changed from this turn baseline.
PASS: Steps 001-009 complete; 185 steps unchecked; component metadata/World remain unimplemented.
PASS: prior work preserved; links/whitespace valid; no staged changes or deletions.
```

`git diff --check` passed without output. Reviewed the registry's ordered mapping behavior, error paths, shared empty container and tests alongside documentation/status updates. Next action, when requested: Step 010 only.

## Step 010 — Describe and register data components

**Status:** complete. **Date:** 2026-10-29. **Next:** Step 011 — Serialize one component at a time. **Phase 1:** in progress.

### Scope and files

- Added `FieldInfo` and `ComponentInfo` dataclasses to `simworld/registry.py`, and typed the existing global registry as `Registry[ComponentInfo]`.
- Added `prop` as a dataclass-field helper retaining min/max/tooltip/serialize and arbitrary widget metadata, defaults/factories and constructor participation.
- Added bare/called `@component` forms with optional name/category, slots for plain classes, reflection of fields/defaults/docstrings, and same-module/qualified-name replacement. Other classes colliding on a name raise `DuplicateNameError` with explicit-name advice. Existing dataclasses retain their identity/configuration.
- Re-exported `component`, `prop` and the existing `COMPONENTS` object from `simworld/__init__.py`; metadata classes remain available from the registry module.
- Added 13 focused cases in `tests/test_components.py`, all using `clean_components`. Verified cleanup of actual registered/reloaded metadata after normal completion and an exception; the fixture already activated in Step 009 required no code changes.
- Updated root README, Phase 1/index status and this log. Existing staged changes are preserved without staging, unstaging or committing anything.

### Commands and observed outcomes

- Read Step 010, blueprint §5.2 and existing registry/fixtures; inspected repository/ancestor guidance and saved pre-edit content hashes plus the staged binary diff. No applicable `AGENTS.md` was found.
- Added tests first. `.venv/bin/python -m pytest tests/test_components.py -o addopts='' -q` failed as expected before implementation: **1 error in 0.14s**, reporting `ImportError: cannot import name 'ComponentInfo' from 'simworld.registry'`.
- After implementation, `.venv/bin/python -m pytest tests -o addopts='' -q`: **66 passed in 0.12s**, covering all 53 prior cases and 13 new component cases.

### Decisions and limitations

Factory defaults are evaluated once for the reflected metadata default; dataclass instances still receive independently created values. Fields without a declared default are represented as `None` in metadata while remaining required constructor arguments. Field metadata keeps all supplied keys, including arbitrary editor hints. These choices fill in details left implicit by §5.2; they do not enforce numeric types/ranges on component instances.

Serialization, `component_name`, active-world context, engine Position/Appearance/Parent classes and World remain for their owning steps. No dependencies or unrelated fixture behavior changed. Component metadata reload replaces registration; live-entity migration is a later plugin concern.

### Verification and diff review

Final review compares pre-edit content hashes and staged diff, limits changes to registry/root exports, component tests and four documentation/status files, and checks exactly Steps 001–010 are complete. Results follow after execution.

Ran `.venv/bin/python -B /tmp/verify_simworld_step010.py` (temporary stdlib-only scope verifier):

```text
PASS: only component metadata/registration, root exports, tests and four documentation/status files changed.
PASS: existing staged diff unchanged; prior source/tests/pins preserved.
PASS: Steps 001-010 complete; 184 steps unchecked; no serialization, context or World implemented.
PASS: Markdown links and whitespace valid.
```

`git diff --check` passed without output. Reviewed field reflection/default behavior, decorator identity rules, public exports and cleanup regression cases. Next action, when requested: Step 011 only.

## Step 011 — Serialize one component at a time

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 012 — Add the three core data components. **Phase 1:** in progress.

### Scope and files

- Added `component_name`, `component_to_dict` and `component_from_dict` to `simworld/registry.py` and its module exports. Names supplied as strings use the specialized unknown-component error; classes and instances must carry a currently registered component name.
- Component conversion calls `_check_serializable()` when present, omits fields marked `serialize=False`, converts NumPy scalars to Python scalars, sequences to lists, mapping keys to strings, and nested dataclass instances to dictionaries. Unsupported values raise `SerializationError`.
- Restoration accepts omitted data, rejects unknown field names, converts lists back to tuples where the reflected default is a tuple, and wraps constructor `TypeError` as `SerializationError`. Dataclass defaults continue to apply to missing fields.
- Added six focused tests in `tests/test_components.py` for names, nested JSON conversion, omitted fields, serialization guards, unsupported values, tuple/default restoration, bad fields and constructor errors. Updated README and plan status. No package-root exports were added because §5.20 does not include these helpers in its stable root API.

### Commands and observed outcomes

- Read Step 011 and blueprint §5.2; inspected registry, error classes, existing component tests, plan status and staged state.
- Added tests first. `.venv/bin/python -m pytest tests/test_components.py -o addopts='' -q` failed at collection as expected because `component_from_dict` was not yet present.
- After implementation, `.venv/bin/python -m pytest tests -o addopts='' -q`: **72 passed in 0.25s**.

### Decisions and limitations

Mapping keys are converted with `str(key)` as specified. JSON conversion accepts Python scalar types, NumPy scalars, sequences, dictionaries and nested dataclass instances; NumPy arrays and other arbitrary objects raise `SerializationError`. Component class input is supported by `component_name`, while serialization requires an instance. Only `TypeError` from component construction is translated, matching §5.2.

### Verification and diff review

Check that only `simworld/registry.py`, `tests/test_components.py` and the README/plan status files changed in this step, that the pre-existing staged diff remains byte-for-byte unchanged, that exactly Steps 001–011 are checked, and that `git diff --check` passes. Review the final diff and record the actual results below.

## Step 012 — Add the three core data components

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 013 — Allocate generation-safe entity ids. **Phase 1:** in progress.

### Scope and files

- Added `simworld/components.py` with registered core `Position`, `Appearance` and `Parent` dataclasses. Position keeps its annotated numeric values without runtime coercion. Appearance includes the color widget, white RGB default and minimum size; Parent includes the entity picker metadata and zero sentinel.
- Exported `Position` and `Appearance` from the package root as required by §5.20. `Parent` remains available from `simworld.components`, matching the blueprint's explicit root-export exception.
- Added three focused checks in `tests/test_core_components.py` for registry metadata, integer and NumPy numeric preservation, and public exports. Updated README and plan status.

### Commands and observed outcomes

- Read Step 012, blueprint §5.4 and §5.20, current package exports, registry behavior and repository status. No applicable `AGENTS.md` was found.
- Added tests first. `.venv/bin/python -m pytest tests/test_core_components.py -o addopts='' -q` failed at collection as expected because `simworld.components` did not exist.
- After implementation, the same focused command passed: **3 passed in 0.16s**. `.venv/bin/python -m pytest tests -o addopts='' -q`: **75 passed in 0.36s**.

### Decisions and limitations

Metadata tooltips use concise descriptions because §5.4 specifies their presence but leaves exact text as ellipses. The component values remain plain dataclass data; validation and editor behavior are left to later systems.

### Verification and diff review

Confirm scope is limited to the core component module, required package exports, focused tests and README/plan status; preserve the staged diff; verify exactly Steps 001–012 are checked; run `git diff --check`; review the final diff.

## Step 013 — Allocate generation-safe entity ids

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 014 — Make allocation reversible and serializable. **Phase 1:** in progress.

- Added `simworld/ecs.py` with the integer Entity alias, 32-bit index helpers and EntityAllocator. New slots begin at generation 1; releasing a live id increments its generation and pushes its slot onto the free stack. Allocation reuses the most recently released slot. Allocators have independent state.
- Added safe liveness checks, live counts and diagnostics distinguishing invalid values, never-allocated slots/generations and despawned ids. Failed releases leave allocator state unchanged. Booleans are rejected as ids; negative and zero values are invalid. Decode helpers follow the blueprint's bit operations without adding validation.
- Exported `entity_index` and `entity_generation` from the package root per §5.20. Added 15 cases to `tests/test_ecs.py` covering id layout, LIFO reuse, stale generations, malformed inputs, repeated release, atomic failure and exports.
- Before edits, saved content hashes and staged diff to `/tmp/simworld-step013-baseline.json`; inspected blueprint §5.3, plans and guidance. No applicable `AGENTS.md` was found.
- Tests first: `.venv/bin/python -m pytest tests/test_ecs.py -o addopts='' -q` failed at collection with the expected missing `simworld.ecs` module. After implementation: **50 passed in 0.18s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **90 passed in 0.24s**.
- Updated README and plan status. Reversal, allocator serialization and command buffers remain for later steps; World is not introduced here. No contract deviations beyond explicitly rejecting bool values as ids.
- Final review: a stdlib snapshot comparison confirmed only the seven intended implementation/test/export/documentation files changed from this turn's baseline; existing Step 012 work and the staged diff were preserved. Verified exactly 13 checked steps and 181 pending. `git diff --check` passed without output; reviewed allocator code, error paths and focused tests.

## Step 014 — Make allocation reversible and serializable

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 015 — Introduce minimal World state. **Phase 1:** in progress.

- Added `revive` and `rollback_alloc` to `simworld/ecs.py`. Revive checks the released generation and free-stack top before restoring the original id. Allocation rollback removes a fresh final slot or returns a recycled slot to the free stack without advancing its generation.
- Added `to_dict` and classmethod `from_dict`, preserving generations, liveness and free-slot order in the specified three-list format. Both copy lists so returned data, input data and allocator state remain independent.
- Added seven tests in `tests/test_ecs.py`: exact fresh/recycled allocation undo, reverse-order release revival, the editor's release/revive/rollback sequence, invalid undo atomicity, JSON roundtrip with stale ids and next-allocation equivalence, and list ownership.
- Read Step 014 and blueprint §5.3; inspected repository guidance and saved this turn's content/staged baseline in `/tmp/simworld-step014-baseline.json`. No applicable `AGENTS.md` was found.
- Tests first: `.venv/bin/python -m pytest tests/test_ecs.py -o addopts='' -q` produced **7 failed, 50 passed in 0.40s**, all new cases failing because serialization methods were missing. After implementation the same command produced **57 passed in 0.24s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **97 passed in 0.25s**.
- LIFO remains a caller precondition, as in §5.3: state checks catch invalid revival and rollback of a non-final fresh slot, but there is no added operation-history stack to detect every possible out-of-order recycled rollback. The later editor command stack owns ordering. Restoration expects valid allocator data; broader save-format validation belongs to later persistence work. No World or command buffer was introduced.
- Updated README and plan status; final scope and staged-state review recorded below.
- Final review passed: baseline hashes limit this step to allocator implementation/tests plus four documentation files; prior work and staged state are preserved. Exactly 14 steps are checked and 180 pending. `git diff --check` passed without output. Reviewed validation-before-mutation paths, list copies and undo preconditions.

## Step 015 — Introduce minimal World state

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 016 — Implement entity creation and deletion. **Phase 1:** in progress.

- Added `simworld/world.py` with WorldSettings defaults from §5.7, a minimal World constructor, one seeded NumPy Generator per world, resource-backed clock/RNG properties, an independent EntityAllocator and insertion-ordered component-store dictionaries. `resources["settings"]` references the world's settings object. Exported World and WorldSettings from the package root.
- Unknown additional settings raise TypeError naming the invalid keys and valid options. Settings extra dictionaries have independent defaults; supplied extra mappings are shallow-copied. Time starts at 0.0, tick at 0 and dt at the configured value; resource dt can change independently of the configured default.
- Added seven checks in `tests/test_world.py` for defaults, overrides, diagnostics, seeded sequences, independent mutable state, clock properties and exports. Read Step 015/§5.7 and inspected guidance/status; saved pre-edit hashes and staged state in `/tmp/simworld-step015-baseline.json`. No applicable AGENTS.md was found.
- Tests first: `.venv/bin/python -m pytest tests/test_world.py -o addopts='' -q` failed at collection with the expected missing `simworld.world` module. After implementation: **7 passed in 0.15s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **104 passed in 0.27s**.
- Integration boundary: the documented constructor signature includes modules, but nonempty module requests explicitly raise NotImplementedError until module installation is built in Phase 4. They are never silently ignored. Layers, terrain, scheduler, commands, actions, events and spatial services are not initialized yet; they will be connected in their owning steps. Component/entity lifecycle methods remain for Step 016 onward. These temporary omissions follow Step 015's restriction against importing future subsystems.
- Updated README and plan status. Final scope and preservation checks follow below.
- Final review passed: baseline hashes limit changes to World implementation/exports/tests and four status documents; all prior work and staged state are preserved. Exactly 15 steps are checked and 179 pending. `git diff --check` passed without output. Reviewed constructor validation, settings/resource ownership and the absence of future-service imports.

## Step 016 — Implement entity creation and deletion

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 017 — Implement component access and mutation. **Phase 1:** in progress.

- Added World.spawn, despawn and the minimal is_alive allocator wrapper in `simworld/world.py`. Spawn resolves registered component names, rejects duplicate component types and invalid component arguments, validates optional unique string names, and only then allocates and stores the supplied component instances. Empty entities and empty-string names are supported.
- Initialized both name maps here because named creation and deletion require them. Public rename/name lookup APIs remain Step 019. Despawn checks liveness before mutation, removes the id from every component store and both name maps, and releases its slot. Store dictionaries remain available when emptied.
- Added ten cases in `tests/test_world.py`, including failure atomicity on a reusable allocator slot, duplicate components/names, unregistered objects and non-instance component arguments, survivor preservation, stale deletion after reuse, empty entities and independent worlds.
- Read Step 016 and §5.7; inspected guidance/status and saved baseline hashes/staged state to `/tmp/simworld-step016-baseline.json`. No applicable AGENTS.md was found; the initial working tree was clean.
- Tests first: `.venv/bin/python -m pytest tests/test_world.py -o addopts='' -q` produced **10 failed, 7 passed in 0.50s** because spawn was missing. After implementation: **17 passed in 0.16s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **114 passed in 0.29s**.
- Spawn accepts component instances; registered classes/names remain lookup inputs rather than stored data. Names must be strings or None. Spatial-hash removal is deferred until the spatial service exists; no future-service placeholders, component-access APIs or naming APIs were added. README and plan status updated.
- Final review passed: snapshot comparison limits this step to World lifecycle/tests plus four status documents, with staged state preserved. Exactly 16 steps are checked and 178 pending. `git diff --check` passed without output; reviewed validation-before-allocation and cleanup-before-slot-reuse paths.

## Step 017 — Implement component access and mutation

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 018 — Implement deterministic queries and counts. **Phase 1:** in progress.

- Added World.add/remove/get/try_get/has/components_of in `simworld/world.py`. Lookup/removal resolve registered component names, classes or instances; add accepts instances and replaces an existing component without changing its store position. Variadic add/remove validate every argument before mutating stores.
- Get uses direct store lookup first, then distinguishes stale ids from missing components. MissingComponentError includes the entity id, requested component and existing types. Optional reads check liveness first, returning None/False for dead or invalid ids. Has uses membership rather than component truthiness; components_of returns a new dictionary retaining original component references.
- Added 14 cases in `tests/test_world.py` for reference forms, replacement/removal, all-component membership, missing/stale diagnostics, malformed/dead ids, slot reuse, independent mapping results, atomic validation errors and false-valued components.
- Read Step 017/§5.7, guidance and status; saved baseline content/staged hashes in `/tmp/simworld-step017-baseline.json`. No applicable AGENTS.md was found. Preserved existing Step 016 changes.
- Tests first: `.venv/bin/python -m pytest tests/test_world.py -o addopts='' -q`: **14 failed, 17 passed in 0.61s**, reflecting missing access/mutation methods. After implementation: **31 passed in 0.22s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **128 passed in 0.31s**.
- Decisions for unspecified details: removing an absent registered component is harmless; add replaces components of the same registered name (later arguments win), and add/remove return None. Unknown component names still raise on live entities. Queries, counts and naming methods remain in their owning steps. README and plan status updated.
- Final review passed: baseline comparison confirms only component access/mutation, focused tests and four status documents changed this turn. Prior Step 016 work and staged state are preserved; exactly 17 steps are checked and 177 pending. `git diff --check` passed without output. Reviewed lookup/error ordering, validation-before-mutation and component identity preservation.

## Step 018 — Implement deterministic queries and counts

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 019 — Implement entity naming. **Phase 1:** in progress.

- Added World.query and its store/iterator helpers in `simworld/world.py`, following the §5.7 sketch: select the smallest requested store (first argument wins size ties), snapshot its items at query-call time, preserve argument order in returned tuples, apply any-type exclusions and recheck base membership before yielding. Includes the specified single-store fast path.
- Added entities as a fresh list of live ids in allocator slot order, using current generations and including empty entities. Count delegates component filters/exclusions to query; with no component arguments it returns the allocator's live count, as specified.
- Added ten cases in `tests/test_world.py` covering order/ties, tuple layout, exclusions/intersections, removal during iteration, snapshot timing, slot reuse, base/non-base removal, immediate errors, entity listing and counts.
- Read Step 018/§5.7 and checked guidance/status; saved baseline content and staged state in `/tmp/simworld-step018-baseline.json`. No applicable AGENTS.md was found. Earlier work is preserved.
- Tests first: `.venv/bin/python -m pytest tests/test_world.py -o addopts='' -q`: **10 failed, 31 passed in 0.64s**, due to missing query/entity listing methods. After implementation: **41 passed in 0.24s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **138 passed in 0.36s**.
- Query snapshots capture base component references, while other stores and exclusions are read during iteration, matching the blueprint sketch. Determinism here means stable store/slot ordering; concurrent mutation is not supported. Naming, prefabs and scheduling remain for later steps. Updated README and plan status.
- Final review passed: baseline comparison confirms only query/list/count implementation, focused tests and four status documents changed this turn; prior work and staged state are preserved. Exactly 18 steps are checked and 176 pending. `git diff --check` passed without output. Reviewed snapshot timing, tie-breaking, membership checks and current-generation id reconstruction.

## Step 019 — Implement entity naming

**Status:** complete. **Date:** 2026-10-30. **Next:** Step 020 — Implement prefab templates and overrides. **Phase 1:** in progress.

- Added World.set_name/entity/name_of in `simworld/world.py`. Renaming validates liveness, name type and uniqueness before changing either map. None removes a name, an unchanged name is a no-op and empty-string names remain supported. Existing spawn/despawn naming behavior is preserved.
- Entity lookup raises UnknownNameError with kind="entity" and known-name suggestions. Name_of checks liveness and returns None for an unnamed live entity. These clarify behavior not detailed in §5.7; set_name returns None, consistent with other mutations.
- Added eight cases in `tests/test_world.py`: rename/removal/lookup, same-name and empty-string behavior, duplicate/invalid edits without state changes, stale ids after slot reuse, and suggestions. No prefab or scheduler work was introduced.
- Read Step 019/§5.7 and name-error conventions, inspected guidance/status, and saved baseline hashes/staged state in `/tmp/simworld-step019-baseline.json`. No applicable AGENTS.md was found.
- Tests first: `.venv/bin/python -m pytest tests/test_world.py -o addopts='' -q`: **8 failed, 41 passed in 0.82s** for missing naming methods. After implementation: **49 passed in 0.24s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **146 passed in 0.41s**. README and plan status updated.
- Final review passed: baseline comparison limits changes to naming implementation/tests and four status documents, preserving prior work and staged state. Exactly 19 steps are checked and 175 pending. `git diff --check` passed without output. Reviewed validation-before-mutation, empty-name handling and generation checks on stale edits.

## Step 020 — Implement prefab templates and overrides

**Status:** complete. **Date:** 2026-10-31. **Next:** Step 021 — Define systems and registration context. **Phase 1:** in progress.

- Added World.define_prefab/spawn_prefab/prefabs and private builder helpers in `simworld/world.py`. Definitions normalize registered names/classes, copy field data and construct each component once to validate before publishing the template. Spawns copy templates, merge component-field dictionaries or dotted Component.field overrides, accept copied component-instance replacements, and remove types overridden with None before calling spawn.
- Added seven focused cases in `tests/test_prefabs.py` for partial defaults, mapping inputs, tuple restoration, field merging, instance replacement/removal/addition, mutable isolation, immediate definition failures, failed-spawn allocation safety and missing-prefab suggestions.
- Read Step 020/§5.7 and existing serialization contracts; inspected guidance/status and saved content/staged baseline in `/tmp/simworld-step020-baseline.json`. No applicable AGENTS.md was found. Previous work is preserved.
- Tests first: `.venv/bin/python -m pytest tests/test_prefabs.py -o addopts='' -q`: **7 failed in 0.59s**, because define_prefab was missing. After implementation the focused command produced **7 passed in 0.35s**. Extended the replacement case to cover a subsequent dotted override and rejection of an unknown field without changing the caller's instance.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **153 passed in 0.66s**.
- Decisions for unspecified details: redefining a prefab replaces it only after successful validation; prefabs returns a deep-copy snapshot; overrides apply in supplied order and merge at the component-field level, while dotted keys address Component.field. Arbitrary nested object-path traversal is not added. Mismatched component replacements are rejected. All building/override validation finishes before allocation; instance replacements are copied without serializing away runtime fields. Scheduling, active-world context and plugin helper exports remain for their owning steps. README and plan status updated.
- Final review passed: baseline comparison limits changes to prefab implementation/tests and four status documents, preserving prior work and staged state. Exactly 20 steps are checked and 174 pending. `git diff --check` passed without output. Reviewed copy boundaries, replacement validation and publish/allocation ordering.

## Step 021 — Define systems and registration context

**Status:** complete. **Date:** 2026-10-31. **Next:** Step 022 — Schedule systems in stable stages. **Phase 1:** in progress.

- Added the specified stack-based active_world/loading_into context to `simworld/registry.py`. Nested contexts route to the innermost world and unwind in finally, including when registration raises.
- Added `simworld/systems.py` with SystemDef fields from §5.8 and bare/called @system forms. The decorator preserves function identity, attaches SystemDef as __sim_system__, records docstrings and read/write tuples, and registers only when active_world is present. Base_order captures the original order when unspecified. Reads/writes remain descriptive.
- Added World.add_system/register for explicit registration, copying definitions to avoid sharing world-local enabled/order state with decorator metadata or other worlds, retaining the current module origin and rejecting duplicate names. Exported system from the package root. Plain functions can be passed to add_system; register currently accepts decorated functions and SystemDef values, with other extension kinds deferred.
- Added five tests in `tests/test_systems.py` for definition/decorator defaults, explicit and automatic registration, independent world-owned copies, nested/error context restoration, module origins and overrides.
- Read Step 021/§§5.2, 5.8 and inspected guidance/status; saved baseline content/staged state in `/tmp/simworld-step021-baseline.json`. No applicable AGENTS.md was found.
- Tests first: `.venv/bin/python -m pytest tests/test_systems.py -o addopts='' -q` failed at collection as expected because active_world did not exist. After implementation: **5 passed in 0.37s**.
- Regression command: `.venv/bin/python -m pytest tests -o addopts='' -q`: **158 passed in 0.61s**.
- Integration boundary: World temporarily holds registrations in _systems. Step 022 will connect Scheduler and stage validation, sequence assignment, ordering, caching and execution gating. Step 025 owns World.system and the run loop. No execution stubs, scheduling logic or event/action registration were introduced. This keeps the Step 021 registration surface usable without importing a future Scheduler. README and plan status updated.
- Final review passed: baseline comparison limits this turn to system metadata/context/registration, root export, focused tests and four status documents; prior work and staged state are preserved. Exactly 21 steps are checked and 173 pending, with Scheduler still deferred. `git diff --check` passed without output. Reviewed context unwinding, definition ownership and duplicate registration paths.
