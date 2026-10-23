"""Deterministic discovery and validation of trusted project worlds."""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from types import ModuleType

from ..world_definition import MAX_ENTITY_COUNT, MAX_SEED, WorldDefinition

_VALID_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class WorldLoadError:
    package: str
    message: str


@dataclass(frozen=True, slots=True)
class WorldCatalog:
    definitions: tuple[WorldDefinition, ...]
    errors: tuple[WorldLoadError, ...] = ()

    def get(self, world_id: str) -> WorldDefinition | None:
        return next((item for item in self.definitions if item.id == world_id), None)

    def require(self, world_id: str) -> WorldDefinition:
        definition = self.get(world_id)
        if definition is None:
            available = ", ".join(item.id for item in self.definitions) or "none"
            raise KeyError(f"unknown world {world_id!r}; available worlds: {available}")
        return definition


def _validate(definition: object, folder_name: str) -> WorldDefinition:
    if not isinstance(definition, WorldDefinition):
        raise TypeError("WORLD_DEFINITION must be a WorldDefinition")
    if not _VALID_ID.fullmatch(definition.id):
        raise ValueError("world ID must use lowercase letters, digits, and underscores")
    if definition.id != folder_name:
        raise ValueError(
            f"world ID {definition.id!r} must match folder name {folder_name!r}"
        )
    if not definition.name.strip():
        raise ValueError("world name cannot be empty")
    if not definition.description.strip():
        raise ValueError("world description cannot be empty")
    if not 0 <= definition.default_seed <= MAX_SEED:
        raise ValueError(f"default seed must be between 0 and {MAX_SEED}")
    if not 0 <= definition.default_population <= MAX_ENTITY_COUNT:
        raise ValueError(f"default population must be between 0 and {MAX_ENTITY_COUNT}")
    if not callable(definition.factory):
        raise TypeError("world factory must be callable")
    return definition


def _package_children(package: ModuleType) -> list[pkgutil.ModuleInfo]:
    package_path = getattr(package, "__path__", None)
    if package_path is None:
        raise ValueError(f"{package.__name__!r} is not a package")
    return sorted(pkgutil.iter_modules(package_path), key=lambda info: info.name)


def discover_worlds(
    package_name: str = "sim_sandbox.game.worlds",
) -> WorldCatalog:
    """Load immediate child packages without letting one failure hide the rest."""
    package = importlib.import_module(package_name)
    definitions: list[WorldDefinition] = []
    errors: list[WorldLoadError] = []
    seen_ids: set[str] = set()

    for info in sorted(_package_children(package), key=lambda item: item.name):
        if not info.ispkg or info.name.startswith("_"):
            continue
        module_name = f"{package_name}.{info.name}.definition"
        try:
            module = importlib.import_module(module_name)
            definition = _validate(getattr(module, "WORLD_DEFINITION"), info.name)
            if definition.id in seen_ids:
                raise ValueError(f"duplicate world ID {definition.id!r}")
            seen_ids.add(definition.id)
            definitions.append(definition)
        except Exception as exc:  # A broken trusted package is reported, not fatal.
            errors.append(WorldLoadError(info.name, f"{type(exc).__name__}: {exc}"))

    definitions.sort(key=lambda item: (item.menu_order, item.name.casefold(), item.id))
    return WorldCatalog(tuple(definitions), tuple(errors))


__all__ = ["WorldCatalog", "WorldLoadError", "discover_worlds"]
