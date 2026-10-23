"""Filesystem persistence and trusted runtime loading for entity projects."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .model import (
    DEFAULT_BEHAVIOR_SOURCE,
    BehaviorDiagnostic,
    EntityProjectDefinition,
    EntityProjectValidationError,
    validate_behavior_source,
)
from .runtime import BehaviorCallbacks, EditableEntity, compile_behavior
from ..behavior_projects.registry import BehaviorProjectRegistry


@dataclass(frozen=True, slots=True)
class EntityProject:
    definition: EntityProjectDefinition
    behavior_source: str
    directory: Path


@dataclass(frozen=True, slots=True)
class EntityProjectLoadError:
    project: str
    message: str


@dataclass(frozen=True, slots=True)
class EntityProjectCatalog:
    projects: tuple[EntityProject, ...]
    errors: tuple[EntityProjectLoadError, ...]

    def get(self, project_id: str) -> EntityProject | None:
        return next(
            (project for project in self.projects if project.definition.id == project_id),
            None,
        )


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


class EntityProjectStore:
    def __init__(self, root: Path | str = Path("content/entities")) -> None:
        self.root = Path(root)

    def project_directory(self, project_id: str) -> Path:
        if not project_id or Path(project_id).name != project_id:
            raise EntityProjectValidationError("invalid project ID path")
        return self.root / project_id

    def load_directory(self, directory: Path) -> EntityProject:
        manifest_path = directory / "entity.json"
        behavior_path = directory / "behavior.py"
        if not manifest_path.is_file():
            raise EntityProjectValidationError("entity.json is missing")
        if not behavior_path.is_file():
            raise EntityProjectValidationError("behavior.py is missing")
        definition = EntityProjectDefinition.from_json(
            manifest_path.read_text(encoding="utf-8"), directory
        )
        behavior_source = behavior_path.read_text(encoding="utf-8")
        diagnostics = validate_behavior_source(behavior_source)
        if diagnostics:
            first = diagnostics[0]
            raise EntityProjectValidationError(
                f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
            )
        return EntityProject(definition, behavior_source, directory)

    def load(self, project_id: str) -> EntityProject:
        return self.load_directory(self.project_directory(project_id))

    def scan(self) -> EntityProjectCatalog:
        projects: list[EntityProject] = []
        errors: list[EntityProjectLoadError] = []
        if not self.root.exists():
            return EntityProjectCatalog((), ())
        for directory in sorted(self.root.iterdir(), key=lambda path: path.name.casefold()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            try:
                projects.append(self.load_directory(directory))
            except Exception as exc:
                errors.append(
                    EntityProjectLoadError(directory.name, f"{type(exc).__name__}: {exc}")
                )
        projects.sort(key=lambda project: (project.definition.name.casefold(), project.definition.id))
        return EntityProjectCatalog(tuple(projects), tuple(errors))

    def save(self, definition: EntityProjectDefinition, behavior_source: str) -> EntityProject:
        # Validate all metadata before creating a project directory. Sprite existence is
        # checked again after resolving paths against the final directory below.
        prevalidated = EntityProjectDefinition.from_json(definition.to_json())
        directory = self.project_directory(prevalidated.id)
        diagnostics = validate_behavior_source(behavior_source)
        if diagnostics:
            first = diagnostics[0]
            raise EntityProjectValidationError(
                f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
            )
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "assets").mkdir(exist_ok=True)
        validated = EntityProjectDefinition.from_json(prevalidated.to_json(), directory)
        _atomic_write(directory / "behavior.py", behavior_source)
        _atomic_write(directory / "entity.json", validated.to_json())
        return EntityProject(validated, behavior_source, directory)

    def create_default(self, project_id: str, name: str) -> EntityProject:
        directory = self.project_directory(project_id)
        if directory.exists():
            raise FileExistsError(f"entity project {project_id!r} already exists")
        definition = EntityProjectDefinition(id=project_id, name=name)
        return self.save(definition, DEFAULT_BEHAVIOR_SOURCE)

    def duplicate(self, project_id: str, new_id: str, new_name: str) -> EntityProject:
        source = self.load(project_id)
        destination = self.project_directory(new_id)
        if destination.exists():
            raise FileExistsError(f"entity project {new_id!r} already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source.directory, destination)
        try:
            definition = replace(source.definition, id=new_id, name=new_name)
            return self.save(definition, source.behavior_source)
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def archive(self, project_id: str) -> Path:
        source = self.project_directory(project_id)
        if not source.is_dir():
            raise FileNotFoundError(f"entity project {project_id!r} does not exist")
        trash = self.root / ".trash"
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = trash / f"{project_id}-{stamp}"
        suffix = 2
        while destination.exists():
            destination = trash / f"{project_id}-{stamp}-{suffix}"
            suffix += 1
        return Path(shutil.move(str(source), str(destination)))

    def import_sprite(self, project_id: str, source: Path | str) -> str:
        source_path = Path(source)
        if source_path.suffix.lower() != ".png" or not source_path.is_file():
            raise EntityProjectValidationError("sprite source must be an existing PNG file")
        with source_path.open("rb") as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                raise EntityProjectValidationError("sprite source is not a valid PNG file")
        assets = self.project_directory(project_id) / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in source_path.stem
        ).strip("_") or "sprite"
        destination = assets / f"{safe_stem}.png"
        suffix = 2
        while destination.exists():
            destination = assets / f"{safe_stem}_{suffix}.png"
            suffix += 1
        shutil.copy2(source_path, destination)
        return destination.relative_to(self.project_directory(project_id)).as_posix()


class EntityProjectRegistry:
    """Discover projects and create trusted in-process runtime entities."""

    def __init__(
        self,
        content_root: Path | str = Path("content/entities"),
        behavior_registry: BehaviorProjectRegistry | None = None,
    ) -> None:
        self.store = EntityProjectStore(content_root)
        self.behaviors = behavior_registry or BehaviorProjectRegistry(
            self.store.root.parent / "behaviors"
        )
        self._callback_cache: dict[str, tuple[str, BehaviorCallbacks]] = {}
        self.catalog = self.store.scan()
        self.catalog = self._validated_catalog(self.catalog)

    def _validated_catalog(
        self, catalog: EntityProjectCatalog
    ) -> EntityProjectCatalog:
        # Project selector validation needs a complete first-pass catalog so
        # references can resolve regardless of folder order.
        self.catalog = catalog
        accepted: list[EntityProject] = []
        errors = list(catalog.errors)
        for project in catalog.projects:
            try:
                self._validate_project_selectors(project.definition)
                self.behaviors.validate_entity(project.definition)
                accepted.append(project)
            except Exception as exc:
                errors.append(
                    EntityProjectLoadError(
                        project.definition.id, f"{type(exc).__name__}: {exc}"
                    )
                )
        return EntityProjectCatalog(tuple(accepted), tuple(errors))

    def refresh(self) -> EntityProjectCatalog:
        self.behaviors.refresh()
        self.catalog = self._validated_catalog(self.store.scan())
        active_ids = {project.definition.id for project in self.catalog.projects}
        self._callback_cache = {
            project_id: cached
            for project_id, cached in self._callback_cache.items()
            if project_id in active_ids
        }
        return self.catalog

    def require(self, project_id: str) -> EntityProject:
        project = self.catalog.get(project_id)
        if project is None:
            available = ", ".join(
                item.definition.id for item in self.catalog.projects
            ) or "none"
            raise KeyError(f"unknown entity project {project_id!r}; available: {available}")
        return project

    def create(self, project_id: str, x: float, y: float) -> EditableEntity:
        project = self.require(project_id)
        self._validate_project_selectors(project.definition)
        behavior_instances = self.behaviors.instantiate_entity_behaviors(
            project.definition
        )
        cached = self._callback_cache.get(project_id)
        if cached is None or cached[0] != project.behavior_source:
            callbacks = compile_behavior(
                project.behavior_source, str(project.directory / "behavior.py")
            )
            self._callback_cache[project_id] = (project.behavior_source, callbacks)
        else:
            callbacks = cached[1]
        return EditableEntity(
            project.definition,
            callbacks,
            project.directory,
            x,
            y,
            behavior_instances,
        )

    def _validate_project_selectors(self, definition: EntityProjectDefinition) -> None:
        for attachment in definition.behaviors:
            behavior = self.behaviors.require(attachment.behavior_id).definition
            config = behavior.normalized_config(attachment.parameters)
            for parameter in behavior.parameters:
                if parameter.editor != "project":
                    continue
                project_id = str(config[parameter.name])
                if project_id and self.catalog.get(project_id) is None:
                    raise EntityProjectValidationError(
                        f"behavior {behavior.name!r} refers to unknown entity project {project_id!r}"
                    )

    def validate(self, definition: EntityProjectDefinition):
        self._validate_project_selectors(definition)
        return self.behaviors.validate_entity(definition)

    def configure_world(self, world) -> None:
        world.configure_entity_factory(self.create)


__all__ = [
    "EntityProject",
    "EntityProjectCatalog",
    "EntityProjectLoadError",
    "EntityProjectRegistry",
    "EntityProjectStore",
]
