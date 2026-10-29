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
