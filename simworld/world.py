"""World settings and the shared state used by simulation services."""

from __future__ import annotations

import dataclasses as dc
import typing as t
from collections.abc import Mapping
from copy import deepcopy

import numpy as np

from .ecs import INDEX_BITS, CommandBuffer, Entity, EntityAllocator
from .errors import (
    ConfigError, DuplicateNameError, MissingComponentError, NotAComponentError,
    SerializationError, SimWorldError, UnknownNameError, UnknownPrefabError,
)
from .registry import component_from_dict, component_name, loading_into
from .layers import Layer, LayerStore
from .systems import Scheduler, SystemDef, system as system_decorator
from .terrain import TERRAIN_LAYER, Terrain, TerrainRegistry


__all__ = ["World", "WorldSettings"]


@dc.dataclass
class WorldSettings:
    """Configuration retained by a world and its eventual save data."""

    width: int = 64
    height: int = 64
    seed: int = 0
    dt: float = 1.0
    cell_size: float = 8.0
    energy_component: str = "Energy"
    default_speed: float = 1.0
    shuffle_actions: bool = True
    extra: dict = dc.field(default_factory=dict)


class World:
    """Own simulation settings, grid services, entities and scheduled systems."""

    def __init__(
        self, width=64, height=64, *, seed=0, dt=1.0, modules=(),
        cell_size=8.0, extra=None, **settings,
    ):
        explicit = {"width", "height", "seed", "dt", "cell_size", "extra"}
        valid = {field.name for field in dc.fields(WorldSettings)} - explicit
        unknown = settings.keys() - valid
        if unknown:
            raise TypeError(
                f"Unknown world settings: {', '.join(sorted(unknown))}. "
                f"Valid additional settings: {', '.join(sorted(valid))}."
            )
        if modules:
            raise NotImplementedError("World module installation is not implemented yet.")

        self.settings = WorldSettings(
            width=width, height=height, seed=seed, dt=dt, cell_size=cell_size,
            extra={} if extra is None else dict(extra), **settings,
        )
        self.resources: dict[str, t.Any] = {
            "time": 0.0,
            "tick": 0,
            "dt": dt,
            "rng": np.random.default_rng(seed),
            "settings": self.settings,
        }
        self.layers = LayerStore()
        self.terrains = TerrainRegistry(self)
        self._alloc = EntityAllocator()
        self._stores: dict[str, dict[Entity, t.Any]] = {}
        self._names: dict[str, Entity] = {}
        self._entity_names: dict[Entity, str] = {}
        self._prefabs: dict[str, dict] = {}
        self.commands = CommandBuffer(self)
        self.scheduler = Scheduler(self)
        self._systems = self.scheduler.systems
        self._current_module: str | None = None

    def define_layer(
        self, name, dtype=float, default=0, *, shape=(), min=None, max=None,
        decay=0.0, diffusion=0.0, color=None, tooltip="", kind="layer",
        replace=False, **props,
    ) -> Layer:
        """Allocate a named grid; replacing an existing name requires opt-in."""
        if name in self.layers and not replace:
            raise DuplicateNameError(
                f"A layer named {name!r} already exists. Pass replace=True to replace it."
            )
        layer = Layer(
            name, self.width, self.height, dtype=dtype, default=default, shape=shape,
            min=min, max=max, decay=decay, diffusion=diffusion, color=color,
            tooltip=tooltip, kind=kind, props=props,
        )
        self.layers[name] = layer
        if name == TERRAIN_LAYER:
            self._paths_changed()
        return layer

    def define_field(
        self, name, *, initial=0.0, min=0.0, max=None, decay=0.0, diffusion=0.0,
        regrow=0.0, regrow_by=None, diffuse_on=None, color=None, tooltip="",
        replace=False, **props,
    ) -> Layer:
        """Define a float field and validate its future regrowth prerequisites."""
        if regrow and max is None:
            raise ConfigError(f"Field {name!r} needs max when regrow is nonzero.")
        if regrow_by is not None and not any(
            regrow_by in terrain.props for terrain in self.terrains.by_id.values()
        ):
            raise ConfigError(
                f"Field {name!r} regrow_by property {regrow_by!r} is not defined by any terrain."
            )
        return self.define_layer(
            name, dtype=float, default=initial, min=min, max=max, decay=decay,
            diffusion=diffusion, color=color, tooltip=tooltip, kind="field",
            replace=replace, regrow=regrow, regrow_by=regrow_by,
            diffuse_on=diffuse_on, **props,
        )

    def define_terrain(
        self, name, id, move_cost=1.0, passable=True, color=(128, 128, 128), **props,
    ) -> Terrain:
        """Define terrain metadata without allocating or repainting the grid."""
        return self.terrains.define(name, id, move_cost, passable, color, **props)

    def terrain_at(self, x, y) -> Terrain:
        return self.terrains.at(x, y)

    def set_terrain(self, x, y, name) -> None:
        """Paint one floored cell and notify the path-invalidation hook."""
        terrain_id = self.terrains.id_of(name)
        self.terrains.ensure_layer().set(x, y, terrain_id)
        self._paths_changed()

    def fill_terrain(self, name) -> None:
        """Paint the whole terrain plane and notify the path-invalidation hook."""
        terrain_id = self.terrains.id_of(name)
        self.terrains.ensure_layer().fill(terrain_id)
        self._paths_changed()

    def _paths_changed(self) -> None:
        """Terrain-change extension hook; path-cache integration is Step 076."""

    def add_system(self, fn_or_SystemDef, **overrides) -> SystemDef:
        """Register a world-owned copy of a definition or function's metadata."""
        if isinstance(fn_or_SystemDef, SystemDef):
            definition = fn_or_SystemDef
        elif callable(fn_or_SystemDef):
            definition = getattr(fn_or_SystemDef, "__sim_system__", None)
            if definition is None:
                definition = SystemDef(
                    name=fn_or_SystemDef.__name__, fn=fn_or_SystemDef,
                    doc=(fn_or_SystemDef.__doc__ or "").strip(),
                )
        else:
            raise TypeError("add_system() expects a function or SystemDef.")
        registered = dc.replace(definition, **overrides)
        if self._current_module is not None:
            registered.module = self._current_module
        self.scheduler.add(registered)
        return registered

    def register(self, *objs):
        """Explicitly register systems decorated outside a loading context."""
        for obj in objs:
            if not isinstance(obj, SystemDef) and not hasattr(obj, "__sim_system__"):
                raise TypeError("register() currently expects @system functions or SystemDef values.")
            self.add_system(obj)
        return self

    def system(self, *, stage="update", order=0, reads=(), writes=(), name=None, every=1):
        """Decorate and immediately register a system into this world."""
        def decorate(fn):
            with loading_into(self):
                return system_decorator(
                    fn, stage=stage, order=order, reads=reads, writes=writes,
                    name=name, every=every,
                )
        return decorate

    def enable_system(self, name, enabled=True) -> None:
        self.scheduler.set_enabled(name, enabled)

    def disable_system(self, name) -> None:
        self.enable_system(name, False)

    def step(self, dt=None) -> None:
        """Run one scheduled pass, then advance the clock on success."""
        previous_dt = self.dt
        step_dt = previous_dt if dt is None else dt
        self.resources["dt"] = step_dt
        try:
            self.scheduler.run_step()
            self.resources["time"] += step_dt
            self.resources["tick"] += 1
        finally:
            self.resources["dt"] = previous_dt

    def run(self, steps, dt=None, callback=None) -> World:
        """Run up to steps passes; call callback(world) after each completed step."""
        for _ in range(steps):
            self.step(dt=dt)
            if callback is not None and callback(self) is False:
                break
        return self

    def spawn(self, *components, name=None) -> Entity:
        """Validate and attach component instances to a newly allocated entity."""
        prepared = self._prepare_spawn(components, name)
        entity = self._alloc.alloc()
        for registered_name, comp in prepared.items():
            self._stores.setdefault(registered_name, {})[entity] = comp
        if name is not None:
            self._names[name] = entity
            self._entity_names[entity] = name
        return entity

    def _prepare_spawn(self, components, name) -> dict:
        """Validate a complete spawn before changing stores or name maps."""
        prepared = {}
        for comp in components:
            registered_name = component_name(comp)
            if isinstance(comp, (str, type)):
                raise NotAComponentError("spawn() expects component instances, not names or classes.")
            if registered_name in prepared:
                raise SimWorldError(f"spawn() got two {registered_name!r} components.")
            prepared[registered_name] = comp
        if name is not None:
            if not isinstance(name, str):
                raise TypeError("Entity name must be a string or None.")
            if name in self._names:
                raise DuplicateNameError(f"An entity named {name!r} already exists.")

        return prepared

    def _finish_spawn(self, e: Entity, components, name) -> None:
        """Attach a queued spawn to its already reserved entity id."""
        self._alloc.check(e)
        prepared = self._prepare_spawn(components, name)
        self.add(e, *prepared.values())
        self.set_name(e, name)

    def despawn(self, e: Entity) -> None:
        """Remove a live entity's components and name, then release its slot."""
        self._alloc.check(e)
        for store in self._stores.values():
            store.pop(e, None)
        name = self._entity_names.pop(e, None)
        if name is not None:
            self._names.pop(name, None)
        self._alloc.release(e)

    def is_alive(self, e) -> bool:
        return self._alloc.is_alive(e)

    def set_name(self, e: Entity, name) -> None:
        """Assign a unique name to a live entity, or remove its name with None."""
        self._alloc.check(e)
        if name is not None:
            if not isinstance(name, str):
                raise TypeError("Entity name must be a string or None.")
            owner = self._names.get(name)
            if owner is not None and owner != e:
                raise DuplicateNameError(f"An entity named {name!r} already exists.")
        previous = self._entity_names.get(e)
        if previous == name:
            return
        if previous is not None:
            del self._names[previous]
            del self._entity_names[e]
        if name is not None:
            self._names[name] = e
            self._entity_names[e] = name

    def entity(self, name: str) -> Entity:
        """Look up an entity by name, suggesting known names on a miss."""
        if not isinstance(name, str):
            raise TypeError("Entity lookup name must be a string.")
        try:
            return self._names[name]
        except KeyError:
            raise UnknownNameError(name, self._names, kind="entity") from None

    def name_of(self, e: Entity) -> str | None:
        """Return a live entity's name, or None when it is unnamed."""
        self._alloc.check(e)
        return self._entity_names.get(e)

    def define_prefab(self, name, components: Mapping) -> None:
        """Validate a partial component template before storing an independent copy."""
        if not isinstance(name, str):
            raise TypeError("Prefab name must be a string.")
        if not isinstance(components, Mapping):
            raise TypeError("Prefab components must be a mapping.")
        prepared = {}
        for comp, data in components.items():
            registered_name = component_name(comp)
            if registered_name in prepared:
                raise SimWorldError(f"Prefab got two {registered_name!r} components.")
            if not isinstance(data, Mapping):
                raise SerializationError(f"Prefab data for {registered_name!r} must be a mapping.")
            copied = deepcopy(dict(data))
            component_from_dict(registered_name, copied)
            prepared[registered_name] = copied
        self._prefabs[name] = prepared

    @property
    def prefabs(self) -> dict:
        """Return an independent snapshot of this world's prefab templates."""
        return deepcopy(self._prefabs)

    def spawn_prefab(self, name, *, entity_name=None, **overrides) -> Entity:
        """Build independent components, apply overrides, then spawn an entity."""
        return self.spawn(*self._prefab_components(name, overrides), name=entity_name)

    def _prefab_components(self, name, overrides):
        try:
            spec = deepcopy(self._prefabs[name])
        except KeyError:
            raise UnknownPrefabError(name, self._prefabs) from None
        for key, value in overrides.items():
            comp, dot, field = key.partition(".")
            registered_name = component_name(comp)
            if dot:
                current = spec.get(registered_name, {})
                spec[registered_name] = self._merge_prefab_fields(current, {field: value})
            elif value is None:
                spec.pop(registered_name, None)
            elif isinstance(value, Mapping):
                current = spec.get(registered_name, {})
                spec[registered_name] = self._merge_prefab_fields(current, value)
            else:
                if isinstance(value, (str, type)) or component_name(value) != registered_name:
                    raise SimWorldError(f"Override for {registered_name!r} must be an instance of that component.")
                spec[registered_name] = deepcopy(value)
        return [component_from_dict(comp, data) if isinstance(data, dict) else data
                for comp, data in spec.items()]

    @staticmethod
    def _merge_prefab_fields(current, updates):
        """Merge field overrides into copied template data or a copied replacement instance."""
        if isinstance(current, dict):
            current.update(deepcopy(dict(updates)))
            return current
        fields = {field.name: field for field in dc.fields(current)}
        for name, value in updates.items():
            if name not in fields:
                raise SerializationError(
                    f"Unknown field {name!r}. Valid fields: {', '.join(fields)}."
                )
            copied = deepcopy(value)
            if isinstance(copied, list) and isinstance(fields[name].default, tuple):
                copied = tuple(copied)
            try:
                setattr(current, name, copied)
            except (AttributeError, TypeError) as exc:
                raise SerializationError(f"Could not override field {name!r}: {exc}") from exc
        return current

    def add(self, e: Entity, *components) -> None:
        """Attach or replace component instances after validating all arguments."""
        self._alloc.check(e)
        prepared = []
        for comp in components:
            name = component_name(comp)
            if isinstance(comp, (str, type)):
                raise NotAComponentError("add() expects component instances, not names or classes.")
            prepared.append((name, comp))
        for name, comp in prepared:
            self._stores.setdefault(name, {})[e] = comp

    def remove(self, e: Entity, *components) -> None:
        """Remove registered component types; absent components are harmless."""
        self._alloc.check(e)
        names = [component_name(comp) for comp in components]
        for name in names:
            store = self._stores.get(name)
            if store is not None:
                store.pop(e, None)

    def get(self, e: Entity, comp):
        """Return a component, distinguishing a missing component from a stale id."""
        name = component_name(comp)
        # Numeric dictionary keys can compare equal even when their types differ.
        if not isinstance(e, int) or isinstance(e, bool):
            self._alloc.check(e)
        try:
            return self._stores.get(name, {})[e]
        except (KeyError, TypeError):
            self._alloc.check(e)
        known = ", ".join(self.components_of(e)) or "none"
        raise MissingComponentError(f"Entity {e} has no component {name!r} (it has: {known}).")

    def try_get(self, e: Entity, comp):
        """Return None for a dead entity or an absent registered component."""
        if not self.is_alive(e):
            return None
        name = component_name(comp)
        return self._stores.get(name, {}).get(e)

    def has(self, e: Entity, *comps) -> bool:
        """Whether a live entity has every requested registered component."""
        if not self.is_alive(e):
            return False
        names = [component_name(comp) for comp in comps]
        return all(e in self._stores.get(name, {}) for name in names)

    def components_of(self, e: Entity) -> dict:
        """Return a new name-to-instance mapping for a live entity."""
        self._alloc.check(e)
        return {name: store[e] for name, store in self._stores.items() if e in store}

    def entities(self) -> list[Entity]:
        """List live entity ids in allocator slot order, including empty entities."""
        return [
            (self._alloc.generations[index] << INDEX_BITS) | index
            for index, alive in enumerate(self._alloc.alive) if alive
        ]

    def _store(self, name: str) -> dict[Entity, t.Any]:
        return self._stores.setdefault(name, {})

    def query(self, *comps, without=()) -> t.Iterator[tuple]:
        """Snapshot the smallest store now and yield matching components in argument order."""
        if not comps:
            raise SimWorldError("query() needs at least one component.")
        stores = [self._store(component_name(comp)) for comp in comps]
        excluded = [self._store(component_name(comp)) for comp in without]
        base = min(range(len(stores)), key=lambda index: len(stores[index]))
        items = list(stores[base].items())
        return self._iter_query(stores, excluded, base, items)

    @staticmethod
    def _iter_query(stores, excluded, base, items):
        if len(stores) == 1 and not excluded:
            store = stores[0]
            for entity, comp in items:
                if entity in store:
                    yield (entity, comp)
            return
        for entity, comp in items:
            row = []
            for index, store in enumerate(stores):
                value = comp if index == base else store.get(entity)
                if value is None:
                    break
                row.append(value)
            else:
                if any(entity in store for store in excluded):
                    continue
                if entity in stores[base]:
                    yield (entity, *row)

    def count(self, *comps, without=()) -> int:
        """Count matching entities, or all live entities when no components are supplied."""
        if not comps:
            return self._alloc.count_alive()
        return sum(1 for _ in self.query(*comps, without=without))

    @property
    def width(self):
        return self.settings.width

    @property
    def height(self):
        return self.settings.height

    @property
    def dt(self):
        return self.resources["dt"]

    @property
    def time(self):
        return self.resources["time"]

    @property
    def tick(self):
        return self.resources["tick"]

    @property
    def rng(self):
        return self.resources["rng"]
