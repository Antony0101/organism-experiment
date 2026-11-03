"""System definitions, registration metadata and stage scheduling."""

from __future__ import annotations

import dataclasses as dc
import typing as t
from time import perf_counter

from .registry import active_world
from .errors import DuplicateNameError, UnknownSystemError

if t.TYPE_CHECKING:
    from .world import World


DEFAULT_STAGES = ("input", "sense", "decide", "act", "update", "late")

__all__ = ["DEFAULT_STAGES", "SystemDef", "system", "Scheduler"]


@dc.dataclass
class SystemDef:
    """A simulation function and its registration/scheduling metadata."""

    name: str
    fn: t.Callable[[World], None]
    stage: str = "update"
    order: float = 0
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    module: str | None = None
    enabled: bool = True
    every: int = 1
    doc: str = ""
    seq: int = 0
    base_order: float | None = None

    def __post_init__(self):
        self.reads = tuple(self.reads)
        self.writes = tuple(self.writes)
        if self.base_order is None:
            self.base_order = self.order


def system(fn=None, *, stage="update", order=0, reads=(), writes=(), name=None, every=1):
    """Attach system metadata and register immediately inside a loading context."""
    def decorate(fn):
        definition = SystemDef(
            name=fn.__name__ if name is None else name, fn=fn, stage=stage,
            order=order, reads=reads, writes=writes, every=every,
            doc=(fn.__doc__ or "").strip(),
        )
        fn.__sim_system__ = definition
        world = active_world()
        if world is not None:
            world.add_system(definition)
        return fn

    return decorate if fn is None else decorate(fn)


class Scheduler:
    """Order systems by stage, priority and registration sequence."""

    def __init__(self, world: World):
        self._world = world
        self.stages: list[str] = list(DEFAULT_STAGES)
        self.systems: dict[str, SystemDef] = {}
        self.profile = False
        self.timings: dict[str, float] = {}
        self._seq = 0
        self._sorted: dict[str, list[SystemDef]] | None = None

    def add_stage(self, name, *, after=None, before=None) -> None:
        if after is not None and before is not None:
            raise ValueError("Specify either after or before for a stage, not both.")
        if name in self.stages:
            raise DuplicateNameError(f"A stage named {name!r} already exists.")
        anchor = after if after is not None else before
        if anchor is not None:
            if anchor not in self.stages:
                raise UnknownSystemError(anchor, self.stages, "stage")
            index = self.stages.index(anchor) + (1 if after is not None else 0)
            self.stages.insert(index, name)
        else:
            self.stages.append(name)
        self._sorted = None

    def add(self, sd: SystemDef, *, replace=False) -> None:
        if sd.stage not in self.stages:
            raise UnknownSystemError(sd.stage, self.stages, "stage")
        if sd.name in self.systems and not replace:
            raise DuplicateNameError(f"A system named {sd.name!r} is already registered.")
        sd.seq = self._seq
        self._seq += 1
        self.systems[sd.name] = sd
        self._sorted = None

    def get(self, name) -> SystemDef:
        try:
            return self.systems[name]
        except KeyError:
            raise UnknownSystemError(name, self.systems) from None

    def remove(self, name) -> None:
        self.get(name)
        del self.systems[name]
        self._sorted = None

    def set_enabled(self, name, enabled) -> None:
        self.get(name).enabled = bool(enabled)

    def ordered(self) -> list[SystemDef]:
        """Return systems in execution order, caching the lists within each stage."""
        if self._sorted is None:
            self._sorted = {
                stage: sorted(
                    (sd for sd in self.systems.values() if sd.stage == stage),
                    key=lambda sd: (sd.order, sd.seq),
                )
                for stage in self.stages
            }
        return [sd for stage in self.stages for sd in self._sorted[stage]]

    def run_step(self) -> None:
        """Execute eligible systems at the current tick without advancing the world clock."""
        world = self._world
        for sd in self.ordered():
            if not sd.enabled:
                continue
            # Module installation is introduced later; no modules are disabled before then.
            module_enabled = getattr(world, "module_enabled", None)
            if sd.module is not None and module_enabled is not None and not module_enabled(sd.module):
                continue
            if sd.every > 1 and world.tick % sd.every != 0:
                continue
            if not self.profile:
                sd.fn(world)
                continue
            started = perf_counter()
            try:
                sd.fn(world)
            finally:
                self.timings[sd.name] = self.timings.get(sd.name, 0.0) + perf_counter() - started
