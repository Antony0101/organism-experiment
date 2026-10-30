# simworld

A general-purpose 2D simulation engine and scene editor, being built incrementally
from [BLUEPRINT.md](BLUEPRINT.md).

## Current status

Steps 001–015 are complete and **Phase 0's scaffold gate has passed**: editable
installation, scaffold tests and imports outside the checkout were verified.
The engine error hierarchy, `component`, `prop`, `COMPONENTS`, `Position` and
`Appearance` are available through `simworld`; `Parent` and registry metadata
live in their respective modules. Entity allocation and stale-id checks live in
`simworld.ecs`, along with LIFO undo and allocator serialization. ID decoding
helpers are exported through `simworld`. `World` and `WorldSettings` provide
configuration, seeded randomness, resources and initial entity storage.
Phase 1 is in progress.
**Step 016 — Implement entity creation and deletion** in
[Phase 1](plans/01-ecs.md) is next.

Entity lifecycle APIs, built-in modules and the editor window arrive in later steps.
The declared `simworld-editor` entry point targets a future module and cannot
launch yet. The current import example is:

<!-- run -->
```python
import simworld
```

## Development setup

Python 3.10 or newer is required. Run these commands from the repository root
using a Python installation with `venv`/`ensurepip` support. Package installation
requires access to a package index or the corresponding local packages.

For a new checkout without `.venv`, create the environment and install the recorded
development versions:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

[requirements-dev.txt](requirements-dev.txt) includes `-e .[test]`: it installs this
checkout in editable mode with its test extra. Python source edits are available
without reinstalling. If `.venv` already exists from Step 003, use its Python for
the checks below; activation is optional.

To install using the dependency ranges in `pyproject.toml` instead of the recorded
pins, use `.venv/bin/python -m pip install -e '.[test]'` in a virtual environment.

The current environment was checked on Linux x86_64 with these versions:

| Tool or library | Version |
| --- | --- |
| Python | 3.12.3 |
| NumPy | 2.5.4 |
| pytest | 9.2.0 |
| pip | 24.0 |

These are local observations, not the blueprint's reference environment.
The requirements file pins installed packages; Python itself and isolated build
dependencies are not locked by it. Fresh-environment recreation from these pins
has not yet been verified. Seeded simulation comparisons will require matching
Python/NumPy versions once simulation is implemented.

## Verification

Run all current tests and check dependency consistency:

```bash
.venv/bin/python -m pytest tests
.venv/bin/python -m pip --no-cache-dir check
```

For only the executable documentation checks:

```bash
.venv/bin/python -m pytest tests/test_readme.py
```

README Python blocks marked with `<!-- run -->` run independently in temporary
directories with fresh namespaces. `clean_components` restores global component
registrations in the shared `COMPONENTS` registry, including decorated component
classes replaced by reloads. The complete `world` fixture is deferred to Step 071,
after built-ins.

## Package boundaries

- `simworld/`: engine and public API; runtime dependencies are Python's standard
  library and NumPy. Core code must not import the editor, Dear PyGui or pygame.
- `simworld/modules/`: optional simulation behavior, built on engine APIs.
- `simworld/editor/`: headless editor models built on the same engine. Dear PyGui
  imports belong only in the future `gui_dpg.py` and `gui_panels.py` front-end.
- `tests/`: fixtures and behavior checks. Optional pygame usage belongs in the
  future viewer example, rather than the engine or editor models.

Packaging declares `test`, `editor` and `viewer` extras. Only the test extra is
installed in the recorded environment. GUI dependencies and display/OpenGL
behavior remain unverified; no cross-platform support claim has been established.

## One step at a time

1. Read the next unchecked step in [the implementation plan](plans/README.md), its
   cited blueprint sections and [the progress log](plans/progress.md). Check git
   status and applicable repository guidance before editing; preserve existing
   work.
2. Implement only that numbered step. For new behavior, write a focused failing
   test, implement the smallest working change and review/refactor the patch.
   Documentation and setup steps use their stated direct checks.
3. Run the step's checks and relevant regressions. At a phase boundary, run the
   full accumulated suite and satisfy that phase's exit gate before advancing.
4. Record changed files, exact commands, observed results, skips and deviations
   in the progress log. Check a step only after its acceptance checks pass.
5. Report the result and next step, then stop. Continue when another step is
   requested; if several are explicitly requested, finish and verify each in
   sequence. Keep roadmap suggestions separate from the specified rebuild.

No commit, push or publication is required by this workflow. Work not exercised
must remain listed as unverified. Steps 010–012 add component metadata,
serialization and the core component types. Step 013 adds entity allocation;
Step 015 adds minimal World state; entity lifecycle and simulation execution
remain planned.
