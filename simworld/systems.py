"""System definitions and decorator metadata for world registration."""

from __future__ import annotations

import dataclasses as dc
import typing as t

from .registry import active_world

if t.TYPE_CHECKING:
    from .world import World


__all__ = ["SystemDef", "system"]


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
