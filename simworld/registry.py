"""Ordered name registries shared by engine extension points."""

from __future__ import annotations

import dataclasses as dc
import typing as t

import numpy as np

from .errors import DuplicateNameError, UnknownComponentError, UnknownNameError
from .errors import NotAComponentError, SerializationError


__all__ = [
    "Registry", "COMPONENTS", "FieldInfo", "ComponentInfo", "prop", "component",
    "component_name", "component_to_dict", "component_from_dict",
]

T = t.TypeVar("T")


class Registry(t.Generic[T]):
    """Store named values with explicit replacement and useful lookup errors."""

    def __init__(
        self,
        kind: str,
        error: type[UnknownNameError] = UnknownNameError,
    ):
        self.kind = kind
        self.error = error
        self._items: dict[str, T] = {}

    def register(self, name: str, item: T, *, replace: bool = False) -> T:
        if name in self._items and not replace:
            raise DuplicateNameError(f"A {self.kind} named {name!r} is already registered.")
        self._items[name] = item
        return item

    def unregister(self, name: str) -> T | None:
        return self._items.pop(name, None)

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError:
            raise self.error(name, self.names()) from None

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __iter__(self) -> t.Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def names(self) -> list[str]:
        return list(self._items)

    def items(self) -> t.ItemsView[str, T]:
        return self._items.items()


@dc.dataclass
class FieldInfo:
    """A component field's type, default and editor/serialization metadata."""

    name: str
    type: str
    default: t.Any = None
    min: float | None = None
    max: float | None = None
    tooltip: str = ""
    serialize: bool = True
    meta: dict[str, t.Any] = dc.field(default_factory=dict)


@dc.dataclass
class ComponentInfo:
    """A registered data class and its reflected fields."""

    name: str
    cls: type
    category: str = "general"
    doc: str = ""
    fields: list[FieldInfo] = dc.field(default_factory=list)


COMPONENTS: Registry[ComponentInfo] = Registry("component", UnknownComponentError)


def prop(
    default=dc.MISSING,
    *,
    default_factory=dc.MISSING,
    min=None,
    max=None,
    tooltip="",
    serialize=True,
    init=True,
    **meta,
) -> dc.Field:
    """Declare a dataclass field with editor and serialization hints."""
    return dc.field(
        default=default,
        default_factory=default_factory,
        init=init,
        metadata={
            "min": min,
            "max": max,
            "tooltip": tooltip,
            "serialize": serialize,
            **meta,
        },
    )


def component(cls=None, *, name: str | None = None, category: str = "general"):
    """Register a data component, allowing the same logical class to reload."""
    def decorate(cls):
        registered_name = cls.__name__ if name is None else name
        previous = COMPONENTS._items.get(registered_name)
        identity = (cls.__module__, cls.__qualname__)
        if previous is not None and (
            previous.cls.__module__, previous.cls.__qualname__
        ) != identity:
            raise DuplicateNameError(
                f"Component {registered_name!r} is already registered by another class. "
                "Pass @component(name=...) to choose a distinct name."
            )

        if not dc.is_dataclass(cls):
            cls = dc.dataclass(cls, slots=True)

        reflected = []
        for field in dc.fields(cls):
            if field.default is not dc.MISSING:
                default = field.default
            elif field.default_factory is not dc.MISSING:
                default = field.default_factory()
            else:
                default = None
            type_name = (
                field.type if isinstance(field.type, str)
                else getattr(field.type, "__name__", str(field.type))
            )
            metadata = dict(field.metadata)
            reflected.append(FieldInfo(
                name=field.name,
                type=type_name,
                default=default,
                min=metadata.get("min"),
                max=metadata.get("max"),
                tooltip=metadata.get("tooltip", ""),
                serialize=metadata.get("serialize", True),
                meta=metadata,
            ))

        cls.__component_name__ = registered_name
        COMPONENTS.register(registered_name, ComponentInfo(
            name=registered_name,
            cls=cls,
            category=category,
            doc=(cls.__doc__ or "").strip(),
            fields=reflected,
        ), replace=True)
        return cls

    return decorate if cls is None else decorate(cls)


def component_name(obj) -> str:
    """Return a registered component name from its name, class, or instance."""
    if isinstance(obj, str):
        COMPONENTS.get(obj)
        return obj

    cls = obj if isinstance(obj, type) else type(obj)
    registered_name = getattr(cls, "__component_name__", None)
    if not isinstance(registered_name, str) or registered_name not in COMPONENTS:
        raise NotAComponentError(f"{obj!r} is not a registered component.")
    return registered_name


def _json_value(value):
    """Convert a supported value to JSON-compatible Python values."""
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if dc.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name))
            for field in dc.fields(value)
        }
    raise SerializationError(f"Unsupported value for component serialization: {type(value).__name__}.")


def component_to_dict(comp) -> dict:
    """Convert a registered component instance to JSON-compatible field data."""
    name = component_name(comp)
    if isinstance(comp, type):
        raise NotAComponentError("component_to_dict() expects a component instance.")
    check = getattr(comp, "_check_serializable", None)
    if check is not None:
        check()

    info = COMPONENTS.get(name)
    result = {}
    for field in info.fields:
        if field.serialize:
            result[field.name] = _json_value(getattr(comp, field.name))
    return result


def component_from_dict(name, data=None):
    """Build a component from serialized data, using dataclass defaults for omissions."""
    registered_name = component_name(name)
    info = COMPONENTS.get(registered_name)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SerializationError(f"Data for component {registered_name!r} must be a dictionary.")

    valid_fields = {field.name: field for field in info.fields}
    unknown = [key for key in data if key not in valid_fields]
    if unknown:
        valid = ", ".join(repr(field) for field in valid_fields) or "(none)"
        raise SerializationError(
            f"Unknown fields for component {registered_name!r}: "
            f"{', '.join(repr(key) for key in unknown)}. Valid fields: {valid}."
        )

    values = dict(data)
    for key, value in values.items():
        if isinstance(value, list) and isinstance(valid_fields[key].default, tuple):
            values[key] = tuple(value)
    try:
        return info.cls(**values)
    except TypeError as exc:
        raise SerializationError(f"Could not restore component {registered_name!r}: {exc}") from exc
