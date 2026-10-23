"""Integrated editor for reusable behavior components."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pygame
import pygame_gui
from pygame_gui.elements import (
    UIButton,
    UIDropDownMenu,
    UILabel,
    UISelectionList,
    UITextEntryBox,
    UITextEntryLine,
    UIWindow,
)
from pygame_gui.windows import UIConfirmationDialog

from ...engine.camera import Camera2D
from ...game.behavior_projects.model import (
    BEHAVIOR_CATEGORIES,
    DEFAULT_BEHAVIOR_SOURCE,
    BehaviorAttachment,
    BehaviorDefinition,
    BehaviorFieldDefinition,
    validate_behavior_project_source,
)
from ...game.behavior_projects.registry import (
    BehaviorProject,
    BehaviorProjectRegistry,
    BehaviorProjectStore,
)
from ...game.entity_projects.model import (
    DEFAULT_BEHAVIOR_SOURCE as ENTITY_BEHAVIOR_SOURCE,
    PROPERTY_TYPES,
    AppearanceDefinition,
    EntityProjectDefinition,
    PreviewSettings,
)
from ...game.entity_projects.registry import EntityProjectStore
from ...game.project_types import EntityProjectValidationError, PropertyDefinition
from ...game.terrain import TerrainMap
from ..editor.code_editor import PythonCodeEditor
from ..editor.preview import PREVIEW_MAP_TILES, PreviewController
from ..editor.rendering import EntityAppearanceRenderer
from ..rendering import TerrainRenderer


@dataclass(frozen=True, slots=True)
class BehaviorEditorAction:
    kind: str
    value: str | None = None


class BehaviorEditorScreen:
    """Library, schema forms, source editor, and isolated component preview."""

    TABS = ("details", "parameters", "state", "requirements", "code", "preview")

    def __init__(
        self,
        surface_size: tuple[int, int],
        content_root: Path | str = Path("content/behaviors"),
        initial_behavior_id: str | None = None,
    ) -> None:
        self.surface_size = surface_size
        self.store = BehaviorProjectStore(content_root)
        self.registry = BehaviorProjectRegistry(content_root)
        self.entity_store = EntityProjectStore(self.store.root.parent / "entities")
        self.entity_catalog = self.entity_store.scan()
        self.current: BehaviorProject | None = None
        self.parameters: list[BehaviorFieldDefinition] = []
        self.runtime_state: list[BehaviorFieldDefinition] = []
        self.required_properties: list[PropertyDefinition] = []
        self.selected_field: str | None = None
        self.active_tab = "details"
        self.search_text = ""
        self.dirty = False
        self.saved_source = ""
        self.status_message = "Select a behavior or create one."
        self.status_is_error = False
        self.pending_action: tuple[str, str | None] | None = None
        self.confirmation: UIConfirmationDialog | None = None
        self.prompt_window: UIWindow | None = None
        self.prompt_kind: str | None = None
        self.prompt_id_entry: UITextEntryLine | None = None
        self.prompt_name_entry: UITextEntryLine | None = None
        self.prompt_ok_button: UIButton | None = None
        self.ui = pygame_gui.UIManager(surface_size)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.heading_font = pygame.font.Font(None, 32)
        self.code_editor = PythonCodeEditor(self._content_rect(), DEFAULT_BEHAVIOR_SOURCE)
        self.preview = PreviewController()
        self.preview_definition: EntityProjectDefinition | None = None
        self.preview_project_directory: Path | None = None
        self.preview_terrain_renderer: TerrainRenderer | None = None
        self.preview_camera: Camera2D | None = None
        self.preview_paused = False
        self.preview_host_id = ""
        self.fixtures: list[dict[str, object]] = []
        self.selected_fixture = -1
        self.appearance_renderer = EntityAppearanceRenderer()
        self._library_labels: dict[str, str] = {}
        self._widgets: list[Any] = []
        self._tab_widgets: list[Any] = []
        self._build_shell()
        initial = self.registry.catalog.get(initial_behavior_id or "")
        if initial is None and self.registry.catalog.projects:
            initial = self.registry.catalog.projects[0]
        if initial is not None:
            self._load_project(initial)
        else:
            self._sync_controls()
        pygame.key.start_text_input()

    def _workspace_rect(self) -> pygame.Rect:
        return pygame.Rect(262, 104, max(420, self.surface_size[0] - 274), max(300, self.surface_size[1] - 146))

    def _content_rect(self) -> pygame.Rect:
        workspace = self._workspace_rect()
        return pygame.Rect(workspace.x + 12, workspace.y + 52, workspace.width - 24, workspace.height - 66)

    def _button(self, rect: pygame.Rect, text: str) -> UIButton:
        button = UIButton(rect, text, self.ui)
        self._widgets.append(button)
        return button

    def _build_shell(self) -> None:
        self.back_button = self._button(pygame.Rect(10, 10, 80, 38), "Back")
        self.new_button = self._button(pygame.Rect(98, 10, 74, 38), "New")
        self.duplicate_button = self._button(pygame.Rect(180, 10, 94, 38), "Duplicate")
        self.archive_button = self._button(pygame.Rect(282, 10, 82, 38), "Archive")
        self.save_button = self._button(pygame.Rect(372, 10, 76, 38), "Save")
        self.apply_button = self._button(pygame.Rect(456, 10, 76, 38), "Apply")
        self.search_entry = UITextEntryLine(
            pygame.Rect(10, 62, 240, 34), self.ui, placeholder_text="Search behaviors"
        )
        self._widgets.append(self.search_entry)
        self.library_list = UISelectionList(
            pygame.Rect(10, 104, 240, max(120, self.surface_size[1] - 152)), [], self.ui
        )
        self._widgets.append(self.library_list)
        labels = ("Details", "Parameters", "State", "Requirements", "Code", "Preview")
        self.tab_buttons: dict[str, UIButton] = {}
        x = 270
        widths = (82, 100, 70, 116, 70, 82)
        for tab, label, width in zip(self.TABS, labels, widths):
            self.tab_buttons[tab] = self._button(pygame.Rect(x, 60, width, 36), label)
            x += width + 8
        self._refresh_library()

    def _kill_tab_widgets(self) -> None:
        for widget in self._tab_widgets:
            widget.kill()
        self._tab_widgets.clear()

    def _label(self, rect: pygame.Rect, text: str) -> UILabel:
        widget = UILabel(rect, text, self.ui)
        self._tab_widgets.append(widget)
        return widget

    def _line(self, rect: pygame.Rect, text: str = "") -> UITextEntryLine:
        widget = UITextEntryLine(rect, self.ui, initial_text=text)
        self._tab_widgets.append(widget)
        return widget

    def _refresh_library(self) -> None:
        self.registry.refresh()
        labels: list[str] = []
        self._library_labels.clear()
        query = self.search_text.casefold().strip()
        for project in self.registry.catalog.projects:
            definition = project.definition
            label = f"{definition.name} [{definition.id}]{'  built-in' if project.builtin else ''}"
            if query and query not in label.casefold() and query not in definition.category:
                continue
            labels.append(label)
            self._library_labels[label] = definition.id
        rect = self.library_list.relative_rect.copy()
        self.library_list.kill()
        self.library_list = UISelectionList(rect, labels, self.ui)
        self._widgets.append(self.library_list)

    def _load_project(self, project: BehaviorProject) -> None:
        self.preview.stop()
        self.preview_definition = None
        self.current = project
        self.parameters = list(project.definition.parameters)
        self.runtime_state = list(project.definition.state)
        self.required_properties = list(project.definition.required_properties)
        self.selected_field = None
        self.saved_source = project.behavior_source
        self.code_editor.set_text(project.behavior_source)
        self.code_editor.set_diagnostics(())
        self.dirty = False
        self.status_message = (
            f"Viewing built-in {project.definition.name}; duplicate it to customize."
            if project.builtin
            else f"Loaded {project.definition.name}."
        )
        self.status_is_error = False
        self._build_active_tab()
        self._sync_controls()

    def _sync_controls(self) -> None:
        has = self.current is not None
        editable = has and not self.current.builtin
        for button in self.tab_buttons.values():
            (button.enable() if has else button.disable())
        (self.duplicate_button.enable() if has else self.duplicate_button.disable())
        for button in (self.archive_button, self.save_button):
            (button.enable() if editable else button.disable())
        (self.apply_button.enable() if has else self.apply_button.disable())

    def _build_active_tab(self) -> None:
        self._kill_tab_widgets()
        if self.current is None:
            return
        if self.active_tab == "details":
            self._build_details()
        elif self.active_tab in ("parameters", "state", "requirements"):
            self._build_fields()
        elif self.active_tab == "preview":
            self._build_preview_controls()
        self.code_editor.focused = self.active_tab == "code"
        if self.current.builtin and self.active_tab != "preview":
            for widget in self._tab_widgets:
                if hasattr(widget, "disable"):
                    widget.disable()

    def _build_details(self) -> None:
        definition = self.current.definition
        rect = self._content_rect()
        x, y = rect.x + 24, rect.y + 18
        self._label(pygame.Rect(x, y, 150, 30), "Display name")
        self.name_entry = self._line(pygame.Rect(x + 160, y, 350, 34), definition.name)
        self._label(pygame.Rect(x, y + 46, 150, 30), "Description")
        self.description_entry = UITextEntryBox(
            relative_rect=pygame.Rect(x + 160, y + 46, min(620, rect.width - 190), 86),
            initial_text=definition.description,
            manager=self.ui,
        )
        self._tab_widgets.append(self.description_entry)
        self._label(pygame.Rect(x, y + 146, 150, 30), "Category")
        self.category_dropdown = UIDropDownMenu(
            sorted(BEHAVIOR_CATEGORIES), definition.category,
            pygame.Rect(x + 160, y + 144, 200, 34), self.ui,
        )
        self._tab_widgets.append(self.category_dropdown)
        self._label(pygame.Rect(x, y + 192, 150, 30), "Allow multiple")
        self.multiple_dropdown = UIDropDownMenu(
            ["Yes", "No"], "Yes" if definition.allow_multiple else "No",
            pygame.Rect(x + 160, y + 190, 110, 34), self.ui,
        )
        self._tab_widgets.append(self.multiple_dropdown)
        self._label(pygame.Rect(x, y + 238, 150, 30), "Exclusive group")
        self.exclusive_entry = self._line(
            pygame.Rect(x + 160, y + 236, 260, 34), definition.exclusive_group or ""
        )
        self._label(pygame.Rect(x, y + 284, 150, 30), "Writes")
        self.writes_entry = self._line(
            pygame.Rect(x + 160, y + 282, min(500, rect.width - 190), 34),
            ", ".join(definition.writes),
        )
        self._label(pygame.Rect(x, y + 330, 150, 30), "Requires behaviors")
        self.required_behaviors_entry = self._line(
            pygame.Rect(x + 160, y + 328, min(500, rect.width - 190), 34),
            ", ".join(definition.required_behaviors),
        )

    def _active_fields(self) -> list[BehaviorFieldDefinition] | list[PropertyDefinition]:
        if self.active_tab == "parameters":
            return self.parameters
        if self.active_tab == "state":
            return self.runtime_state
        return self.required_properties

    def _field_labels(self) -> list[str]:
        return [f"{item.name} : {item.type}" for item in self._active_fields()]

    def _build_fields(self) -> None:
        rect = self._content_rect()
        x, y = rect.x + 24, rect.y + 18
        heading = {
            "parameters": "Configurable parameters (behavior.config)",
            "state": "Private runtime state (behavior.state)",
            "requirements": "Required entity properties",
        }[self.active_tab]
        self._label(pygame.Rect(x, y, 430, 30), heading)
        self.field_list = UISelectionList(
            pygame.Rect(x, y + 34, min(500, rect.width // 2), 210), self._field_labels(), self.ui
        )
        self._tab_widgets.append(self.field_list)
        form_x = x + min(530, rect.width // 2 + 30)
        self._label(pygame.Rect(form_x, y + 34, 90, 30), "Name")
        self.field_name_entry = self._line(pygame.Rect(form_x + 96, y + 32, 190, 34))
        self._label(pygame.Rect(form_x, y + 78, 90, 30), "Type")
        self.field_type_dropdown = UIDropDownMenu(
            sorted(PROPERTY_TYPES), "float", pygame.Rect(form_x + 96, y + 76, 150, 34), self.ui
        )
        self._tab_widgets.append(self.field_type_dropdown)
        self._label(pygame.Rect(form_x, y + 122, 90, 30), "Default")
        self.field_default_entry = self._line(pygame.Rect(form_x + 96, y + 120, 240, 34), "0.0")
        self._label(pygame.Rect(form_x, y + 166, 90, 30), "Inspector")
        self.field_inspector_dropdown = UIDropDownMenu(
            ["Yes", "No"], "No", pygame.Rect(form_x + 96, y + 164, 110, 34), self.ui
        )
        self._tab_widgets.append(self.field_inspector_dropdown)
        if self.active_tab != "requirements":
            self._label(pygame.Rect(form_x, y + 210, 90, 30), "Editor")
            self.field_editor_dropdown = UIDropDownMenu(
                ["value", "tag", "project", "property", "choice"], "value",
                pygame.Rect(form_x + 96, y + 208, 150, 34), self.ui,
            )
            self._tab_widgets.append(self.field_editor_dropdown)
            self._label(pygame.Rect(form_x, y + 254, 90, 30), "Choices")
            self.field_choices_entry = self._line(pygame.Rect(form_x + 96, y + 252, 240, 34))
        self.field_add_button = UIButton(pygame.Rect(x, y + 258, 120, 34), "Add / Update", self.ui)
        self.field_clear_button = UIButton(pygame.Rect(x + 130, y + 258, 84, 34), "Clear", self.ui)
        self.field_remove_button = UIButton(pygame.Rect(x + 224, y + 258, 90, 34), "Remove", self.ui)
        self._tab_widgets.extend((self.field_add_button, self.field_clear_button, self.field_remove_button))

    def _build_preview_controls(self) -> None:
        rect = self._content_rect()
        y = rect.y + 4
        self.preview_run_button = UIButton(pygame.Rect(rect.x, y, 72, 34), "Run", self.ui)
        self.preview_pause_button = UIButton(pygame.Rect(rect.x + 80, y, 76, 34), "Pause", self.ui)
        self.preview_step_button = UIButton(pygame.Rect(rect.x + 164, y, 70, 34), "Step", self.ui)
        self.preview_reset_button = UIButton(pygame.Rect(rect.x + 242, y, 72, 34), "Reset", self.ui)
        self._label(pygame.Rect(rect.x + 326, y, 38, 34), "Seed")
        self.preview_seed_entry = self._line(pygame.Rect(rect.x + 366, y, 72, 34), "1")
        self._label(pygame.Rect(rect.x + 446, y, 46, 34), "Count")
        self.preview_count_entry = self._line(pygame.Rect(rect.x + 494, y, 58, 34), "1")
        self.preview_speed_dropdown = UIDropDownMenu(
            ["0.25x", "1x", "2x", "4x"], "1x", pygame.Rect(rect.x + 562, y, 86, 34), self.ui
        )
        self._tab_widgets.extend(
            (self.preview_run_button, self.preview_pause_button, self.preview_step_button,
             self.preview_reset_button, self.preview_speed_dropdown)
        )
        host_options = ["Generated compatible host", *[project.definition.id for project in self.entity_catalog.projects]]
        selected_host = self.preview_host_id if self.preview_host_id in host_options else host_options[0]
        self.preview_host_dropdown = UIDropDownMenu(
            host_options, selected_host, pygame.Rect(rect.x, y + 42, 250, 32), self.ui
        )
        fixture_options = ["Tagged marker", *[project.definition.id for project in self.entity_catalog.projects]]
        self.fixture_project_dropdown = UIDropDownMenu(
            fixture_options, fixture_options[0], pygame.Rect(rect.x + 258, y + 42, 190, 32), self.ui
        )
        self.fixture_tags_entry = self._line(pygame.Rect(rect.x + 456, y + 42, 150, 32), "target")
        self.fixture_count_entry = self._line(pygame.Rect(rect.x + 614, y + 42, 54, 32), "1")
        self.fixture_add_button = UIButton(pygame.Rect(rect.x + 676, y + 42, 64, 32), "Add", self.ui)
        self.fixture_list = UISelectionList(
            pygame.Rect(rect.x, y + 80, max(300, rect.width - 112), 64),
            [
                f"{item.get('project_id') or 'marker'} · {','.join(item.get('tags', ())) or 'no tags'} × {item.get('count', 0)}"
                for item in self.fixtures
            ],
            self.ui,
        )
        self.fixture_remove_button = UIButton(
            pygame.Rect(rect.right - 104, y + 80, 104, 34), "Remove", self.ui
        )
        self._tab_widgets.extend(
            (
                self.preview_host_dropdown,
                self.fixture_project_dropdown,
                self.fixture_add_button,
                self.fixture_list,
                self.fixture_remove_button,
            )
        )

    @staticmethod
    def _parse_value(type_name: str, source: str) -> object:
        if type_name == "float":
            return float(source)
        if type_name == "int":
            return int(source)
        if type_name == "bool":
            if source.casefold().strip() not in ("true", "false"):
                raise ValueError("bool defaults must be true or false")
            return source.casefold().strip() == "true"
        if type_name == "str":
            return source
        return json.loads(source)

    def _definition_from_forms(self) -> BehaviorDefinition:
        if self.current is None:
            raise EntityProjectValidationError("select a behavior first")
        base = self.current.definition
        if self.active_tab == "details":
            name = self.name_entry.get_text().strip()
            description = self.description_entry.get_text()
            category = self.category_dropdown.selected_option[0]
            allow_multiple = self.multiple_dropdown.selected_option[0] == "Yes"
            exclusive = self.exclusive_entry.get_text().strip() or None
            writes = tuple(dict.fromkeys(item.strip() for item in self.writes_entry.get_text().split(",") if item.strip()))
            required_behaviors = tuple(dict.fromkeys(item.strip() for item in self.required_behaviors_entry.get_text().split(",") if item.strip()))
        else:
            name, description, category = base.name, base.description, base.category
            allow_multiple, exclusive = base.allow_multiple, base.exclusive_group
            writes, required_behaviors = base.writes, base.required_behaviors
        draft = BehaviorDefinition(
            id=base.id,
            name=name,
            description=description,
            category=category,
            parameters=tuple(self.parameters),
            state=tuple(self.runtime_state),
            required_properties=tuple(self.required_properties),
            required_behaviors=required_behaviors,
            writes=writes,
            allow_multiple=allow_multiple,
            exclusive_group=exclusive,
        )
        return BehaviorDefinition.from_json(draft.to_json())

    def _commit_details_if_needed(self) -> None:
        if self.active_tab != "details" or self.current is None:
            return
        definition = self._definition_from_forms()
        self.current = replace(self.current, definition=definition)

    def _set_tab(self, tab: str) -> None:
        if tab == self.active_tab:
            return
        try:
            self._commit_details_if_needed()
        except Exception as exc:
            self._set_error(str(exc))
            return
        self.active_tab = tab
        self._build_active_tab()

    def _select_field(self, label: str) -> None:
        name = label.split(" : ", 1)[0]
        item = next((field for field in self._active_fields() if field.name == name), None)
        if item is None:
            return
        self.selected_field = item.name
        self.field_name_entry.set_text(item.name)
        self.field_default_entry.set_text(item.default if isinstance(item.default, str) else json.dumps(item.default))
        self.field_type_dropdown.kill()
        self.field_type_dropdown = UIDropDownMenu(
            sorted(PROPERTY_TYPES), item.type, self.field_type_dropdown.relative_rect, self.ui
        )
        self._tab_widgets.append(self.field_type_dropdown)
        inspector = "Yes" if item.inspector else "No"
        old = self.field_inspector_dropdown
        old.kill()
        self.field_inspector_dropdown = UIDropDownMenu(["Yes", "No"], inspector, old.relative_rect, self.ui)
        self._tab_widgets.append(self.field_inspector_dropdown)
        if isinstance(item, BehaviorFieldDefinition):
            old_editor = self.field_editor_dropdown
            old_editor.kill()
            self.field_editor_dropdown = UIDropDownMenu(
                ["value", "tag", "project", "property", "choice"], item.editor,
                old_editor.relative_rect, self.ui,
            )
            self._tab_widgets.append(self.field_editor_dropdown)
            self.field_choices_entry.set_text(", ".join(item.choices))

    def _add_or_update_field(self) -> None:
        try:
            type_name = self.field_type_dropdown.selected_option[0]
            name = self.field_name_entry.get_text().strip()
            default = self._parse_value(type_name, self.field_default_entry.get_text())
            inspector = self.field_inspector_dropdown.selected_option[0] == "Yes"
            if self.active_tab == "requirements":
                value: PropertyDefinition | BehaviorFieldDefinition = PropertyDefinition.from_mapping(
                    {"name": name, "type": type_name, "default": default, "inspector": inspector}
                )
            else:
                editor = self.field_editor_dropdown.selected_option[0]
                choices = [item.strip() for item in self.field_choices_entry.get_text().split(",") if item.strip()]
                value = BehaviorFieldDefinition.from_mapping(
                    {"name": name, "type": type_name, "default": default, "inspector": inspector,
                     "editor": editor, "choices": choices if editor == "choice" else []}
                )
            fields = self._active_fields()
            index = next((i for i, item in enumerate(fields) if item.name == self.selected_field), None)
            if index is None:
                if any(item.name == name for item in fields):
                    raise ValueError(f"field {name!r} already exists")
                fields.append(value)  # type: ignore[arg-type]
            else:
                if any(i != index and item.name == name for i, item in enumerate(fields)):
                    raise ValueError(f"field {name!r} already exists")
                fields[index] = value  # type: ignore[index]
            self.selected_field = name
            self.dirty = True
            self._build_active_tab()
            self._set_success(f"Updated {name}.")
        except Exception as exc:
            self._set_error(str(exc))

    def _clear_field(self) -> None:
        self.selected_field = None
        self._build_active_tab()

    def _remove_field(self) -> None:
        if self.selected_field is None:
            return
        fields = self._active_fields()
        fields[:] = [item for item in fields if item.name != self.selected_field]
        self.selected_field = None
        self.dirty = True
        self._build_active_tab()

    def _set_error(self, message: str) -> None:
        self.status_message, self.status_is_error = message, True

    def _set_success(self, message: str) -> None:
        self.status_message, self.status_is_error = message, False

    def _draft(self) -> tuple[BehaviorDefinition, str]:
        self._commit_details_if_needed()
        assert self.current is not None
        definition = self.current.definition
        definition = replace(
            definition,
            parameters=tuple(self.parameters),
            state=tuple(self.runtime_state),
            required_properties=tuple(self.required_properties),
        )
        definition = BehaviorDefinition.from_json(definition.to_json())
        diagnostics = validate_behavior_project_source(self.code_editor.text)
        self.code_editor.set_diagnostics(diagnostics)
        if diagnostics:
            first = diagnostics[0]
            raise EntityProjectValidationError(
                f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
            )
        return definition, self.code_editor.text

    def _preview_host(
        self, behavior: BehaviorDefinition
    ) -> tuple[EntityProjectDefinition, str, Path]:
        attachment_id = "preview"
        if self.preview_host_id:
            project = self.entity_catalog.get(self.preview_host_id)
            if project is None:
                raise EntityProjectValidationError(
                    f"preview host {self.preview_host_id!r} no longer exists"
                )
            properties = list(project.definition.properties)
            by_name = {item.name: item for item in properties}
            for required in behavior.required_properties:
                existing = by_name.get(required.name)
                if existing is not None and existing.type != required.type:
                    raise EntityProjectValidationError(
                        f"host property {required.name!r} has type {existing.type}; {required.type} is required"
                    )
                if existing is None:
                    properties.append(required)
            used = {item.attachment_id for item in project.definition.behaviors}
            suffix = 2
            while attachment_id in used:
                attachment_id = f"preview_{suffix}"
                suffix += 1
            definition = replace(
                project.definition,
                properties=tuple(properties),
                behaviors=project.definition.behaviors
                + (BehaviorAttachment(attachment_id, behavior.id, True, {}),),
            )
            return definition, project.behavior_source, project.directory
        definition = EntityProjectDefinition(
            id="behavior_preview_host",
            name=f"{behavior.name} Preview Host",
            collision_radius=7.0,
            properties=behavior.required_properties,
            tags=("preview_host",),
            behaviors=(BehaviorAttachment("preview", behavior.id, True, {}),),
            appearance=AppearanceDefinition(
                kind="circle", size=(14.0, 14.0), fill_color=(93, 196, 255, 255),
                outline_color=(220, 240, 255, 255), outline_width=1,
            ),
            preview=PreviewSettings(1, 1),
        )
        directory = self.store.root.parent / "entities" / definition.id
        return definition, ENTITY_BEHAVIOR_SOURCE, directory

    def apply(self) -> bool:
        try:
            definition, source = self._draft()
            host, host_source, entity_directory = self._preview_host(definition)
            seed = int(self.preview_seed_entry.get_text()) if self.active_tab == "preview" else 1
            instances = int(self.preview_count_entry.get_text()) if self.active_tab == "preview" else 1
            if not 0 <= seed <= 0xFFFFFFFF or not 1 <= instances <= 100:
                raise ValueError("preview seed must be 0..4294967295 and count must be 1..100")
            draft_project = BehaviorProject(definition, source, self.current.directory, False)
            draft_registry = BehaviorProjectRegistry(self.store.root, overrides=(draft_project,))
            draft_registry.validate_entity(host)
            self.preview.apply(
                host,
                host_source,
                entity_directory,
                seed=seed,
                instances=instances,
                behavior_drafts=(
                    {
                        "manifest": definition.to_json(),
                        "source": source,
                        "directory": str(self.current.directory or self.store.project_directory(definition.id)),
                    },
                ),
                fixtures=tuple(dict(item) for item in self.fixtures),
            )
            self.preview_definition = host
            self.preview_project_directory = entity_directory
            self._prepare_preview(seed)
            self._set_success("Applied draft to the isolated behavior preview.")
            return True
        except Exception as exc:
            self._set_error(str(exc))
            return False

    def save(self) -> bool:
        if self.current is None or self.current.builtin:
            self._set_error("Built-ins are read-only. Duplicate this behavior to customize it.")
            return False
        try:
            definition, source = self._draft()
            saved = self.store.save(definition, source)
            self.current = saved
            self.saved_source = source
            self.dirty = False
            self._refresh_library()
            self._set_success(f"Saved {definition.name}.")
            return True
        except Exception as exc:
            self._set_error(str(exc))
            return False

    def _prepare_preview(self, seed: int) -> None:
        terrain = TerrainMap(seed, width=PREVIEW_MAP_TILES, height=PREVIEW_MAP_TILES, tile_size=16)
        self.preview_terrain_renderer = TerrainRenderer(terrain, chunk_tiles=16)
        rect = self._preview_view_rect()
        zoom = .92 * min(rect.width / terrain.pixel_width, rect.height / terrain.pixel_height)
        self.preview_camera = Camera2D(
            terrain.pixel_width / 2, terrain.pixel_height / 2, rect.width, rect.height,
            zoom=max(.25, min(4.0, zoom)), min_zoom=.25, max_zoom=4.0,
            world_width=terrain.pixel_width, world_height=terrain.pixel_height,
        )

    def _preview_view_rect(self) -> pygame.Rect:
        rect = self._content_rect()
        return pygame.Rect(rect.x, rect.y + 152, rect.width, max(80, rect.height - 152))

    def _reset_preview(self) -> None:
        try:
            seed = int(self.preview_seed_entry.get_text())
            count = int(self.preview_count_entry.get_text())
            if not 0 <= seed <= 0xFFFFFFFF or not 1 <= count <= 100:
                raise ValueError("preview seed must be 0..4294967295 and count must be 1..100")
            self.preview.reset(seed, count)
            self._prepare_preview(seed)
        except Exception as exc:
            self._set_error(str(exc))

    def _show_prompt(self, kind: str) -> None:
        self.prompt_kind = kind
        width, height = self.surface_size
        self.prompt_window = UIWindow(
            pygame.Rect(width // 2 - 190, height // 2 - 120, 380, 235), self.ui,
            window_display_title="New behavior" if kind == "new" else "Duplicate behavior",
        )
        UILabel(pygame.Rect(16, 24, 90, 30), "Behavior ID", self.ui, container=self.prompt_window)
        self.prompt_id_entry = UITextEntryLine(pygame.Rect(112, 24, 225, 32), self.ui, container=self.prompt_window)
        UILabel(pygame.Rect(16, 68, 90, 30), "Name", self.ui, container=self.prompt_window)
        self.prompt_name_entry = UITextEntryLine(pygame.Rect(112, 68, 225, 32), self.ui, container=self.prompt_window)
        if kind == "duplicate" and self.current is not None:
            self.prompt_id_entry.set_text(f"{self.current.definition.id}_custom")
            self.prompt_name_entry.set_text(f"{self.current.definition.name} Custom")
        self.prompt_ok_button = UIButton(pygame.Rect(112, 126, 110, 36), "Create", self.ui, container=self.prompt_window)

    def _complete_prompt(self) -> None:
        try:
            assert self.prompt_id_entry is not None and self.prompt_name_entry is not None
            project_id = self.prompt_id_entry.get_text().strip()
            name = self.prompt_name_entry.get_text().strip()
            if self.registry.catalog.get(project_id) is not None:
                raise FileExistsError(f"behavior {project_id!r} already exists")
            if self.prompt_kind == "duplicate" and self.current is not None:
                project = self.registry.duplicate_to_custom(self.current.definition.id, project_id, name)
            else:
                project = self.store.create_default(project_id, name)
            self._refresh_library()
            self._load_project(project)
            if self.prompt_window is not None:
                self.prompt_window.kill()
            self.prompt_window = None
            self._set_success(f"Created {name}.")
        except Exception as exc:
            self._set_error(str(exc))

    def _dependents(self, behavior_id: str) -> list[str]:
        catalog = self.entity_store.scan()
        return [
            project.definition.id
            for project in catalog.projects
            if any(item.behavior_id == behavior_id for item in project.definition.behaviors)
        ]

    def _confirm(self, action: str, argument: str | None, message: str) -> None:
        self.pending_action = (action, argument)
        width, height = self.surface_size
        self.confirmation = UIConfirmationDialog(
            pygame.Rect(width // 2 - 210, height // 2 - 100, 420, 200), self.ui,
            window_title="Confirm", action_long_desc=message, action_short_name="Confirm", blocking=True,
        )

    def request_exit(self, kind: str = "back") -> BehaviorEditorAction | None:
        if self.dirty:
            self._confirm(kind, None, "Discard unsaved behavior changes?")
            return None
        return BehaviorEditorAction(kind)

    def _execute_pending(self) -> BehaviorEditorAction | None:
        pending = self.pending_action
        self.pending_action = None
        self.confirmation = None
        if pending is None:
            return None
        action, argument = pending
        if action in ("back", "quit"):
            return BehaviorEditorAction(action)
        if action == "open" and argument:
            project = self.registry.catalog.get(argument)
            if project:
                self._load_project(project)
        elif action == "archive" and self.current is not None:
            self.store.archive(self.current.definition.id)
            self._refresh_library()
            self.current = None
            if self.registry.catalog.projects:
                self._load_project(self.registry.catalog.projects[0])
        return None

    def _mark_dirty(self, event: pygame.event.Event) -> None:
        if self.current is not None and not self.current.builtin:
            self.dirty = True

    def _handle_gui(self, event: pygame.event.Event) -> BehaviorEditorAction | None:
        if event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            if event.ui_element == self.search_entry:
                self.search_text = event.text
                self._refresh_library()
            else:
                self._mark_dirty(event)
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element == self.library_list:
                behavior_id = self._library_labels.get(event.text)
                if behavior_id and (self.current is None or behavior_id != self.current.definition.id):
                    if self.dirty:
                        self._confirm("open", behavior_id, "Discard changes and open this behavior?")
                    else:
                        project = self.registry.catalog.get(behavior_id)
                        if project:
                            self._load_project(project)
            elif hasattr(self, "field_list") and event.ui_element == self.field_list:
                self._select_field(event.text)
            elif event.ui_element == getattr(self, "fixture_list", None):
                labels = [
                    f"{item.get('project_id') or 'marker'} · {','.join(item.get('tags', ())) or 'no tags'} × {item.get('count', 0)}"
                    for item in self.fixtures
                ]
                try:
                    self.selected_fixture = labels.index(event.text)
                except ValueError:
                    self.selected_fixture = -1
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == getattr(self, "preview_speed_dropdown", None):
                self.preview.set_speed(float(event.text.rstrip("x")))
            elif event.ui_element == getattr(self, "preview_host_dropdown", None):
                self.preview_host_id = "" if event.text == "Generated compatible host" else event.text
            else:
                self._mark_dirty(event)
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            element = event.ui_element
            if element == self.back_button:
                return self.request_exit()
            if element == self.new_button:
                if self.dirty:
                    self._set_error("Save or discard changes before creating a behavior.")
                else:
                    self._show_prompt("new")
            elif element == self.duplicate_button:
                if self.dirty:
                    self._set_error("Save or discard changes before duplicating.")
                else:
                    self._show_prompt("duplicate")
            elif element == self.archive_button and self.current is not None:
                dependents = self._dependents(self.current.definition.id)
                if dependents:
                    self._set_error("Cannot archive; used by: " + ", ".join(dependents))
                else:
                    self._confirm("archive", None, f"Archive {self.current.definition.name} to .trash?")
            elif element == self.save_button:
                self.save()
            elif element == self.apply_button:
                self.apply()
            elif element in self.tab_buttons.values():
                tab = next(name for name, button in self.tab_buttons.items() if button == element)
                self._set_tab(tab)
                if tab == "preview":
                    self.apply()
            elif element == getattr(self, "field_add_button", None):
                self._add_or_update_field()
            elif element == getattr(self, "field_clear_button", None):
                self._clear_field()
            elif element == getattr(self, "field_remove_button", None):
                self._remove_field()
            elif element == getattr(self, "preview_run_button", None):
                if self.preview.status.loaded or self.apply():
                    self.preview.pause(False)
            elif element == getattr(self, "preview_pause_button", None):
                self.preview_paused = not self.preview_paused
                self.preview.pause(self.preview_paused)
            elif element == getattr(self, "preview_step_button", None):
                self.preview.step()
            elif element == getattr(self, "preview_reset_button", None):
                self._reset_preview()
            elif element == getattr(self, "fixture_add_button", None):
                try:
                    if len(self.fixtures) >= 8:
                        raise ValueError("preview supports at most eight fixture rows")
                    count = int(self.fixture_count_entry.get_text())
                    if not 1 <= count <= 50:
                        raise ValueError("fixture count must be 1..50")
                    selected = self.fixture_project_dropdown.selected_option[0]
                    project_id = "" if selected == "Tagged marker" else selected
                    tags = tuple(
                        dict.fromkeys(
                            item.strip()
                            for item in self.fixture_tags_entry.get_text().split(",")
                            if item.strip()
                        )
                    )
                    self.fixtures.append(
                        {"project_id": project_id, "tags": tags, "count": count}
                    )
                    self.selected_fixture = len(self.fixtures) - 1
                    self._build_active_tab()
                    self._set_success("Added preview fixture row.")
                except Exception as exc:
                    self._set_error(str(exc))
            elif element == getattr(self, "fixture_remove_button", None):
                if 0 <= self.selected_fixture < len(self.fixtures):
                    self.fixtures.pop(self.selected_fixture)
                    self.selected_fixture = min(self.selected_fixture, len(self.fixtures) - 1)
                    self._build_active_tab()
            elif element == self.prompt_ok_button:
                self._complete_prompt()
        elif event.type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED and event.ui_element == self.confirmation:
            return self._execute_pending()
        elif event.type == pygame_gui.UI_WINDOW_CLOSE:
            if event.ui_element == self.confirmation:
                self.confirmation = None
                self.pending_action = None
            elif event.ui_element == self.prompt_window:
                self.prompt_window = None
        return None

    def handle_event(self, event: pygame.event.Event) -> BehaviorEditorAction | None:
        self.ui.process_events(event)
        code_action = None
        find_active = self.code_editor.find_active
        if self.active_tab == "code" and self.current is not None and not self.current.builtin:
            code_action = self.code_editor.handle_event(event)
            if code_action and code_action.kind == "save":
                self.save()
            elif code_action and code_action.kind == "apply":
                self.apply()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and not find_active and self.confirmation is None and self.prompt_window is None:
                return self.request_exit()
            if code_action is None and event.mod & pygame.KMOD_CTRL and event.key == pygame.K_s:
                self.save()
            elif code_action is None and event.key == pygame.K_F5:
                self.apply()
        return self._handle_gui(event)

    def update(self, real_dt: float) -> None:
        self.ui.update(real_dt)
        if self.current is not None and not self.current.builtin and self.code_editor.text != self.saved_source:
            self.dirty = True
        status = self.preview.poll()
        if status.snapshot is not None:
            self.preview_paused = bool(status.snapshot.get("paused", False))
            if hasattr(self, "preview_pause_button"):
                self.preview_pause_button.set_text("Resume" if self.preview_paused else "Pause")
        if status.error:
            message = str(status.error.get("message", "preview error"))
            if message != self.status_message:
                self._set_error(message)
                matches = re.findall(r'behavior\.py", line (\d+)', str(status.error.get("traceback", "")))
                if matches:
                    from ...game.project_types import BehaviorDiagnostic
                    self.code_editor.set_diagnostics((BehaviorDiagnostic(int(matches[-1]), 0, message),))

    def _draw_preview(self, surface: pygame.Surface) -> None:
        rect = self._preview_view_rect()
        pygame.draw.rect(surface, (14, 18, 23), rect)
        if self.preview_camera is None or self.preview_terrain_renderer is None or self.preview_definition is None:
            text = self.heading_font.render("Press Apply to run this behavior", True, (175, 188, 201))
            surface.blit(text, text.get_rect(center=rect.center))
            return
        view = surface.subsurface(rect)
        self.preview_terrain_renderer.draw(view, self.preview_camera)
        snapshot = self.preview.status.snapshot
        if snapshot:
            project_dir = self.preview_project_directory or (
                self.store.root.parent / "entities" / self.preview_definition.id
            )
            for entity in snapshot.get("entities", []):
                self.appearance_renderer.draw_snapshot(
                    view, self.preview_definition, project_dir, self.preview_camera, entity
                )
            hud = self.small_font.render(
                f"Tick {snapshot.get('tick', 0)} · {len(snapshot.get('entities', []))} hosts · {snapshot.get('update_ms', 0):.2f} ms",
                True, (245, 247, 250),
            )
            surface.blit(hud, (rect.x + 10, rect.y + 10))
        pygame.draw.rect(surface, (82, 96, 111), rect, 1)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((17, 21, 27))
        pygame.draw.rect(surface, (22, 27, 34), (0, 52, 260, self.surface_size[1] - 52))
        workspace = self._workspace_rect()
        pygame.draw.rect(surface, (25, 30, 38), workspace, border_radius=8)
        title = "Behavior Studio"
        if self.current:
            title += f" — {self.current.definition.name}{' (built-in)' if self.current.builtin else ''}{' *' if self.dirty else ''}"
        surface.blit(self.heading_font.render(title, True, (241, 244, 248)), (550, 15))
        if self.current is None:
            message = self.heading_font.render("Create or select a behavior", True, (190, 202, 214))
            surface.blit(message, message.get_rect(center=workspace.center))
        elif self.active_tab == "code":
            self.code_editor.draw(surface)
        elif self.active_tab == "preview":
            self._draw_preview(surface)
        elif self.active_tab in ("parameters", "state", "requirements"):
            guidance = {
                "parameters": "Parameters are immutable configuration selected for each attachment.",
                "state": "Runtime state is private to each behavior instance and included in deterministic snapshots.",
                "requirements": "Apply and Save are blocked until the host entity supplies these properties.",
            }[self.active_tab]
            surface.blit(self.small_font.render(guidance, True, (143, 158, 173)), (workspace.x + 24, workspace.bottom - 32))
        status_color = (239, 104, 104) if self.status_is_error else (142, 202, 165)
        surface.blit(self.small_font.render(self.status_message, True, status_color), (270, self.surface_size[1] - 29))
        if self.registry.catalog.errors:
            surface.blit(self.small_font.render(
                f"{len(self.registry.catalog.errors)} invalid custom behavior(s)", True, (231, 180, 92)
            ), (12, self.surface_size[1] - 27))
        self.ui.draw_ui(surface)

    def resize(self, surface_size: tuple[int, int]) -> None:
        self.surface_size = surface_size
        self.ui.set_window_resolution(surface_size)
        self.library_list.set_dimensions((240, max(120, surface_size[1] - 152)))
        self.code_editor.resize(self._content_rect())
        self._build_active_tab()
        if self.preview_camera:
            rect = self._preview_view_rect()
            self.preview_camera.resize(rect.width, rect.height)

    def close(self) -> None:
        pygame.key.stop_text_input()
        self.preview.stop()
        self.ui.clear_and_reset()


__all__ = ["BehaviorEditorAction", "BehaviorEditorScreen"]
