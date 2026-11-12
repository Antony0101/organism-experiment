"""Terrain definitions and per-cell cost, passability and property lookups."""

from __future__ import annotations

import dataclasses as dc
from math import isfinite
from operator import index

import numpy as np

from .errors import DuplicateNameError, SimWorldError, UnknownTerrainError
from .layers import Layer


TERRAIN_LAYER = "terrain"

__all__ = ["TERRAIN_LAYER", "Terrain", "TerrainRegistry"]


@dc.dataclass
class Terrain:
    """The metadata associated with one terrain id stored in grid cells."""

    name: str
    id: int
    move_cost: float = 1.0
    passable: bool = True
    color: tuple[int, int, int] = (128, 128, 128)
    props: dict = dc.field(default_factory=dict)

    def to_dict(self) -> dict:
        """Copy terrain metadata, using a list for the RGB color."""
        data = dc.asdict(self)
        data["color"] = list(self.color)
        return data


class TerrainRegistry:
    """Associate unique names and ids with terrain records for a grid owner."""

    def __init__(self, world):
        self._world = world
        self.by_name: dict[str, Terrain] = {}
        self.by_id: dict[int, Terrain] = {}
        self._mc: list[float] = [1.0]
        self._pass: list[bool] = [True]
        self.move_cost_lut = np.array(self._mc, dtype=float)
        self.passable_lut = np.array(self._pass, dtype=bool)
        self._prop_cache: dict[tuple[str, float], np.ndarray] = {}

    def _rebuild(self) -> None:
        """Refresh definition-derived tables and notify an owner's path hook."""
        size = max(self.by_id, default=0) + 1
        self._mc = [1.0] * size
        self._pass = [True] * size
        for terrain_id, terrain in self.by_id.items():
            self._mc[terrain_id] = terrain.move_cost
            self._pass[terrain_id] = terrain.passable
        self.move_cost_lut = np.array(self._mc, dtype=float)
        self.passable_lut = np.array(self._pass, dtype=bool)
        self._prop_cache.clear()
        # Standalone owners may omit this hook; World supplies it in Step 034.
        paths_changed = getattr(self._world, "_paths_changed", None)
        if paths_changed is not None:
            paths_changed()

    def define(self, name, id, move_cost=1.0, passable=True, color=(128, 128, 128), **props) -> Terrain:
        """Validate and publish a terrain, permitting updates of the same name/id."""
        if not isinstance(name, str):
            raise TypeError("Terrain name must be a string.")
        try:
            terrain_id = index(id)
        except TypeError:
            raise SimWorldError("Terrain id must be an integer in [0, 32767].") from None
        if isinstance(id, bool) or not 0 <= terrain_id <= np.iinfo(np.int16).max:
            raise SimWorldError("Terrain id must be an integer in [0, 32767].")
        try:
            cost = float(move_cost)
        except (TypeError, ValueError):
            raise SimWorldError("Terrain move_cost must be a finite number.") from None
        passable = bool(passable)
        if not isfinite(cost) or (passable and cost <= 0):
            raise SimWorldError("Terrain move_cost must be finite and positive for passable terrain.")
        try:
            rgb = tuple(index(channel) for channel in color)
        except TypeError:
            raise SimWorldError("Terrain color must be an RGB triple of integers in [0, 255].") from None
        if len(rgb) != 3 or any(channel < 0 or channel > 255 for channel in rgb):
            raise SimWorldError("Terrain color must be an RGB triple of integers in [0, 255].")

        previous = self.by_name.get(name)
        if previous is not None and previous.id != terrain_id:
            raise DuplicateNameError(f"Terrain {name!r} already uses id {previous.id}.")
        owner = self.by_id.get(terrain_id)
        if owner is not None and owner.name != name:
            raise DuplicateNameError(f"Terrain id {terrain_id} already belongs to {owner.name!r}.")
        terrain = Terrain(name, terrain_id, cost, passable, rgb, dict(props))
        self.by_name[name] = terrain
        self.by_id[terrain_id] = terrain
        self._rebuild()
        return terrain

    def undefine(self, name) -> Terrain:
        """Remove a named definition without rewriting cells that hold its id."""
        try:
            terrain = self.by_name[name]
        except KeyError:
            raise UnknownTerrainError(name, self.names()) from None
        del self.by_name[name]
        del self.by_id[terrain.id]
        self._rebuild()
        return terrain

    def get(self, key: str | int) -> Terrain:
        """Find a terrain by registered name or integer id."""
        if isinstance(key, str):
            items = self.by_name
        else:
            if isinstance(key, bool):
                raise TypeError("Terrain lookup requires a name or integer id.")
            try:
                key = index(key)
            except TypeError:
                raise TypeError("Terrain lookup requires a name or integer id.") from None
            items = self.by_id
        try:
            return items[key]
        except KeyError:
            raise UnknownTerrainError(key, self.names()) from None

    def id_of(self, name) -> int:
        return self.get(name).id

    def names(self) -> list[str]:
        """Return a fresh name list sorted by terrain id."""
        return [self.by_id[key].name for key in sorted(self.by_id)]

    @property
    def layer(self) -> Layer | None:
        return self._world.layers.get(TERRAIN_LAYER)

    def ensure_layer(self) -> Layer:
        """Create an int16 terrain grid once, preserving any existing layer."""
        layer = self.layer
        if layer is None:
            layer = Layer(
                TERRAIN_LAYER, self._world.width, self._world.height,
                dtype=np.int16, default=min(self.by_id) if self.by_id else 0,
                tooltip="terrain id per cell", kind="terrain",
            )
            self._world.layers[TERRAIN_LAYER] = layer
        return layer

    def at(self, x, y) -> Terrain:
        """Return the defined record at a floored world coordinate."""
        return self.get(self.ensure_layer().get(x, y))

    def move_cost_at(self, x, y) -> float:
        """Read a cell's movement cost, defaulting to one for undefined ids."""
        terrain_id = self.ensure_layer().get(x, y)
        return self._mc[terrain_id] if 0 <= terrain_id < len(self._mc) else 1.0

    def passable_at(self, x, y) -> bool:
        """Read a cell's passability, defaulting to True for undefined ids."""
        terrain_id = self.ensure_layer().get(x, y)
        return self._pass[terrain_id] if 0 <= terrain_id < len(self._pass) else True

    def _lookup_grid(self, lut: np.ndarray, default) -> np.ndarray:
        """Gather a fresh grid without indexing outside a table or wrapping ids."""
        ids = self.ensure_layer().data
        valid = (ids >= 0) & (ids < len(lut))
        result = np.full(ids.shape, default, dtype=lut.dtype)
        result[valid] = lut[ids[valid]]
        return result

    def move_cost_grid(self) -> np.ndarray:
        return self._lookup_grid(self.move_cost_lut, 1.0)

    def passable_grid(self) -> np.ndarray:
        return self._lookup_grid(self.passable_lut, True)

    def prop_grid(self, prop, default=0.0) -> np.ndarray:
        """Gather numeric props, caching their id table until definitions change."""
        default = float(default)
        key = (prop, default)
        lut = self._prop_cache.get(key)
        if lut is None:
            lut = np.full(len(self._mc), default, dtype=float)
            for terrain_id, terrain in self.by_id.items():
                lut[terrain_id] = terrain.props.get(prop, default)
            self._prop_cache[key] = lut
        return self._lookup_grid(lut, default)

    def mask(self, names) -> np.ndarray:
        """Select cells belonging to a terrain name or iterable of names."""
        if isinstance(names, str):
            names = (names,)
        ids = [self.id_of(name) for name in names]
        return np.isin(self.ensure_layer().data, ids)
