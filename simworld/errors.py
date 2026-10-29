"""Engine exceptions with actionable lookup diagnostics."""

from __future__ import annotations

from difflib import get_close_matches
import typing as t


__all__ = [
    "SimWorldError",
    "UnknownNameError",
    "UnknownComponentError",
    "UnknownLayerError",
    "UnknownTerrainError",
    "UnknownActionError",
    "UnknownModuleError",
    "UnknownBrainError",
    "UnknownPrefabError",
    "UnknownSystemError",
    "StaleEntityError",
    "MissingComponentError",
    "DuplicateNameError",
    "NotAComponentError",
    "OutOfBoundsError",
    "ActionError",
    "ActionRejected",
    "ConfigError",
    "PluginError",
    "SerializationError",
]


class SimWorldError(Exception):
    """Base exception for simulation errors."""


class UnknownNameError(SimWorldError, LookupError):
    """A name lookup failed; list available names and likely matches."""

    kind = "name"

    def __init__(
        self,
        name: object,
        known: t.Iterable[object],
        kind: str | None = None,
        hint: str | None = None,
    ):
        kind = self.kind if kind is None else kind
        names = [str(item) for item in known]
        matches = get_close_matches(str(name), names, n=3)
        message = f"Unknown {kind} {name!r}."
        if matches:
            message += f" Did you mean {', '.join(repr(item) for item in matches)}?"
        available = ", ".join(repr(item) for item in names) or "(none)"
        message += f" Known {kind} names: {available}."
        if hint:
            message += f" {hint}"
        super().__init__(message)


class UnknownComponentError(UnknownNameError):
    kind = "component"


class UnknownLayerError(UnknownNameError):
    kind = "layer"


class UnknownTerrainError(UnknownNameError):
    kind = "terrain"


class UnknownActionError(UnknownNameError):
    kind = "action"


class UnknownModuleError(UnknownNameError):
    kind = "module"


class UnknownBrainError(UnknownNameError):
    kind = "brain"


class UnknownPrefabError(UnknownNameError):
    kind = "prefab"


class UnknownSystemError(UnknownNameError):
    kind = "system"


class StaleEntityError(SimWorldError, LookupError):
    """An entity id is dead, stale or was never allocated."""


class MissingComponentError(SimWorldError, LookupError):
    """A live entity lacks the requested component."""


class DuplicateNameError(SimWorldError, ValueError):
    """A name or identity is already in use."""


class NotAComponentError(SimWorldError, TypeError):
    """A value is not a registered component."""


class OutOfBoundsError(SimWorldError, IndexError):
    """A layer coordinate is outside the world."""


class ActionError(SimWorldError):
    """An action cannot be submitted."""


class ActionRejected(SimWorldError):
    """A handler rejected an action without charging its cost."""


class ConfigError(SimWorldError, ValueError):
    """Configuration data is invalid."""


class PluginError(SimWorldError):
    """A plugin could not be loaded or executed."""


class SerializationError(SimWorldError):
    """State could not be encoded or restored."""
