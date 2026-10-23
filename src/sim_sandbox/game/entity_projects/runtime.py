"""Runtime entity that delegates lifecycle behavior to an entity project."""

from __future__ import annotations

import copy
import inspect
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...engine.entity import Entity
from ..behavior_projects.runtime import BehaviorInstance
from .model import (
    BehaviorDiagnostic,
    EntityProjectDefinition,
    EntityProjectValidationError,
    normalize_property_value,
    validate_behavior_source,
)

if TYPE_CHECKING:
    from ...engine.camera import Camera2D
    from ...engine.world import World


LifecycleCallback = Callable[..., None]


@dataclass(frozen=True, slots=True)
class BehaviorCallbacks:
    init: LifecycleCallback | None = None
    update: LifecycleCallback | None = None
    delete: LifecycleCallback | None = None


class EntityScriptRuntimeError(RuntimeError):
    """Add entity and callback context to a custom entity-script failure."""

    def __init__(self, entity_id: int, callback: str, cause: BaseException) -> None:
        self.entity_id = entity_id
        self.callback = callback
        self.cause = cause
        super().__init__(
            f"entity {entity_id} custom behavior.py failed in {callback}: {cause}"
        )


@dataclass(slots=True)
class VisualState:
    visible: bool
    color: tuple[int, int, int, int]
    rotation_degrees: float
    scale_x: float
    scale_y: float

    @classmethod
    def from_definition(cls, definition: EntityProjectDefinition) -> VisualState:
        appearance = definition.appearance
        return cls(
            visible=appearance.visible,
            color=appearance.fill_color,
            rotation_degrees=appearance.rotation_degrees,
            scale_x=appearance.scale[0],
            scale_y=appearance.scale[1],
        )

    def state_values(self) -> tuple[object, ...]:
        return (
            self.visible,
            self.color,
            self.rotation_degrees,
            self.scale_x,
            self.scale_y,
        )


