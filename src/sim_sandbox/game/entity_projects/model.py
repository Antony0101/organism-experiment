"""Versioned, JSON-serializable definitions for editor-created entities."""

from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..world_definition import MAX_SEED

SCHEMA_VERSION = 2
MAX_PREVIEW_INSTANCES = 100
PROPERTY_TYPES = frozenset(("float", "int", "bool", "str", "color", "vec2"))
APPEARANCE_KINDS = frozenset(("circle", "rectangle", "sprite"))
_VALID_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_TAG = re.compile(r"^[a-z][a-z0-9_:-]*$")
_RESERVED_PROPERTIES = frozenset(
    (
        "entity_id",
        "x",
        "y",
        "previous_x",
        "previous_y",
        "radius",
        "state",
        "visual",
        "project_id",
        "display_name",
    )
)

DEFAULT_BEHAVIOR_SOURCE = '''"""Lifecycle behavior for this editable entity."""


def init(entity, world):
    """Called once when the entity becomes active."""
    pass


def update(entity, world, dt):
    """Called on each fixed simulation tick."""
    # Example: entity.x += entity.state["speed"] * dt
    pass


def delete(entity, world):
    """Called once before removal or world shutdown."""
    pass
'''


class EntityProjectValidationError(ValueError):
    """Raised when an entity project cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class BehaviorDiagnostic:
    line: int
    column: int
    message: str
    severity: str = "error"


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EntityProjectValidationError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise EntityProjectValidationError(f"{label} must be finite")
    return result


def _pair(value: object, label: str, *, positive: bool = False) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise EntityProjectValidationError(f"{label} must contain two numbers")
    pair = (_number(value[0], label), _number(value[1], label))
    if positive and (pair[0] <= 0.0 or pair[1] <= 0.0):
        raise EntityProjectValidationError(f"{label} values must be positive")
    return pair


def _color(value: object, label: str) -> tuple[int, int, int, int]:
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
        return _number(value, label)
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
        return _color(value, label)
    if property_type == "vec2":
        return _pair(value, label)
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
        if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
            raise EntityProjectValidationError("property names must be public Python identifiers")
        if name in _RESERVED_PROPERTIES:
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


# Shared definitions are re-exported from this legacy module path. Keeping the
# aliases here preserves existing imports while behavior projects avoid a
# package-level circular dependency.
from ..project_types import (  # noqa: E402
    PROPERTY_TYPES as PROPERTY_TYPES,
    BehaviorDiagnostic as BehaviorDiagnostic,
    EntityProjectValidationError as EntityProjectValidationError,
    PropertyDefinition as PropertyDefinition,
    normalize_property_value as normalize_property_value,
)


@dataclass(frozen=True, slots=True)
class AppearanceDefinition:
    kind: str = "circle"
    size: tuple[float, float] = (10.0, 10.0)
    fill_color: tuple[int, int, int, int] = (255, 210, 70, 255)
    outline_color: tuple[int, int, int, int] = (40, 40, 40, 255)
    outline_width: int = 0
    rotation_degrees: float = 0.0
    scale: tuple[float, float] = (1.0, 1.0)
    visible: bool = True
    sprite: str | None = None

    @classmethod
    def from_mapping(
        cls, value: object, project_directory: Path | None = None
    ) -> AppearanceDefinition:
        if not isinstance(value, dict):
            raise EntityProjectValidationError("appearance must be an object")
        kind = value.get("kind", "circle")
        if kind not in APPEARANCE_KINDS:
            raise EntityProjectValidationError(f"unsupported appearance kind {kind!r}")
        size = _pair(value.get("size", [10, 10]), "appearance size", positive=True)
        if size[0] > 4096 or size[1] > 4096:
            raise EntityProjectValidationError("appearance size cannot exceed 4096 pixels")
        outline_width = value.get("outline_width", 0)
        if isinstance(outline_width, bool) or not isinstance(outline_width, int):
            raise EntityProjectValidationError("outline_width must be an integer")
        if not 0 <= outline_width <= 100:
            raise EntityProjectValidationError("outline_width must be between 0 and 100")
        visible = value.get("visible", True)
        if not isinstance(visible, bool):
            raise EntityProjectValidationError("appearance visible must be boolean")
        sprite = value.get("sprite")
        if sprite is not None and not isinstance(sprite, str):
            raise EntityProjectValidationError("sprite must be a relative PNG path")
        if kind == "sprite":
            if not sprite:
                raise EntityProjectValidationError("sprite appearance requires a PNG asset")
            sprite_path = Path(sprite)
            if sprite_path.is_absolute() or ".." in sprite_path.parts:
                raise EntityProjectValidationError("sprite path must stay inside the project")
            if sprite_path.suffix.lower() != ".png":
                raise EntityProjectValidationError("sprite asset must be a PNG file")
            if project_directory is not None:
                resolved_project = project_directory.resolve()
                resolved_sprite = (project_directory / sprite_path).resolve()
                if not resolved_sprite.is_relative_to(resolved_project):
                    raise EntityProjectValidationError("sprite path escapes the project")
                if not resolved_sprite.is_file():
                    raise EntityProjectValidationError(f"sprite asset not found: {sprite}")
        elif sprite is not None:
            raise EntityProjectValidationError("only sprite appearances may define a sprite")
        return cls(
            kind=kind,
            size=size,
            fill_color=_color(value.get("fill_color", [255, 210, 70, 255]), "fill_color"),
            outline_color=_color(
                value.get("outline_color", [40, 40, 40, 255]), "outline_color"
            ),
            outline_width=outline_width,
            rotation_degrees=_number(value.get("rotation_degrees", 0), "rotation"),
            scale=_pair(value.get("scale", [1, 1]), "scale", positive=True),
            visible=visible,
            sprite=sprite,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "size": list(self.size),
            "fill_color": list(self.fill_color),
            "outline_color": list(self.outline_color),
            "outline_width": self.outline_width,
            "rotation_degrees": self.rotation_degrees,
            "scale": list(self.scale),
            "visible": self.visible,
            "sprite": self.sprite,
        }


@dataclass(frozen=True, slots=True)
class PreviewSettings:
    seed: int = 1
    instances: int = 1

    @classmethod
    def from_mapping(cls, value: object) -> PreviewSettings:
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise EntityProjectValidationError("preview must be an object")
        seed = value.get("seed", 1)
        instances = value.get("instances", 1)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
            raise EntityProjectValidationError(f"preview seed must be between 0 and {MAX_SEED}")
        if (
            isinstance(instances, bool)
            or not isinstance(instances, int)
            or not 1 <= instances <= MAX_PREVIEW_INSTANCES
        ):
            raise EntityProjectValidationError(
                f"preview instances must be between 1 and {MAX_PREVIEW_INSTANCES}"
            )
        return cls(seed, instances)

    def to_mapping(self) -> dict[str, int]:
        return {"seed": self.seed, "instances": self.instances}


@dataclass(frozen=True, slots=True)
class EntityProjectDefinition:
    id: str
    name: str
    description: str = ""
    collision_radius: float = 5.0
    properties: tuple[PropertyDefinition, ...] = ()
    tags: tuple[str, ...] = ()
    behaviors: tuple["BehaviorAttachment", ...] = ()
    appearance: AppearanceDefinition = AppearanceDefinition()
    preview: PreviewSettings = PreviewSettings()
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_mapping(
        cls, value: object, project_directory: Path | None = None
    ) -> EntityProjectDefinition:
        if not isinstance(value, dict):
            raise EntityProjectValidationError("entity.json must contain an object")
        schema_version = value.get("schema_version")
        if schema_version not in (1, SCHEMA_VERSION):
            raise EntityProjectValidationError(
                f"unsupported schema_version {schema_version!r}; expected 1 or {SCHEMA_VERSION}"
            )
        entity_id = value.get("id")
        if not isinstance(entity_id, str) or not _VALID_ID.fullmatch(entity_id):
            raise EntityProjectValidationError(
                "entity ID must start with a lowercase letter and use lowercase letters, digits, or underscores"
            )
        if project_directory is not None and project_directory.name != entity_id:
            raise EntityProjectValidationError(
                f"entity ID {entity_id!r} must match folder {project_directory.name!r}"
            )
        name = value.get("name")
        description = value.get("description", "")
        if not isinstance(name, str) or not name.strip():
            raise EntityProjectValidationError("entity name cannot be empty")
        if not isinstance(description, str):
            raise EntityProjectValidationError("entity description must be text")
        collision_radius = _number(value.get("collision_radius", 5), "collision_radius")
        if not 0 < collision_radius <= 2048:
            raise EntityProjectValidationError("collision_radius must be between 0 and 2048")
        raw_properties = value.get("properties", [])
        if not isinstance(raw_properties, list) or len(raw_properties) > 128:
            raise EntityProjectValidationError("properties must be a list of at most 128 items")
        properties = tuple(PropertyDefinition.from_mapping(item) for item in raw_properties)
        names = [item.name for item in properties]
        if len(set(names)) != len(names):
            raise EntityProjectValidationError("property names must be unique")
        if schema_version == 1:
            tags: tuple[str, ...] = ()
            behaviors: tuple[BehaviorAttachment, ...] = ()
        else:
            raw_tags = value.get("tags", [])
            if not isinstance(raw_tags, list) or any(
                not isinstance(tag, str) or not _VALID_TAG.fullmatch(tag)
                for tag in raw_tags
            ):
                raise EntityProjectValidationError(
                    "tags must use lowercase letters, digits, underscores, colons, or hyphens"
                )
            if len(raw_tags) != len(set(raw_tags)):
                raise EntityProjectValidationError("entity tags must be unique")
            tags = tuple(raw_tags)
            from ..behavior_projects.model import BehaviorAttachment

            raw_behaviors = value.get("behaviors", [])
            if not isinstance(raw_behaviors, list) or len(raw_behaviors) > 128:
                raise EntityProjectValidationError(
                    "behaviors must be a list of at most 128 attachments"
                )
            behaviors = tuple(
                BehaviorAttachment.from_mapping(item) for item in raw_behaviors
            )
            attachment_ids = [item.attachment_id for item in behaviors]
            if len(attachment_ids) != len(set(attachment_ids)):
                raise EntityProjectValidationError("behavior attachment IDs must be unique")
        return cls(
            id=entity_id,
            name=name.strip(),
            description=description,
            collision_radius=collision_radius,
            properties=properties,
            tags=tags,
            behaviors=behaviors,
            appearance=AppearanceDefinition.from_mapping(
                value.get("appearance", {}), project_directory
            ),
            preview=PreviewSettings.from_mapping(value.get("preview")),
            schema_version=SCHEMA_VERSION,
        )

    @classmethod
    def from_json(
        cls, source: str, project_directory: Path | None = None
    ) -> EntityProjectDefinition:
        try:
            value = json.loads(source)
        except json.JSONDecodeError as exc:
            raise EntityProjectValidationError(
                f"invalid entity.json at line {exc.lineno}: {exc.msg}"
            ) from exc
        return cls.from_mapping(value, project_directory)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "collision_radius": self.collision_radius,
            "properties": [item.to_mapping() for item in self.properties],
            "tags": list(self.tags),
            "behaviors": [item.to_mapping() for item in self.behaviors],
            "appearance": self.appearance.to_mapping(),
            "preview": self.preview.to_mapping(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), indent=2, ensure_ascii=False) + "\n"


_CALLBACK_ARGUMENTS = {"init": 2, "update": 3, "delete": 2}


def validate_behavior_source(source: str) -> tuple[BehaviorDiagnostic, ...]:
    try:
        tree = ast.parse(source, filename="behavior.py")
    except SyntaxError as exc:
        return (
            BehaviorDiagnostic(
                exc.lineno or 1,
                max(0, (exc.offset or 1) - 1),
                exc.msg,
            ),
        )
    diagnostics: list[BehaviorDiagnostic] = []
    callbacks: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _CALLBACK_ARGUMENTS:
            if node.name in callbacks:
                diagnostics.append(
                    BehaviorDiagnostic(node.lineno, node.col_offset, f"duplicate {node.name} callback")
                )
                continue
            callbacks[node.name] = node
            if isinstance(node, ast.AsyncFunctionDef):
                diagnostics.append(
                    BehaviorDiagnostic(node.lineno, node.col_offset, "callbacks cannot be async")
                )
                continue
            positional = len(node.args.posonlyargs) + len(node.args.args)
            expected = _CALLBACK_ARGUMENTS[node.name]
            if (
                positional != expected
                or node.args.vararg is not None
                or node.args.kwarg is not None
                or node.args.kwonlyargs
            ):
                diagnostics.append(
                    BehaviorDiagnostic(
                        node.lineno,
                        node.col_offset,
                        f"{node.name} must accept exactly {expected} positional arguments",
                    )
                )
    return tuple(diagnostics)
