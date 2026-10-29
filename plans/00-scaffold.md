# Phase 0: Scaffold and environment

Steps **001–007** (7 steps). Source: [BLUEPRINT.md](../BLUEPRINT.md), §§2, 4, 8 Phase 0, 9.2, 9.4.

[Execution rules and index](README.md). Complete the preceding phase gate before starting this file. Within this file, each step depends on the preceding numbered step; Step 001 has no predecessor.

**Phase exit gate:** Editable installation and the initial README test pass; actual environment versions are recorded.

Steps 001–007 are complete and this phase's exit gate has passed. Step 008 in Phase 1 is next. Check a box only after implementing its change and satisfying its verification. Each numbered item is one implementation session, including its focused tests and review. See [progress and evidence](progress.md).

### Step 001 — Record the rebuild baseline

- [x] **Change:** Inspect repository status and available Python/display tools; record existing deletions and the new simworld package layout in plans/progress.md without restoring legacy sim_sandbox files.
- **Verify:** The baseline distinguishes existing user changes from implementation changes; no deleted files were recovered.
- **Blueprint:** §§1–4, 8 Phase 0.

### Step 002 — Create the packaging skeleton

- [x] **Change:** Add pyproject.toml from §2.1, package directories and minimal __init__.py files; add README.md with one self-contained import block.
- **Verify:** Package metadata declares NumPy alone at runtime, optional extras and the future editor entry point; import simworld succeeds from the checkout.
- **Blueprint:** §§2.1, 4.1.

### Step 003 — Create and record the development environment

- [x] **Change:** Create .venv, install editable test extras and record Python, NumPy and pytest versions plus exact dependency pins in a development environment file.
- **Verify:** .venv/bin/python -m pip check succeeds; actual versions are recorded without assuming the reference versions exist locally.
- **Blueprint:** §§2.2, 8 Phase 0.

### Step 004 — Execute the first documentation example

- [x] **Change:** Add tests/__init__.py and test_readme.py to discover and execute marked Python blocks independently in temporary directories; require one block initially.
- **Verify:** The import example passes; a temporary deliberately broken block fails and is reverted before completion.
- **Blueprint:** §9.4.

### Step 005 — Establish isolated test fixtures

- [x] **Change:** Add clean_components with a lazy registry import so the scaffold remains runnable; defer the complete world fixture until built-ins exist.
- **Verify:** Scaffold tests collect without importing missing World/registry implementations; the deferred fixture is explicitly tracked.
- **Blueprint:** §§9.2, 12.2 Phase 0.

### Step 006 — Document the incremental working agreement

- [x] **Change:** Record install/test commands, package boundaries and the one-step execution procedure in README.md and plans/progress.md.
- **Verify:** A new contributor can find the next step, verification command and current limitations without reading chat history.
- **Blueprint:** §§2.3, 8, 12.1.

### Step 007 — Verify the scaffold milestone

- [x] **Change:** Run editable installation, the initial pytest suite and an import from outside the repository; record exact output and changed files.
- **Verify:** Installation and tests pass; versions and any missing optional tools are documented; no later-phase implementation was added.
- **Blueprint:** §8 Phase 0.

Next phase: [Errors, registries, ECS and scheduling](01-ecs.md).
