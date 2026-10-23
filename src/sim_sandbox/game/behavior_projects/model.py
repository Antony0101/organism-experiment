"""Schemas for reusable, configurable behavior projects."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ..project_types import (
    PROPERTY_TYPES,
    BehaviorDiagnostic,
    EntityProjectValidationError,
    PropertyDefinition,
    normalize_property_value,
)

BEHAVIOR_SCHEMA_VERSION = 1
BEHAVIOR_CATEGORIES = frozenset(
    ("movement", "terrain", "state", "lifecycle", "interaction", "visual", "custom")
)
FIELD_EDITORS = frozenset(("value", "tag", "project", "property", "choice"))
_VALID_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.:-]*$")

DEFAULT_BEHAVIOR_SOURCE = '''"""Reusable behavior component."""


def init(behavior, entity, world):
    """Called when the owning entity becomes active."""
    pass


def update(behavior, entity, world, dt):
    """Called on every fixed simulation tick."""
    pass


def delete(behavior, entity, world):
    """Called when the owning entity is removed."""
    pass
'''


@dataclass(frozen=True, slots=True)
class BehaviorFieldDefinition:
    name: str
    type: str
    default: object
    inspector: bool = False
    editor: str = "value"
    choices: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: object) -> BehaviorFieldDefinition:
        base = PropertyDefinition.from_mapping(value)
        assert isinstance(value, dict)
        editor = value.get("editor", "value")
        if editor not in FIELD_EDITORS:
            raise EntityProjectValidationError(
                f"invalid editor kind for behavior field {base.name!r}"
            )
        raw_choices = value.get("choices", [])
        if not isinstance(raw_choices, list) or any(
            not isinstance(item, str) or not item for item in raw_choices
        ):
            raise EntityProjectValidationError(
                f"choices for behavior field {base.name!r} must be text values"
            )
        choices = tuple(raw_choices)
        if editor == "choice":
            if base.type != "str" or not choices:
                raise EntityProjectValidationError(
                    f"choice field {base.name!r} must be text with at least one choice"
                )
            if base.default not in choices:
                raise EntityProjectValidationError(
                    f"default for choice field {base.name!r} must be one of its choices"
                )
        elif choices:
            raise EntityProjectValidationError(
                f"only choice fields may declare choices ({base.name!r})"
            )
        if editor in ("tag", "project", "property") and base.type != "str":
            raise EntityProjectValidationError(
                f"{editor} selector field {base.name!r} must use type str"
            )
        return cls(
            base.name,
            base.type,
            base.default,
            base.inspector,
            editor,
            choices,
        )

    def to_mapping(self) -> dict[str, object]:
        result = PropertyDefinition(
            self.name, self.type, self.default, self.inspector
        ).to_mapping()
        if self.editor != "value":
            result["editor"] = self.editor
        if self.choices:
            result["choices"] = list(self.choices)
        return result


@dataclass(frozen=True, slots=True)
class BehaviorAttachment:
    attachment_id: str
    behavior_id: str
    enabled: bool = True
    parameters: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: object) -> BehaviorAttachment:
        if not isinstance(value, dict):
            raise EntityProjectValidationError("each behavior attachment must be an object")
        attachment_id = value.get("attachment_id")
        behavior_id = value.get("behavior_id")
        enabled = value.get("enabled", True)
        parameters = value.get("parameters", {})
        if not isinstance(attachment_id, str) or not _VALID_ID.fullmatch(attachment_id):
            raise EntityProjectValidationError(
                "attachment IDs must use lowercase letters, digits, and underscores"
            )
        if not isinstance(behavior_id, str) or not _VALID_ID.fullmatch(behavior_id):
            raise EntityProjectValidationError(f"invalid behavior ID {behavior_id!r}")
        if not isinstance(enabled, bool):
            raise EntityProjectValidationError(
                f"enabled flag for attachment {attachment_id!r} must be boolean"
            )
        if not isinstance(parameters, dict) or any(
            not isinstance(name, str) for name in parameters
        ):
            raise EntityProjectValidationError(
                f"parameters for attachment {attachment_id!r} must be an object"
            )
        return cls(
            attachment_id,
            behavior_id,
            enabled,
            MappingProxyType(dict(parameters)),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "attachment_id": self.attachment_id,
            "behavior_id": self.behavior_id,
            "enabled": self.enabled,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class BehaviorDefinition:
    id: str
    name: str
    description: str = ""
    category: str = "custom"
    parameters: tuple[BehaviorFieldDefinition, ...] = ()
    state: tuple[BehaviorFieldDefinition, ...] = ()
    required_properties: tuple[PropertyDefinition, ...] = ()
    required_behaviors: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    allow_multiple: bool = False
    exclusive_group: str | None = None
    schema_version: int = BEHAVIOR_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: object) -> BehaviorDefinition:
        if not isinstance(value, dict):
            raise EntityProjectValidationError("behavior.json must contain an object")
        version = value.get("schema_version")
        if version != BEHAVIOR_SCHEMA_VERSION:
            raise EntityProjectValidationError(
                f"unsupported behavior schema_version {version!r}; expected {BEHAVIOR_SCHEMA_VERSION}"
            )
        behavior_id = value.get("id")
        if not isinstance(behavior_id, str) or not _VALID_ID.fullmatch(behavior_id):
            raise EntityProjectValidationError(
                "behavior ID must start with a lowercase letter and use lowercase letters, digits, or underscores"
            )
        name = value.get("name")
        description = value.get("description", "")
        category = value.get("category", "custom")
        if not isinstance(name, str) or not name.strip():
            raise EntityProjectValidationError("behavior name cannot be empty")
        if not isinstance(description, str):
            raise EntityProjectValidationError("behavior description must be text")
        if category not in BEHAVIOR_CATEGORIES:
            raise EntityProjectValidationError(f"invalid behavior category {category!r}")

        def field_list(key: str) -> tuple[BehaviorFieldDefinition, ...]:
            raw = value.get(key, [])
            if not isinstance(raw, list) or len(raw) > 128:
                raise EntityProjectValidationError(f"{key} must be a list of at most 128 fields")
            result = tuple(BehaviorFieldDefinition.from_mapping(item) for item in raw)
            names = [item.name for item in result]
            if len(names) != len(set(names)):
                raise EntityProjectValidationError(f"{key} names must be unique")
            return result

        raw_required = value.get("required_properties", [])
        if not isinstance(raw_required, list) or len(raw_required) > 128:
            raise EntityProjectValidationError(
                "required_properties must be a list of at most 128 fields"
            )
        required_properties = tuple(
            PropertyDefinition.from_mapping(item) for item in raw_required
        )
        required_names = [item.name for item in required_properties]
        if len(required_names) != len(set(required_names)):
            raise EntityProjectValidationError("required property names must be unique")

        required_behaviors = _slug_list(value.get("required_behaviors", []), "required_behaviors")
        writes = _capability_list(value.get("writes", []))
        allow_multiple = value.get("allow_multiple", False)
        exclusive_group = value.get("exclusive_group")
        if not isinstance(allow_multiple, bool):
            raise EntityProjectValidationError("allow_multiple must be boolean")
        if exclusive_group is not None and (
            not isinstance(exclusive_group, str)
            or not _VALID_CAPABILITY.fullmatch(exclusive_group)
        ):
            raise EntityProjectValidationError("exclusive_group must be a capability slug or null")
        return cls(
            id=behavior_id,
            name=name.strip(),
            description=description,
            category=category,
            parameters=field_list("parameters"),
            state=field_list("state"),
            required_properties=required_properties,
            required_behaviors=required_behaviors,
            writes=writes,
            allow_multiple=allow_multiple,
            exclusive_group=exclusive_group,
            schema_version=version,
        )

    @classmethod
    def from_json(cls, source: str) -> BehaviorDefinition:
        try:
            value = json.loads(source)
        except json.JSONDecodeError as exc:
            raise EntityProjectValidationError(
                f"invalid behavior.json at line {exc.lineno}: {exc.msg}"
            ) from exc
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [item.to_mapping() for item in self.parameters],
            "state": [item.to_mapping() for item in self.state],
            "required_properties": [
                item.to_mapping() for item in self.required_properties
            ],
            "required_behaviors": list(self.required_behaviors),
            "writes": list(self.writes),
            "allow_multiple": self.allow_multiple,
            "exclusive_group": self.exclusive_group,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), indent=2, ensure_ascii=False) + "\n"

    def normalized_config(self, overrides: Mapping[str, object]) -> Mapping[str, object]:
        definitions = {item.name: item for item in self.parameters}
        unknown = sorted(set(overrides) - set(definitions))
        if unknown:
            raise EntityProjectValidationError(
                f"unknown parameters for behavior {self.id!r}: {', '.join(unknown)}"
            )
        result: dict[str, object] = {}
        for name, item in definitions.items():
            result[name] = normalize_property_value(
                item.type,
                overrides.get(name, item.default),
                f"parameter {name!r} for behavior {self.id!r}",
            )
            if item.editor == "choice" and result[name] not in item.choices:
                raise EntityProjectValidationError(
                    f"parameter {name!r} for behavior {self.id!r} must be one of {item.choices}"
                )
        return MappingProxyType(result)


def _slug_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not _VALID_ID.fullmatch(item) for item in value
    ):
        raise EntityProjectValidationError(f"{label} must contain behavior IDs")
    if len(value) != len(set(value)):
        raise EntityProjectValidationError(f"{label} cannot contain duplicates")
    return tuple(value)


def _capability_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not _VALID_CAPABILITY.fullmatch(item)
        for item in value
    ):
        raise EntityProjectValidationError("writes must contain capability slugs")
    if len(value) != len(set(value)):
        raise EntityProjectValidationError("writes cannot contain duplicates")
    return tuple(value)


_CALLBACK_ARGUMENTS = {"init": 3, "update": 4, "delete": 3}


def validate_behavior_project_source(source: str) -> tuple[BehaviorDiagnostic, ...]:
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
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        expected = _CALLBACK_ARGUMENTS.get(node.name)
        if expected is None:
            continue
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


__all__ = [
    "BEHAVIOR_CATEGORIES",
    "BEHAVIOR_SCHEMA_VERSION",
    "DEFAULT_BEHAVIOR_SOURCE",
    "BehaviorAttachment",
    "BehaviorDefinition",
    "BehaviorFieldDefinition",
    "validate_behavior_project_source",
]
