"""A general-purpose 2D simulation engine, built incrementally."""

from .errors import (
    ActionError,
    ActionRejected,
    ConfigError,
    DuplicateNameError,
    MissingComponentError,
    NotAComponentError,
    OutOfBoundsError,
    PluginError,
    SerializationError,
    SimWorldError,
    StaleEntityError,
    UnknownActionError,
    UnknownBrainError,
    UnknownComponentError,
    UnknownLayerError,
    UnknownModuleError,
    UnknownNameError,
    UnknownPrefabError,
    UnknownSystemError,
    UnknownTerrainError,
)
from .errors import __all__ as _error_names
from .registry import COMPONENTS, component, prop

__all__ = [*_error_names, "COMPONENTS", "component", "prop"]
