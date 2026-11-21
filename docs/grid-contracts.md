# Grid contracts for later phases

These contracts are established by Phase 2, Steps 027–043, for simworld 0.1.0.
Later modules, pathfinding, persistence and editor work must preserve them. The
[developer guide](developer-guide.md) explains the APIs in depth; the
[progress log](../plans/progress.md) records the milestone's verification evidence.

## Coordinates and array layout

| Concept | Convention | Example |
| --- | --- | --- |
| World size | Width is x extent; height is y extent | A 5×3 world has five columns and three rows |
| World API arguments | `(x, y)` | `layer.get(3.8, 1.2)` reads cell `(3, 1)` |
| Cell coverage | Cell `(i, j)` covers `[i, i+1) × [j, j+1)` | `(3.8, 1.2)` belongs to column 3, row 1 |
| Cell center | `(i+0.5, j+0.5)` | The center of cell `(3, 1)` is `(3.5, 1.5)` |
| Scalar array | `data[y, x]`, shape `(height, width)` | The same cell is `layer.data[1, 3]` |
| Vector array | Shape `(height, width, *shape)` | A two-value cell has trailing shape `(2,)` |
| RGB array | `pixels[y, x, channel]` | Shape `(height, width, 3)` at render scale 1 |

The rendered origin is the top-left corner. Increasing x moves right; increasing
y moves down. Coordinate access floors rather than truncates: `-0.2` maps to
cell index -1 and is outside a World grid. Raw NumPy indexing has NumPy's own
negative-index and slicing semantics and bypasses coordinate/bounds handling and
write clamping. Keep these two access styles distinct.

Layer sampling interpolates from cell centers. Windows are clipped views into
the source array and return their `(x0, y0)` origin. Layer replacement installs
a fresh Layer/array at the same name; retained old layers and views keep their
old data. Reuse the current layer lookup when following replacements.

## Field evolution and metadata

Float writes through set/add clamp to configured bounds. Take returns the amount
actually removed and respects its floor, so consumers must use its return value.
Integer terrain data is not clamped by float-field bounds.

Diffusion uses pairwise exchanges with rate in `[0, 0.25]`. Both cells must be
inside the supplied mask; no mass crosses the grid border. Diffusion conserves
the total within floating-point tolerance. Decay multiplies values by
`exp(-rate*dt)` and intentionally reduces that total. Neither operation silently
clamps afterward; call clamp explicitly when needed.

Layer metadata includes name, dtype, default, trailing shape, min/max, decay and
diffusion rates, color, tooltip, kind and arbitrary props. World fields also
store regrow, regrow_by and diffuse_on in props. Replacement uses the new
definition's metadata. Existing metadata must remain meaningful when Phase 5
adds world persistence; a complete world file format is not implemented yet.

Worlds with `modules=()` still run core spatial synchronization. They do not
automatically decay, diffuse or regrow fields. Phase 4's resources module will
schedule field updates and split larger diffusion intervals into stable steps.

## Terrain edits and deferred pathfinding

Terrain definitions map names and nonnegative int16 ids to records. Redefining
the same name/id updates the record; conflicting identities fail. Property,
movement-cost and passability lookups refresh after definition changes. Removing
a definition does not repaint cells holding that id: terrain_at raises for an
undefined id, while cost/passability lookups fall back to 1/True and property
lookups use their requested default.

The current invalidation boundary is deliberate:

| Operation | Current behavior | Later pathfinding integration |
| --- | --- | --- |
| World set_terrain/fill_terrain | Paint, then call `_paths_changed()` | Invalidate cached paths immediately |
| Define/redefine/undefine terrain | Rebuild lookup tables, clear property caches and call the hook | Invalidate cached grids and successful/failed paths |
| Define/replace the named terrain layer | Install the new layer, then call the hook | Invalidate against the replacement plane |
| Direct terrain data or layer-mapping edits | Bypass the hook | Raw terrain changes are to be detected on the next tick by checksum synchronization |

`World._paths_changed()` is currently an empty extension hook. Phase 2 tests
verify that sanctioned edits notify it after mutation; they do not verify a path
cache. Phase 4 Steps 072–075 introduce costs, A*, optimality checks and caching.
Step 076 connects the hook and tick/checksum synchronization to the actual
PathFinder service. No pathfinding module, route execution or invalidation cache
exists at this milestone.

