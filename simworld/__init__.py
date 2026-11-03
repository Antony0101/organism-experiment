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
from .components import Appearance, Position
from .registry import COMPONENTS, component, prop
from .ecs import entity_generation, entity_index
from .world import World, WorldSettings
from .systems import DEFAULT_STAGES, system

__all__ = [
    *_error_names, "COMPONENTS", "component", "prop", "Position", "Appearance",
    "entity_index", "entity_generation",
    "World", "WorldSettings",
    "system",
    "DEFAULT_STAGES",
]
