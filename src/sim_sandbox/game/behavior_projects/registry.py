"""Discovery, persistence, validation, and runtime loading for behavior projects."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from ..project_types import EntityProjectValidationError
from .builtins import BUILTIN_BEHAVIORS
from .model import (
    DEFAULT_BEHAVIOR_SOURCE,
    BehaviorAttachment,
    BehaviorDefinition,
    validate_behavior_project_source,
)
from .runtime import BehaviorCallbacks, BehaviorInstance, compile_behavior_project

if TYPE_CHECKING:
    from ..entity_projects.model import EntityProjectDefinition


_VALID_TAG = re.compile(r"^[a-z][a-z0-9_:-]*$")


@dataclass(frozen=True, slots=True)
class BehaviorProject:
    definition: BehaviorDefinition
    behavior_source: str
    directory: Path | None
    builtin: bool = False

    @property
    def filename(self) -> str:
        if self.directory is None:
            return f"<builtin:{self.definition.id}/behavior.py>"
        return str(self.directory / "behavior.py")


@dataclass(frozen=True, slots=True)
class BehaviorProjectLoadError:
    project: str
    message: str


@dataclass(frozen=True, slots=True)
class BehaviorProjectCatalog:
    projects: tuple[BehaviorProject, ...]
    errors: tuple[BehaviorProjectLoadError, ...]

    def get(self, behavior_id: str) -> BehaviorProject | None:
        return next(
            (
                project
                for project in self.projects
                if project.definition.id == behavior_id
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class AttachmentValidation:
    warnings: tuple[str, ...] = ()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class BehaviorProjectStore:
    def __init__(self, root: Path | str = Path("content/behaviors")) -> None:
        self.root = Path(root)

    def project_directory(self, behavior_id: str) -> Path:
        if not behavior_id or Path(behavior_id).name != behavior_id:
            raise EntityProjectValidationError("invalid behavior project ID path")
        return self.root / behavior_id

    def load_directory(self, directory: Path) -> BehaviorProject:
        manifest = directory / "behavior.json"
        source_path = directory / "behavior.py"
        if not manifest.is_file():
            raise EntityProjectValidationError("behavior.json is missing")
        if not source_path.is_file():
            raise EntityProjectValidationError("behavior.py is missing")
        definition = BehaviorDefinition.from_json(manifest.read_text(encoding="utf-8"))
        if definition.id != directory.name:
            raise EntityProjectValidationError(
                f"behavior ID {definition.id!r} must match folder {directory.name!r}"
            )
        source = source_path.read_text(encoding="utf-8")
        diagnostics = validate_behavior_project_source(source)
        if diagnostics:
            first = diagnostics[0]
            raise EntityProjectValidationError(
                f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
            )
        return BehaviorProject(definition, source, directory, False)

    def load(self, behavior_id: str) -> BehaviorProject:
        return self.load_directory(self.project_directory(behavior_id))

    def scan(self) -> tuple[tuple[BehaviorProject, ...], tuple[BehaviorProjectLoadError, ...]]:
        projects: list[BehaviorProject] = []
        errors: list[BehaviorProjectLoadError] = []
        if not self.root.exists():
            return (), ()
        for directory in sorted(self.root.iterdir(), key=lambda path: path.name.casefold()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            try:
                projects.append(self.load_directory(directory))
            except Exception as exc:
                errors.append(
                    BehaviorProjectLoadError(
                        directory.name, f"{type(exc).__name__}: {exc}"
                    )
                )
        return tuple(projects), tuple(errors)

    def save(
        self, definition: BehaviorDefinition, behavior_source: str
    ) -> BehaviorProject:
        validated = BehaviorDefinition.from_json(definition.to_json())
        builtin_ids = {item.id for item, _source in BUILTIN_BEHAVIORS}
        if validated.id in builtin_ids:
            raise EntityProjectValidationError(
                f"custom behavior ID {validated.id!r} is reserved by a packaged built-in"
            )
        diagnostics = validate_behavior_project_source(behavior_source)
        if diagnostics:
            first = diagnostics[0]
            raise EntityProjectValidationError(
                f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
            )
        directory = self.project_directory(validated.id)
        directory.mkdir(parents=True, exist_ok=True)
        _atomic_write(directory / "behavior.py", behavior_source)
        _atomic_write(directory / "behavior.json", validated.to_json())
        return BehaviorProject(validated, behavior_source, directory, False)

    def create_default(self, behavior_id: str, name: str) -> BehaviorProject:
        directory = self.project_directory(behavior_id)
        if directory.exists():
            raise FileExistsError(f"behavior project {behavior_id!r} already exists")
        return self.save(
            BehaviorDefinition(id=behavior_id, name=name), DEFAULT_BEHAVIOR_SOURCE
        )

    def duplicate(
        self,
        source: BehaviorProject,
        new_id: str,
        new_name: str,
    ) -> BehaviorProject:
        destination = self.project_directory(new_id)
        if destination.exists():
            raise FileExistsError(f"behavior project {new_id!r} already exists")
        return self.save(
            replace(source.definition, id=new_id, name=new_name),
            source.behavior_source,
        )

    def archive(self, behavior_id: str) -> Path:
        source = self.project_directory(behavior_id)
        if not source.is_dir():
            raise FileNotFoundError(f"behavior project {behavior_id!r} does not exist")
        trash = self.root / ".trash"
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = trash / f"{behavior_id}-{stamp}"
        suffix = 2
        while destination.exists():
            destination = trash / f"{behavior_id}-{stamp}-{suffix}"
            suffix += 1
        return Path(shutil.move(str(source), str(destination)))


class BehaviorProjectRegistry:
    """Merge packaged presets and custom behavior projects deterministically."""

    def __init__(
        self,
        content_root: Path | str = Path("content/behaviors"),
        *,
        overrides: Iterable[BehaviorProject] = (),
    ) -> None:
        self.store = BehaviorProjectStore(content_root)
        self._overrides = tuple(overrides)
        self._callback_cache: dict[str, tuple[str, BehaviorCallbacks]] = {}
        self.catalog = self._scan()

    def _scan(self) -> BehaviorProjectCatalog:
        builtins = tuple(
            BehaviorProject(definition, source, None, True)
            for definition, source in BUILTIN_BEHAVIORS
        )
        custom, raw_errors = self.store.scan()
        builtin_ids = {project.definition.id for project in builtins}
        errors = list(raw_errors)
        accepted: list[BehaviorProject] = list(builtins)
        for project in custom:
            if project.definition.id in builtin_ids:
                errors.append(
                    BehaviorProjectLoadError(
                        project.definition.id,
                        "custom behavior IDs cannot shadow packaged built-ins",
                    )
                )
            else:
                accepted.append(project)
        if self._overrides:
            override_ids = {project.definition.id for project in self._overrides}
            accepted = [
                project
                for project in accepted
                if project.definition.id not in override_ids
            ]
            accepted.extend(self._overrides)
        accepted.sort(
            key=lambda project: (
                project.definition.category,
                project.definition.name.casefold(),
                project.definition.id,
            )
        )
        return BehaviorProjectCatalog(tuple(accepted), tuple(errors))

    def refresh(self) -> BehaviorProjectCatalog:
        self.catalog = self._scan()
        active = {project.definition.id for project in self.catalog.projects}
        self._callback_cache = {
            key: value for key, value in self._callback_cache.items() if key in active
        }
        return self.catalog

    def require(self, behavior_id: str) -> BehaviorProject:
        project = self.catalog.get(behavior_id)
        if project is None:
            available = ", ".join(
                item.definition.id for item in self.catalog.projects
            ) or "none"
            raise KeyError(
                f"unknown behavior project {behavior_id!r}; available: {available}"
            )
        return project

    def callbacks(self, behavior_id: str) -> BehaviorCallbacks:
        project = self.require(behavior_id)
        cached = self._callback_cache.get(behavior_id)
        if cached is None or cached[0] != project.behavior_source:
            callbacks = compile_behavior_project(
                project.behavior_source, project.filename
            )
            self._callback_cache[behavior_id] = (
                project.behavior_source,
                callbacks,
            )
            return callbacks
        return cached[1]

    def instantiate(self, attachment: BehaviorAttachment) -> BehaviorInstance:
        project = self.require(attachment.behavior_id)
        return BehaviorInstance(
            project.definition,
            attachment,
            self.callbacks(attachment.behavior_id),
        )

    def validate_entity(
        self, definition: EntityProjectDefinition
    ) -> AttachmentValidation:
        properties = {item.name: item for item in definition.properties}
        enabled = [item for item in definition.behaviors if item.enabled]
        behavior_ids = [item.behavior_id for item in enabled]
        by_behavior: dict[str, int] = {}
        exclusive: dict[str, str] = {}
        position_writers: list[str] = []
        warnings: list[str] = []
        for attachment in enabled:
            project = self.require(attachment.behavior_id)
            behavior = project.definition
            behavior.normalized_config(attachment.parameters)
            by_behavior[behavior.id] = by_behavior.get(behavior.id, 0) + 1
            if by_behavior[behavior.id] > 1 and not behavior.allow_multiple:
                raise EntityProjectValidationError(
                    f"behavior {behavior.name!r} cannot be attached more than once"
                )
            for requirement in behavior.required_properties:
                existing = properties.get(requirement.name)
                if existing is None:
                    raise EntityProjectValidationError(
                        f"behavior {behavior.name!r} requires property {requirement.name!r}"
                    )
                if existing.type != requirement.type:
                    raise EntityProjectValidationError(
                        f"behavior {behavior.name!r} requires property {requirement.name!r} "
                        f"to have type {requirement.type}, not {existing.type}"
                    )
            missing_behaviors = sorted(
                set(behavior.required_behaviors) - set(behavior_ids)
            )
            if missing_behaviors:
                raise EntityProjectValidationError(
                    f"behavior {behavior.name!r} requires: {', '.join(missing_behaviors)}"
                )
            if behavior.exclusive_group:
                previous = exclusive.get(behavior.exclusive_group)
                if previous is not None:
                    raise EntityProjectValidationError(
                        f"behaviors {previous!r} and {behavior.id!r} are both in exclusive "
                        f"group {behavior.exclusive_group!r}"
                    )
                exclusive[behavior.exclusive_group] = behavior.id
            if "position" in behavior.writes:
                position_writers.append(behavior.name)
            config = behavior.normalized_config(attachment.parameters)
            for parameter in behavior.parameters:
                value = config[parameter.name]
                if parameter.editor == "tag" and value and not _VALID_TAG.fullmatch(str(value)):
                    raise EntityProjectValidationError(
                        f"tag parameter {parameter.name!r} in {behavior.name!r} is invalid"
                    )
                if parameter.editor == "property" and value not in properties:
                    raise EntityProjectValidationError(
                        f"property parameter {parameter.name!r} in {behavior.name!r} "
                        f"refers to missing property {value!r}"
                    )
        if len(position_writers) > 1:
            warnings.append(
                "Multiple behaviors write position and will run in stack order: "
                + ", ".join(position_writers)
            )
        return AttachmentValidation(tuple(warnings))

    def instantiate_entity_behaviors(
        self, definition: EntityProjectDefinition
    ) -> tuple[BehaviorInstance, ...]:
        self.validate_entity(definition)
        return tuple(
            self.instantiate(attachment)
            for attachment in definition.behaviors
            if attachment.enabled
        )

    def duplicate_to_custom(
        self, behavior_id: str, new_id: str, new_name: str
    ) -> BehaviorProject:
        if self.catalog.get(new_id) is not None:
            raise FileExistsError(f"behavior project {new_id!r} already exists")
        result = self.store.duplicate(
            self.require(behavior_id), new_id, new_name
        )
        self.refresh()
        return result


__all__ = [
    "AttachmentValidation",
    "BehaviorProject",
    "BehaviorProjectCatalog",
    "BehaviorProjectLoadError",
    "BehaviorProjectRegistry",
    "BehaviorProjectStore",
]