## Spatial ordering and synchronization

World lifecycle methods update indexed membership when Position is added,
replaced or removed and when entities spawn/despawn. Deferred commands use these
same paths when applied. Nearby results sort by `(distance, entity id)` and can
require component types. Querying around an entity excludes that entity.

Direct edits to Position coordinates need sync_spatial when crossing buckets;
nearby does not sync implicitly. Core systems sync at sense order -100 and late
order 100. Edits after the late sync need another explicit sync before relying
on membership. Rendering reads current Position data directly.

## Reproduce the milestone image

Run the following complete example from the repository root with the installed
development environment. It writes a 20×20 RGB PNG using stdlib and NumPy only.
The blue pool is on the left, a gray wall with a gap runs down the middle, a gold
field lies at the upper right, and brown mud occupies the lower right. White and
red entity markers provide asymmetric coordinate checks.

```python
from pathlib import Path

from simworld import Appearance, Position, World
from simworld.render import render_rgb, save_frame

world = World(20, 20, seed=43, modules=())
world.define_terrain("ground", 1, color=(60, 110, 50), char=".", fertility=1)
world.define_terrain("water", 2, passable=False, color=(35, 90, 185), char="~")
world.define_terrain("wall", 3, passable=False, color=(100, 100, 100), char="#")
world.define_terrain("mud", 4, move_cost=2, color=(140, 100, 60), char="m")
world.fill_terrain("ground")
for y in range(4, 9):
    for x in range(2, 8):
        world.set_terrain(x, y, "water")
for y in range(2, 18):
    if y not in (9, 10):
        world.set_terrain(10, y, "wall")
for y in range(12, 17):
    for x in range(13, 18):
        world.set_terrain(x, y, "mud")

food = world.define_field("food", max=10, diffusion=0.2,
                          color=(240, 210, 40), tooltip="Food overlay")
for y in range(3, 8):
    for x in range(13, 18):
        food.set(x, y, 10)
food.diffuse(food.diffusion_rate, world.terrains.mask("ground"))
world.spawn(Position(2.5, 1.5), Appearance(color=(255, 255, 255)))
world.spawn(Position(17.5, 16.5), Appearance(color=(220, 40, 40)))
world.step()

pixels = render_rgb(world)
assert pixels.shape == (20, 20, 3) and str(pixels.dtype) == "uint8"
assert tuple(pixels[1, 2]) == (255, 255, 255)
assert tuple(pixels[16, 17]) == (220, 40, 40)
assert tuple(pixels[4, 2]) == (35, 90, 185)
assert tuple(pixels[2, 10]) == (100, 100, 100)
assert tuple(pixels[9, 10]) == (60, 110, 50)
assert tuple(pixels[5, 15]) == (168, 170, 44)
path = Path("docs/artifacts/phase-2-grid.png")
path.parent.mkdir(parents=True, exist_ok=True)
save_frame(world, path)
```

The saved [milestone PNG](artifacts/phase-2-grid.png) is intentionally one pixel
per cell. A nearest-neighbor enlargement was also inspected locally to check
placement, orientation, the wall opening and overlay/marker colors. Rendering
and encoding do not require Pillow, pygame or Dear PyGui.

## Verification boundary

The accumulated suite covers layer access/arithmetic, conservative diffusion,
terrain lookups and notifications, spatial results against independent scans,
seeded generation and PNG chunk/CRC/pixel decoding. The saved image supplements
these numeric checks with visual inspection. This is a headless engine milestone;
interactive GUI verification belongs to the later editor phases.

Step 043's accumulated run passed all **532 tests** with no skips or failures:

```bash
.venv/bin/python -m pytest tests -q -o addopts=''
```

The image was also generated in a fresh process whose import finder rejected
PIL, pygame and dearpygui. None appeared in sys.modules afterward. An independent
stdlib decoder checked the PNG signature, 20×20 header, chunk order and CRCs,
filter-zero rows and exact decompressed RGB pixels. This verifies headless output
in addition to the numerical suite.

The recorded environment is Python 3.12.3, NumPy 2.5.4 and pytest 9.2.0. Later
runtime versions can change reproducibility; this milestone does not certify
every interpreter allowed by the package metadata.