def compile_behavior(
    source: str, filename: str = "behavior.py"
) -> BehaviorCallbacks:
    diagnostics = validate_behavior_source(source)
    if diagnostics:
        first = diagnostics[0]
        raise EntityProjectValidationError(
            f"{filename}:{first.line}:{first.column + 1}: {first.message}"
        )
    namespace: dict[str, object] = {
        "__builtins__": __builtins__,
        "__file__": filename,
        "__name__": "editable_entity_behavior",
    }
    code = compile(source, filename, "exec")
    exec(code, namespace)
    callbacks: dict[str, LifecycleCallback | None] = {}
    expected_arguments = {"init": 2, "update": 3, "delete": 2}
    for name, expected_count in expected_arguments.items():
        callback = namespace.get(name)
        if callback is not None and not callable(callback):
            raise EntityProjectValidationError(f"{name} must be callable")
        if callback is not None:
            try:
                signature = inspect.signature(callback)
            except (TypeError, ValueError) as exc:
                raise EntityProjectValidationError(
                    f"cannot inspect {name} callback signature: {exc}"
                ) from exc
            parameters = tuple(signature.parameters.values())
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


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return tuple((key, _freeze(item)) for key, item in sorted(value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class EditableEntity(Entity):
    """Generic entity backed by declarative appearance and Python callbacks."""

    __slots__ = (
        "project_id",
        "display_name",
        "state",
        "visual",
        "_definition",
        "_callbacks",
        "_behaviors",
        "_project_directory",
        "_sprite_surface",
    )

    def __init__(
        self,
        definition: EntityProjectDefinition,
        callbacks: BehaviorCallbacks,
        project_directory: Path,
        x: float,
        y: float,
        behaviors: tuple[BehaviorInstance, ...] = (),
    ) -> None:
        super().__init__(x, y, definition.collision_radius, tags=definition.tags)
        self.project_id = definition.id
        self.display_name = definition.name
        self.state = {
            item.name: copy.deepcopy(item.default) for item in definition.properties
        }
        self.visual = VisualState.from_definition(definition)
        self._definition = definition
        self._callbacks = callbacks
        self._behaviors = behaviors
        self._project_directory = project_directory
        self._sprite_surface: Any | None = None

    @property
    def definition(self) -> EntityProjectDefinition:
        return self._definition

    def _validate_runtime_state(self) -> None:
        definitions = {item.name: item for item in self._definition.properties}
        if set(self.state) != set(definitions):
            missing = sorted(set(definitions) - set(self.state))
            extra = sorted(set(self.state) - set(definitions))
            raise ValueError(f"entity.state keys changed; missing={missing}, extra={extra}")
        for name, item in definitions.items():
            self.state[name] = normalize_property_value(
                item.type, self.state[name], f"runtime value for {name!r}"
            )
        if not isinstance(self.visual.visible, bool):
            raise ValueError("visual.visible must be boolean")
        color = self.visual.color
        if (
            not isinstance(color, (tuple, list))
            or len(color) != 4
            or any(isinstance(channel, bool) or not isinstance(channel, int) for channel in color)
            or any(channel < 0 or channel > 255 for channel in color)
        ):
            raise ValueError("visual.color must be four integer RGBA channels")
        self.visual.color = tuple(color)  # type: ignore[assignment]
        for label, value in (
            ("rotation_degrees", self.visual.rotation_degrees),
            ("scale_x", self.visual.scale_x),
            ("scale_y", self.visual.scale_y),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"visual.{label} must be a finite number")
        if self.visual.scale_x <= 0 or self.visual.scale_y <= 0:
            raise ValueError("visual scales must be positive")

    def init(self, world: World) -> None:
        for behavior in self._behaviors:
            behavior.init(self, world)
        if self._callbacks.init is not None:
            try:
                self._callbacks.init(self, world)
            except BaseException as exc:
                raise EntityScriptRuntimeError(self.entity_id, "init", exc) from exc
        self._validate_runtime_state()

    def update(self, world: World, dt: float) -> None:
        for behavior in self._behaviors:
            behavior.update(self, world, dt)
        if self._callbacks.update is not None:
            try:
                self._callbacks.update(self, world, dt)
            except BaseException as exc:
                raise EntityScriptRuntimeError(self.entity_id, "update", exc) from exc
        self._validate_runtime_state()

    def delete(self, world: World) -> None:
        first_error: BaseException | None = None
        if self._callbacks.delete is not None:
            try:
                self._callbacks.delete(self, world)
            except BaseException as exc:
                first_error = EntityScriptRuntimeError(
                    self.entity_id, "delete", exc
                )
        for behavior in reversed(self._behaviors):
            try:
                behavior.delete(self, world)
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def _base_visual_surface(self) -> Any:
        import pygame

        appearance = self._definition.appearance
        if appearance.kind == "sprite":
            if self._sprite_surface is None:
                assert appearance.sprite is not None
                loaded = pygame.image.load(str(self._project_directory / appearance.sprite))
                try:
                    loaded = loaded.convert_alpha()
                except pygame.error:
                    pass
                self._sprite_surface = loaded
            surface = self._sprite_surface.copy()
            if self.visual.color != (255, 255, 255, 255):
                tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                tint.fill(self.visual.color)
                surface.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            return surface

        width = max(1, round(appearance.size[0]))
        height = max(1, round(appearance.size[1]))
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        rect = surface.get_rect()
        if appearance.kind == "circle":
            pygame.draw.ellipse(surface, self.visual.color, rect)
            if appearance.outline_width:
                pygame.draw.ellipse(
                    surface,
                    appearance.outline_color,
                    rect,
                    width=min(appearance.outline_width, max(1, min(width, height) // 2)),
                )
        else:
            pygame.draw.rect(surface, self.visual.color, rect)
            if appearance.outline_width:
                pygame.draw.rect(
                    surface,
                    appearance.outline_color,
                    rect,
                    width=min(appearance.outline_width, max(1, min(width, height) // 2)),
                )
        return surface

    def draw(self, surface: Any, camera: Camera2D, alpha: float) -> None:
        if not self.visual.visible:
            return
        import pygame

        render_x = self.previous_x + (self.x - self.previous_x) * alpha
        render_y = self.previous_y + (self.y - self.previous_y) * alpha
        screen_x, screen_y = camera.world_to_screen(render_x, render_y)
        visual = self._base_visual_surface()
        target_size = (
            max(1, round(visual.get_width() * self.visual.scale_x * camera.zoom)),
            max(1, round(visual.get_height() * self.visual.scale_y * camera.zoom)),
        )
        visual = pygame.transform.smoothscale(visual, target_size)
        if self.visual.rotation_degrees:
            visual = pygame.transform.rotate(visual, -self.visual.rotation_degrees)
        surface.blit(visual, visual.get_rect(center=(round(screen_x), round(screen_y))))

    def state_values(self) -> tuple[object, ...]:
        return super().state_values() + (
            self.project_id,
            _freeze(self.state),
            self.visual.state_values(),
            tuple(
                (
                    attachment.attachment_id,
                    attachment.behavior_id,
                    attachment.enabled,
                    _freeze(dict(attachment.parameters)),
                )
                for attachment in self._definition.behaviors
            ),
            tuple(behavior.state_values() for behavior in self._behaviors),
        )

    def inspection_fields(self) -> tuple[tuple[str, str], ...]:
        fields = super().inspection_fields() + (
            ("Project", self.project_id),
            (
                "Behaviors",
                ", ".join(
                    f"{attachment.behavior_id}{'' if attachment.enabled else ' (disabled)'}"
                    for attachment in self._definition.behaviors
                )
                or "none",
            ),
        )
        for item in self._definition.properties:
            if item.inspector:
                fields += ((item.name.replace("_", " ").title(), str(self.state[item.name])),)
        for behavior in self._behaviors:
            fields += behavior.inspection_fields()
        return fields

    def snapshot(self) -> dict[str, object]:
        self._validate_runtime_state()
        return {
            "entity_id": self.entity_id,
            "project_id": self.project_id,
            "x": self.x,
            "y": self.y,
            "previous_x": self.previous_x,
            "previous_y": self.previous_y,
            "radius": self.radius,
            "state": copy.deepcopy(self.state),
            "tags": sorted(self.tags),
            "attachments": [
                attachment.to_mapping()
                for attachment in self._definition.behaviors
            ],
            "behaviors": [behavior.snapshot() for behavior in self._behaviors],
            "visual": {
                "visible": self.visual.visible,
                "color": list(self.visual.color),
                "rotation_degrees": self.visual.rotation_degrees,
                "scale": [self.visual.scale_x, self.visual.scale_y],
            },
        }


__all__ = [
    "BehaviorCallbacks",
    "EditableEntity",
    "EntityScriptRuntimeError",
    "VisualState",
    "compile_behavior",
]
