"""Compilation and deterministic runtime instances for behavior projects."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..project_types import EntityProjectValidationError, normalize_property_value
from .model import (
    BehaviorAttachment,
    BehaviorDefinition,
    validate_behavior_project_source,
)

if TYPE_CHECKING:
    from ...engine.entity import Entity
    from ...engine.world import World


LifecycleCallback = Callable[..., None]


@dataclass(frozen=True, slots=True)
class BehaviorCallbacks:
    init: LifecycleCallback | None = None
    update: LifecycleCallback | None = None
    delete: LifecycleCallback | None = None


class BehaviorRuntimeError(RuntimeError):
    def __init__(
        self,
        behavior_id: str,
        attachment_id: str,
        callback: str,
        cause: BaseException,
        entity_id: int | None = None,
    ) -> None:
        self.behavior_id = behavior_id
        self.attachment_id = attachment_id
        self.callback = callback
        self.cause = cause
        self.entity_id = entity_id
        owner = f" on entity {entity_id}" if entity_id is not None else ""
        super().__init__(
            f"behavior {behavior_id!r} attachment {attachment_id!r}{owner} failed in {callback}: {cause}"
        )


def compile_behavior_project(
    source: str, filename: str = "behavior.py"
) -> BehaviorCallbacks:
    diagnostics = validate_behavior_project_source(source)
    if diagnostics:
        first = diagnostics[0]
        raise EntityProjectValidationError(
            f"{filename}:{first.line}:{first.column + 1}: {first.message}"
        )
    namespace: dict[str, object] = {
        "__builtins__": __builtins__,
        "__file__": filename,
        "__name__": "editable_behavior_project",
    }
    exec(compile(source, filename, "exec"), namespace)
    expected_arguments = {"init": 3, "update": 4, "delete": 3}
    callbacks: dict[str, LifecycleCallback | None] = {}
    for name, expected_count in expected_arguments.items():
        callback = namespace.get(name)
        if callback is not None and not callable(callback):
            raise EntityProjectValidationError(f"{name} must be callable")
        if callback is not None:
            try:
                parameters = tuple(inspect.signature(callback).parameters.values())
            except (TypeError, ValueError) as exc:
                raise EntityProjectValidationError(
                    f"cannot inspect {name} callback signature: {exc}"
                ) from exc
            if (
                len(parameters) != expected_count
                or any(
                    parameter.kind
                    not in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                    for parameter in parameters
                )
            ):
                raise EntityProjectValidationError(
                    f"{name} callback must accept exactly {expected_count} positional arguments"
                )
        callbacks[name] = callback  # type: ignore[assignment]
    return BehaviorCallbacks(**callbacks)


def freeze_value(value: object) -> object:
    if isinstance(value, dict):
        return tuple((key, freeze_value(item)) for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    return value


class BehaviorInstance:
    """One configured attachment owned by one entity instance."""

    __slots__ = ("attachment_id", "definition", "config", "state", "_callbacks")

    def __init__(
        self,
        definition: BehaviorDefinition,
        attachment: BehaviorAttachment,
        callbacks: BehaviorCallbacks,
    ) -> None:
        self.attachment_id = attachment.attachment_id
        self.definition = definition
        self.config = definition.normalized_config(attachment.parameters)
        self.state = {
            item.name: copy.deepcopy(item.default) for item in definition.state
        }
        self._callbacks = callbacks

    @property
    def behavior_id(self) -> str:
        return self.definition.id

    def _validate_state(self) -> None:
        definitions = {item.name: item for item in self.definition.state}
        if set(self.state) != set(definitions):
            missing = sorted(set(definitions) - set(self.state))
            extra = sorted(set(self.state) - set(definitions))
            raise ValueError(
                f"behavior.state keys changed; missing={missing}, extra={extra}"
            )
        for name, item in definitions.items():
            self.state[name] = normalize_property_value(
                item.type,
                self.state[name],
                f"runtime state {name!r} for behavior {self.behavior_id!r}",
            )

    def _call(self, name: str, entity: Entity, world: World, *args: object) -> None:
        callback = getattr(self._callbacks, name)
        if callback is None:
            return
        try:
            callback(self, entity, world, *args)
            self._validate_state()
        except BaseException as exc:
            if isinstance(exc, BehaviorRuntimeError):
                raise
            raise BehaviorRuntimeError(
                self.behavior_id, self.attachment_id, name, exc, entity.entity_id
            ) from exc

    def init(self, entity: Entity, world: World) -> None:
        self._call("init", entity, world)

    def update(self, entity: Entity, world: World, dt: float) -> None:
        self._call("update", entity, world, dt)

    def delete(self, entity: Entity, world: World) -> None:
        self._call("delete", entity, world)

    def state_values(self) -> tuple[object, ...]:
        return (
            self.attachment_id,
            self.behavior_id,
            freeze_value(dict(self.config)),
            freeze_value(self.state),
        )

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        fields: tuple[tuple[str, str], ...] = ()
        for item in self.definition.state:
            if item.inspector:
                fields += (
                    (
                        f"{self.definition.name}: {item.name.replace('_', ' ').title()}",
                        str(self.state[item.name]),
                    ),
                )
        return fields

    def snapshot(self) -> dict[str, object]:
        self._validate_state()
        return {
            "attachment_id": self.attachment_id,
            "behavior_id": self.behavior_id,
            "config": copy.deepcopy(dict(self.config)),
            "state": copy.deepcopy(self.state),
        }


__all__ = [
    "BehaviorCallbacks",
    "BehaviorInstance",
    "BehaviorRuntimeError",
    "compile_behavior_project",
    "freeze_value",
]
