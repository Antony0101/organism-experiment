# simworld

A general-purpose 2D simulation engine and scene editor, being built incrementally
from [BLUEPRINT.md](BLUEPRINT.md). The package skeleton is available; simulation
features and the editor window will be added in later steps.

From the repository root:

<!-- run -->
```python
import simworld
```

Python 3.10 or newer is required. Packaging declares NumPy as the only runtime
dependency, with optional `test`, `editor` and `viewer` extras. The editor launch
entry point is reserved in package metadata; its implementation is still planned.

See [the implementation plan](plans/README.md) and [progress log](plans/progress.md)
for the current step and verification evidence.
