"""World settings and the shared state used by simulation services."""

from __future__ import annotations

import dataclasses as dc
import typing as t

import numpy as np

from .ecs import Entity, EntityAllocator


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
    """Own configuration, resources, an allocator and ordered component stores."""

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
        self._alloc = EntityAllocator()
        self._stores: dict[str, dict[Entity, t.Any]] = {}

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
