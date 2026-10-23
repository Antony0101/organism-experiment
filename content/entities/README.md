# Editable Entity Projects

The Entity Studio stores each reusable entity in its own folder here:

```text
my_entity/
├── entity.json
├── behavior.py
└── assets/
```

Open the editor from the Project Hub or with
`python -m sim_sandbox --entity-editor`. Invalid or newer-schema
projects are reported without modifying their files. Archived projects are
moved to the hidden `.trash` directory and can be restored manually.

If the library is empty, use **Create First Entity**. An ID such as
`energy_orb` becomes the immutable folder name, while the display name can be
edited later. Opening the **Preview** tab validates and starts the current draft
automatically; **Save** persists later changes to its project files.

Entity manifests use schema version 2. In addition to appearance and declared
properties, they store searchable tags and an ordered `behaviors` attachment
list. Schema-1 projects load with empty tags/attachments and are written as
schema 2 on their next save. Unknown future schemas are only reported; their
files are not modified.

The lifecycle order for a saved entity is:

1. Attached component `init` callbacks from top to bottom.
2. The entity project's `behavior.py` `init` callback.
3. Each tick, component `update` callbacks from top to bottom.
4. The entity project's custom `update` callback.
5. On removal, the custom `delete` callback followed by component `delete`
   callbacks from bottom to top.

Use the Behaviors tab to add presets or projects from `../behaviors`, configure
parameters, reorder attachments, and open a component in Behavior Studio.
Missing required properties can be added with their declared defaults.

All custom Python is trusted local code. Preview execution is isolated from UI
crashes and timeouts, but it is not an operating-system security sandbox.
