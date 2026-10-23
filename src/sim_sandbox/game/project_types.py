"""Shared typed fields and diagnostics for editable content projects."""

from __future__ import annotations

import math
import keyword
from dataclasses import dataclass

PROPERTY_TYPES = frozenset(("float", "int", "bool", "str", "color", "vec2"))
RESERVED_PROPERTIES = frozenset(
    (
        "entity_id", "x", "y", "previous_x", "previous_y", "radius", "tags",
        "state", "visual", "project_id", "display_name",
    )
)


class EntityProjectValidationError(ValueError):
    """Raised when editable project data cannot be validated."""


@dataclass(frozen=True, slots=True)
class BehaviorDiagnostic:
    line: int
    column: int
    message: str
    severity: str = "error"


def number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EntityProjectValidationError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise EntityProjectValidationError(f"{label} must be finite")
    return result


def pair(value: object, label: str, *, positive: bool = False) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise EntityProjectValidationError(f"{label} must contain two numbers")
    result = (number(value[0], label), number(value[1], label))
    if positive and (result[0] <= 0.0 or result[1] <= 0.0):
        raise EntityProjectValidationError(f"{label} values must be positive")
    return result


def color(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        raise EntityProjectValidationError(f"{label} must be RGB or RGBA")
    channels = list(value)
    if len(channels) == 3:
        channels.append(255)
    if any(isinstance(channel, bool) or not isinstance(channel, int) for channel in channels):
        raise EntityProjectValidationError(f"{label} channels must be integers")
    if any(channel < 0 or channel > 255 for channel in channels):
        raise EntityProjectValidationError(f"{label} channels must be between 0 and 255")
    return tuple(channels)  # type: ignore[return-value]


def normalize_property_value(property_type: str, value: object, label: str) -> object:
    if property_type == "float":
        return number(value, label)
    if property_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise EntityProjectValidationError(f"{label} must be an integer")
        return value
    if property_type == "bool":
        if not isinstance(value, bool):
            raise EntityProjectValidationError(f"{label} must be true or false")
        return value
    if property_type == "str":
        if not isinstance(value, str):
            raise EntityProjectValidationError(f"{label} must be text")
        return value
    if property_type == "color":
        return color(value, label)
    if property_type == "vec2":
        return pair(value, label)
    raise EntityProjectValidationError(f"unsupported property type {property_type!r}")


@dataclass(frozen=True, slots=True)
class PropertyDefinition:
    name: str
    type: str
    default: object
    inspector: bool = True

    @classmethod
    def from_mapping(cls, value: object) -> PropertyDefinition:
        if not isinstance(value, dict):
            raise EntityProjectValidationError("each property must be an object")
        name = value.get("name")
        property_type = value.get("type")
        inspector = value.get("inspector", True)
        if (
            not isinstance(name, str)
            or not name.isidentifier()
            or name.startswith("_")
            or keyword.iskeyword(name)
        ):
            raise EntityProjectValidationError("property names must be public Python identifiers")
        if name in RESERVED_PROPERTIES:
            raise EntityProjectValidationError(f"property name {name!r} is reserved")
        if property_type not in PROPERTY_TYPES:
            raise EntityProjectValidationError(f"invalid type for property {name!r}")
        if not isinstance(inspector, bool):
            raise EntityProjectValidationError(f"inspector flag for {name!r} must be boolean")
        default = normalize_property_value(
            property_type, value.get("default"), f"default for {name!r}"
        )
        return cls(name, property_type, default, inspector)

    def to_mapping(self) -> dict[str, object]:
        default = list(self.default) if isinstance(self.default, tuple) else self.default
        return {
            "name": self.name,
            "type": self.type,
            "default": default,
            "inspector": self.inspector,
        }


__all__ = [
    "PROPERTY_TYPES", "BehaviorDiagnostic", "EntityProjectValidationError",
    "PropertyDefinition", "color", "normalize_property_value", "number", "pair",
]
