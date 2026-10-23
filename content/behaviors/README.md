# Editable Behavior Projects

Behavior Studio stores each reusable custom component in its own folder:

```text
my_behavior/
├── behavior.json
└── behavior.py
```

Open the studio from the Project Hub or with:

```powershell
python -m sim_sandbox --behavior-editor
```

The packaged library contains 24 read-only presets. Use **Duplicate** before
editing one; a custom project cannot reuse a built-in ID. Archive is recoverable
through `.trash` and is blocked while entity projects reference the behavior.

`behavior.json` declares the display metadata, category, typed parameters,
private runtime state, required entity properties/behaviors, multiplicity,
exclusive group, and capabilities it writes. Supported field types are
`float`, `int`, `bool`, `str`, `color`, and `vec2`.

`behavior.py` can expose any of these callbacks:

```python
def init(behavior, entity, world):
    pass

def update(behavior, entity, world, dt):
    pass

def delete(behavior, entity, world):
    pass
```

`behavior.config` is validated, read-only attachment configuration.
`behavior.state` is mutable state private to that attachment instance. Do not
add or remove state keys at runtime; declare them in the manifest. Private
state participates in deterministic hashes, preview snapshots, and inspection
when its Inspector flag is enabled.

The Preview tab supports a generated compatible host or an existing entity
project. Fixture rows can add saved entities or lightweight tagged markers,
up to 50 instances per row. Apply validates and executes the in-memory draft;
Save atomically writes it.

Behavior Python is trusted local code. The editor worker protects the UI from
exceptions and most infinite loops, but it is not a security sandbox and code
may still access the filesystem or network.
