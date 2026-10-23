"""Integrated entity project designer, code editor, and isolated preview."""

from __future__ import annotations

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
from pygame_gui.windows import (
    UIColourPickerDialog,
    UIConfirmationDialog,
    UIFileDialog,
)

from ...engine.camera import Camera2D
from ...game.entity_projects.model import (
    DEFAULT_BEHAVIOR_SOURCE,
    PROPERTY_TYPES,
    AppearanceDefinition,
    BehaviorDiagnostic,
    EntityProjectDefinition,
    EntityProjectValidationError,
    PreviewSettings,
    PropertyDefinition,
    validate_behavior_source,
)
from ...game.entity_projects.registry import EntityProject, EntityProjectStore
from ...game.entity_projects.registry import EntityProjectRegistry
from ...game.behavior_projects.model import BEHAVIOR_CATEGORIES, BehaviorAttachment
from ...game.behavior_projects.registry import BehaviorProjectRegistry
from ...game.terrain import TerrainMap
from ..editor.code_editor import PythonCodeEditor
from ..editor.preview import PREVIEW_MAP_TILES, PreviewController
from ..editor.rendering import EntityAppearanceRenderer
from ..rendering import TerrainRenderer


@dataclass(frozen=True, slots=True)
class EntityEditorAction:
    kind: str
    value: str | None = None


class EntityEditorScreen:
    """One-screen studio with Design, Code, and Preview workspaces."""

    TABS = ("design", "behaviors", "code", "preview")

    def __init__(
        self,
        surface_size: tuple[int, int],
        content_root: Path | str = Path("content/entities"),
    ) -> None:
        self.surface_size = surface_size
        self.store = EntityProjectStore(content_root)
        self.behavior_registry = BehaviorProjectRegistry(self.store.root.parent / "behaviors")
        self.entity_registry = EntityProjectRegistry(self.store.root, self.behavior_registry)
        self.catalog = self.store.scan()
        self.current: EntityProject | None = None
        self.saved_behavior = ""
        self.properties: list[PropertyDefinition] = []
        self.tags: list[str] = []
        self.attachments: list[BehaviorAttachment] = []
        self.selected_attachment: str | None = None
        self.selected_behavior_project: str | None = None
        self.behavior_search_text = ""
        self.behavior_category = "all"
        self.behavior_parameter_entries: dict[str, Any] = {}
        self._available_behavior_labels: dict[str, str] = {}
        self._attachment_labels: dict[str, str] = {}
        self.selected_property: str | None = None
        self.sprite_path: str | None = None
        self.fill_color = (255, 210, 70, 255)
        self.outline_color = (40, 40, 40, 255)
        self.appearance_kind = "circle"
        self.visible_option = "Yes"
        self.property_type = "float"
        self.property_inspector_option = "Yes"
        self.active_tab = "design"
        self.dirty = False
        self.status_message = "Create or select an entity project."
        self.status_is_error = False
        self.search_text = ""
        self.pending_action: tuple[str, str | None] | None = None
        self.confirmation: UIConfirmationDialog | None = None
        self.file_dialog: UIFileDialog | None = None
        self.color_dialog: UIColourPickerDialog | None = None
        self.color_target: str | None = None
        self.prompt_window: UIWindow | None = None
        self.prompt_kind: str | None = None
        self.prompt_id_entry: UITextEntryLine | None = None
        self.prompt_name_entry: UITextEntryLine | None = None
        self.prompt_ok_button: UIButton | None = None
        self.ui = pygame_gui.UIManager(surface_size)
        self.font = pygame.font.Font(None, 24)
        self.heading_font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 20)
        self.appearance_renderer = EntityAppearanceRenderer()
        self.preview = PreviewController()
        self.preview_definition: EntityProjectDefinition | None = None
        self.preview_terrain: TerrainMap | None = None
        self.preview_terrain_renderer: TerrainRenderer | None = None
        self.preview_camera: Camera2D | None = None
        self.preview_paused = False
        self.preview_speed = 1.0
        self._preview_dragging = False
        self._library_labels: dict[str, str] = {}
        self._persistent_widgets: list[Any] = []
        self._design_widgets: list[Any] = []
        self._behavior_widgets: list[Any] = []
        self._preview_widgets: list[Any] = []
        self._build_ui()
        if self.catalog.projects:
            self._load_project(self.catalog.projects[0])
        else:
            self.status_message = "No entity projects yet. Create your first entity to begin."
            self._sync_project_ui()
        pygame.key.start_text_input()

    def _workspace_rect(self) -> pygame.Rect:
        return pygame.Rect(262, 102, max(300, self.surface_size[0] - 274), max(250, self.surface_size[1] - 146))

    def _preview_rect(self) -> pygame.Rect:
        workspace = self._workspace_rect()
        return pygame.Rect(workspace.x + 12, workspace.y + 58, workspace.width - 24, workspace.height - 70)

    def _code_rect(self) -> pygame.Rect:
        workspace = self._workspace_rect()
        return pygame.Rect(workspace.x + 10, workspace.y + 52, workspace.width - 20, workspace.height - 64)

    def _button(self, rect: pygame.Rect, text: str) -> UIButton:
        widget = UIButton(relative_rect=rect, text=text, manager=self.ui)
        self._persistent_widgets.append(widget)
        return widget

    def _build_ui(self) -> None:
        self.back_button = self._button(pygame.Rect(10, 10, 92, 38), "Back")
        self.new_button = self._button(pygame.Rect(110, 10, 82, 38), "New")
        self.duplicate_button = self._button(pygame.Rect(200, 10, 100, 38), "Duplicate")
        self.archive_button = self._button(pygame.Rect(308, 10, 92, 38), "Archive")
        self.save_button = self._button(pygame.Rect(410, 10, 86, 38), "Save")
        self.apply_button = self._button(pygame.Rect(504, 10, 86, 38), "Apply")
        self.design_tab_button = self._button(pygame.Rect(272, 58, 100, 36), "Design")
        self.behaviors_tab_button = self._button(pygame.Rect(380, 58, 110, 36), "Behaviors")
        self.code_tab_button = self._button(pygame.Rect(498, 58, 100, 36), "Code")
        self.preview_tab_button = self._button(pygame.Rect(606, 58, 100, 36), "Preview")
        workspace = self._workspace_rect()
        self.empty_new_button = self._button(
            pygame.Rect(workspace.centerx - 105, workspace.centery + 80, 210, 44),
            "Create First Entity",
        )
        self.search_entry = UITextEntryLine(
            relative_rect=pygame.Rect(10, 62, 240, 34),
            manager=self.ui,
            placeholder_text="Search entities",
        )
        self._persistent_widgets.append(self.search_entry)
        self.library_list = UISelectionList(
            relative_rect=pygame.Rect(10, 104, 240, max(120, self.surface_size[1] - 152)),
            item_list=[],
            manager=self.ui,
        )
        self._persistent_widgets.append(self.library_list)
        self.code_editor = PythonCodeEditor(self._code_rect(), DEFAULT_BEHAVIOR_SOURCE)
        self._build_design_widgets()
        self._build_behavior_widgets()
        self._build_preview_widgets()
        self._refresh_library_widget()
        self._set_tab("design")

    def _sync_project_ui(self) -> None:
        """Keep controls honest when the library has no selected project."""
        has_project = self.current is not None
        for widget in (
            self.duplicate_button,
            self.archive_button,
            self.save_button,
            self.apply_button,
            self.design_tab_button,
            self.behaviors_tab_button,
            self.code_tab_button,
            self.preview_tab_button,
        ):
            (widget.enable() if has_project else widget.disable())
        (self.empty_new_button.hide() if has_project else self.empty_new_button.show())
        self._set_tab(self.active_tab)

    def _label(self, rect: pygame.Rect, text: str, group: list[Any]) -> UILabel:
        label = UILabel(relative_rect=rect, text=text, manager=self.ui)
        group.append(label)
        return label

    def _line_entry(self, rect: pygame.Rect, text: str, group: list[Any]) -> UITextEntryLine:
        entry = UITextEntryLine(relative_rect=rect, initial_text=text, manager=self.ui)
        group.append(entry)
        return entry

    def _kill_widgets(self, widgets: list[Any]) -> None:
        for widget in widgets:
            widget.kill()
        widgets.clear()

    def _build_design_widgets(self) -> None:
        self._kill_widgets(self._design_widgets)
        definition = self.current.definition if self.current else EntityProjectDefinition("new_entity", "New Entity")
        appearance = definition.appearance
        workspace = self._workspace_rect()
        left = workspace.x + 18
        top = workspace.y + 56
        field_width = min(350, max(220, workspace.width // 3))
        self._label(pygame.Rect(left, top, 120, 28), "Name", self._design_widgets)
        self.name_entry = self._line_entry(
            pygame.Rect(left + 125, top, field_width - 125, 32), definition.name, self._design_widgets
        )
        self._label(pygame.Rect(left, top + 40, 120, 28), "Description", self._design_widgets)
        self.description_entry = UITextEntryBox(
            relative_rect=pygame.Rect(left + 125, top + 40, field_width - 125, 64),
            initial_text=definition.description,
            manager=self.ui,
        )
        self._design_widgets.append(self.description_entry)
        self._label(pygame.Rect(left, top + 114, 120, 28), "Collision radius", self._design_widgets)
        self.radius_entry = self._line_entry(
            pygame.Rect(left + 125, top + 112, 100, 32), str(definition.collision_radius), self._design_widgets
        )
        self._label(pygame.Rect(left, top + 154, 120, 28), "Appearance", self._design_widgets)
        self.appearance_kind = appearance.kind
        self.kind_dropdown = UIDropDownMenu(
            options_list=["circle", "rectangle", "sprite"],
            starting_option=appearance.kind,
            relative_rect=pygame.Rect(left + 125, top + 152, 160, 32),
            manager=self.ui,
        )
        self._design_widgets.append(self.kind_dropdown)
        self._label(pygame.Rect(left, top + 194, 120, 28), "Width / Height", self._design_widgets)
        self.width_entry = self._line_entry(
            pygame.Rect(left + 125, top + 192, 72, 32), str(appearance.size[0]), self._design_widgets
        )
        self.height_entry = self._line_entry(
            pygame.Rect(left + 205, top + 192, 72, 32), str(appearance.size[1]), self._design_widgets
        )
        self.fill_button = UIButton(
            relative_rect=pygame.Rect(left, top + 234, 132, 34), text="Fill / Tint", manager=self.ui
        )
        self.outline_button = UIButton(
            relative_rect=pygame.Rect(left + 142, top + 234, 132, 34), text="Outline", manager=self.ui
        )
        self._design_widgets.extend((self.fill_button, self.outline_button))
        self._label(pygame.Rect(left, top + 278, 120, 28), "Outline width", self._design_widgets)
        self.outline_width_entry = self._line_entry(
            pygame.Rect(left + 125, top + 274, 72, 32), str(appearance.outline_width), self._design_widgets
        )
        self._label(pygame.Rect(left, top + 318, 120, 28), "Rotation", self._design_widgets)
        self.rotation_entry = self._line_entry(
            pygame.Rect(left + 125, top + 314, 100, 32), str(appearance.rotation_degrees), self._design_widgets
        )
        self._label(pygame.Rect(left, top + 358, 120, 28), "Scale X / Y", self._design_widgets)
        self.scale_x_entry = self._line_entry(
            pygame.Rect(left + 125, top + 354, 72, 32), str(appearance.scale[0]), self._design_widgets
        )
        self.scale_y_entry = self._line_entry(
            pygame.Rect(left + 205, top + 354, 72, 32), str(appearance.scale[1]), self._design_widgets
        )
        self._label(pygame.Rect(left, top + 398, 120, 28), "Visible", self._design_widgets)
        self.visible_option = "Yes" if appearance.visible else "No"
        self.visible_dropdown = UIDropDownMenu(
            options_list=["Yes", "No"],
            starting_option=self.visible_option,
            relative_rect=pygame.Rect(left + 125, top + 394, 100, 32),
            manager=self.ui,
        )
        self._design_widgets.append(self.visible_dropdown)
        self.import_sprite_button = UIButton(
            relative_rect=pygame.Rect(left, top + 438, 188, 34), text="Import PNG Sprite", manager=self.ui
        )
        self._design_widgets.append(self.import_sprite_button)
        self._label(pygame.Rect(left, top + 482, 120, 28), "Tags", self._design_widgets)
        self.tags_entry = self._line_entry(
            pygame.Rect(left + 125, top + 480, max(100, field_width - 125), 32),
            ", ".join(definition.tags),
            self._design_widgets,
        )

        properties_left = left + field_width + 24
        properties_width = max(260, workspace.right - properties_left - 20)
        self._label(pygame.Rect(properties_left, top, 220, 28), "Declared properties", self._design_widgets)
        self.property_list = UISelectionList(
            relative_rect=pygame.Rect(properties_left, top + 32, properties_width, 145),
            item_list=self._property_labels(),
            manager=self.ui,
        )
        self._design_widgets.append(self.property_list)
        prop_y = top + 188
        self._label(pygame.Rect(properties_left, prop_y, 70, 28), "Name", self._design_widgets)
        self.property_name_entry = self._line_entry(
            pygame.Rect(properties_left + 76, prop_y, 150, 32), "", self._design_widgets
        )
        self.property_type_dropdown = UIDropDownMenu(
            options_list=sorted(PROPERTY_TYPES),
            starting_option=self.property_type,
            relative_rect=pygame.Rect(properties_left + 236, prop_y, 130, 32),
            manager=self.ui,
        )
        self._design_widgets.append(self.property_type_dropdown)
        self._label(pygame.Rect(properties_left, prop_y + 42, 70, 28), "Default", self._design_widgets)
        self.property_default_entry = self._line_entry(
            pygame.Rect(properties_left + 76, prop_y + 40, 290, 32), "0.0", self._design_widgets
        )
        self._label(pygame.Rect(properties_left, prop_y + 82, 70, 28), "Inspector", self._design_widgets)
        self.property_inspector_dropdown = UIDropDownMenu(
            options_list=["Yes", "No"],
            starting_option="Yes",
            relative_rect=pygame.Rect(properties_left + 76, prop_y + 80, 100, 32),
            manager=self.ui,
        )
        self._design_widgets.append(self.property_inspector_dropdown)
        self.property_add_button = UIButton(
            relative_rect=pygame.Rect(properties_left, prop_y + 124, 110, 34), text="Add / Update", manager=self.ui
        )
        self.property_clear_button = UIButton(
            relative_rect=pygame.Rect(properties_left + 120, prop_y + 124, 92, 34), text="Clear", manager=self.ui
        )
        self.property_remove_button = UIButton(
            relative_rect=pygame.Rect(properties_left + 222, prop_y + 124, 92, 34), text="Remove", manager=self.ui
        )
        self._design_widgets.extend(
            (self.property_add_button, self.property_clear_button, self.property_remove_button)
        )
        self.fill_color = appearance.fill_color
        self.outline_color = appearance.outline_color
        self.sprite_path = appearance.sprite

    def _build_behavior_widgets(self) -> None:
        self._kill_widgets(self._behavior_widgets)
        self.behavior_parameter_entries.clear()
        workspace = self._workspace_rect()
        left = workspace.x + 18
        top = workspace.y + 56
        left_width = min(350, max(280, workspace.width // 3))
        gap = 20
        right = left + left_width + gap
        right_width = max(280, workspace.right - right - 18)

        self._label(
            pygame.Rect(left, top, left_width, 28),
            "Attached stack (top to bottom)",
            self._behavior_widgets,
        )
        self._attachment_labels.clear()
        attachment_items: list[str] = []
        for attachment in self.attachments:
            project = self.behavior_registry.catalog.get(attachment.behavior_id)
            name = project.definition.name if project else attachment.behavior_id
            label = f"{'On' if attachment.enabled else 'Off'} · {name} [{attachment.attachment_id}]"
            attachment_items.append(label)
            self._attachment_labels[label] = attachment.attachment_id
        self.attachment_list = UISelectionList(
            pygame.Rect(left, top + 30, left_width, 158),
            attachment_items,
            self.ui,
        )
        self._behavior_widgets.append(self.attachment_list)
        button_y = top + 198
        self.behavior_remove_button = UIButton(
            pygame.Rect(left, button_y, 74, 32), "Remove", self.ui
        )
        self.behavior_up_button = UIButton(
            pygame.Rect(left + 80, button_y, 54, 32), "Up", self.ui
        )
        self.behavior_down_button = UIButton(
            pygame.Rect(left + 140, button_y, 64, 32), "Down", self.ui
        )
        self.behavior_toggle_button = UIButton(
            pygame.Rect(left + 210, button_y, 70, 32), "On/Off", self.ui
        )
        self.behavior_duplicate_attachment_button = UIButton(
            pygame.Rect(left + 286, button_y, 64, 32), "Copy", self.ui
        )
        self._behavior_widgets.extend(
            (
                self.behavior_remove_button,
                self.behavior_up_button,
                self.behavior_down_button,
                self.behavior_toggle_button,
                self.behavior_duplicate_attachment_button,
            )
        )

        self._label(
            pygame.Rect(right, top, right_width, 28),
            "Behavior library",
            self._behavior_widgets,
        )
        self.behavior_search_entry = UITextEntryLine(
            pygame.Rect(right, top + 30, max(120, right_width - 170), 32),
            self.ui,
            initial_text=self.behavior_search_text,
            placeholder_text="Search behaviors",
        )
        self.behavior_category_dropdown = UIDropDownMenu(
            ["all", *sorted(BEHAVIOR_CATEGORIES)],
            self.behavior_category,
            pygame.Rect(right + max(126, right_width - 162), top + 30, 162, 32),
            self.ui,
        )
        self._behavior_widgets.extend(
            (self.behavior_search_entry, self.behavior_category_dropdown)
        )
        self._available_behavior_labels.clear()
        available_items: list[str] = []
        search = self.behavior_search_text.casefold().strip()
        for project in self.behavior_registry.catalog.projects:
            definition = project.definition
            if self.behavior_category != "all" and definition.category != self.behavior_category:
                continue
            haystack = f"{definition.name} {definition.id} {definition.description}".casefold()
            if search and search not in haystack:
                continue
            label = f"{definition.name} · {definition.category}{' · built-in' if project.builtin else ''}"
            available_items.append(label)
            self._available_behavior_labels[label] = definition.id
        self.available_behavior_list = UISelectionList(
            pygame.Rect(right, top + 68, right_width, 120),
            available_items,
            self.ui,
        )
        self.behavior_add_button = UIButton(
            pygame.Rect(right, button_y, 110, 32), "Add Behavior", self.ui
        )
        self.behavior_open_button = UIButton(
            pygame.Rect(right + 118, button_y, 170, 32), "Open in Studio", self.ui
        )
        self._behavior_widgets.extend(
            (
                self.available_behavior_list,
                self.behavior_add_button,
                self.behavior_open_button,
            )
        )

        selected = next(
            (
                item
                for item in self.attachments
                if item.attachment_id == self.selected_attachment
            ),
            None,
        )
        if selected is not None:
            project = self.behavior_registry.catalog.get(selected.behavior_id)
            if project is not None:
                parameter_y = top + 250
                self._label(
                    pygame.Rect(left, parameter_y, workspace.width - 36, 26),
                    f"Configure {project.definition.name} ({selected.attachment_id})",
                    self._behavior_widgets,
                )
                config = project.definition.normalized_config(selected.parameters)
                for index, parameter in enumerate(project.definition.parameters):
                    column = index % 2
                    row = index // 2
                    x = left + column * max(300, (workspace.width - 54) // 2)
                    y = parameter_y + 34 + row * 42
                    self._label(
                        pygame.Rect(x, y, 126, 30),
                        parameter.name.replace("_", " ").title(),
                        self._behavior_widgets,
                    )
                    value = config[parameter.name]
                    if parameter.type == "str":
                        text = str(value)
                    else:
                        import json

                        text = json.dumps(value)
                    widget_rect = pygame.Rect(x + 132, y, 158, 32)
                    if parameter.editor == "choice":
                        options = list(parameter.choices)
                    elif parameter.editor == "property":
                        options = [item.name for item in self.properties]
                    elif parameter.editor == "project":
                        options = ["<none>"] + [
                            item.definition.id
                            for item in self.entity_registry.catalog.projects
                        ]
                    elif parameter.editor == "tag":
                        options = sorted(
                            {
                                "food",
                                "organism",
                                "predator",
                                "target",
                                "threat",
                                *self.tags,
                            }
                        )
                    else:
                        options = []
                    if options:
                        selected_text = "<none>" if text == "" else text
                        if selected_text not in options:
                            options.insert(0, selected_text)
                        entry = UIDropDownMenu(
                            options,
                            selected_text,
                            widget_rect,
                            self.ui,
                        )
                        self._behavior_widgets.append(entry)
                    else:
                        entry = self._line_entry(
                            widget_rect,
                            text,
                            self._behavior_widgets,
                        )
                    self.behavior_parameter_entries[parameter.name] = entry

        if self.active_tab != "behaviors" or self.current is None:
            for widget in self._behavior_widgets:
                widget.hide()

    def _build_preview_widgets(self) -> None:
        self._kill_widgets(self._preview_widgets)
        workspace = self._workspace_rect()
        y = workspace.y + 10
        x = workspace.x + 12
        self.preview_run_button = UIButton(
            relative_rect=pygame.Rect(x, y, 72, 34), text="Run", manager=self.ui
        )
        self.preview_pause_button = UIButton(
            relative_rect=pygame.Rect(x + 80, y, 76, 34), text="Pause", manager=self.ui
        )
        self.preview_step_button = UIButton(
            relative_rect=pygame.Rect(x + 164, y, 70, 34), text="Step", manager=self.ui
        )
        self.preview_reset_button = UIButton(
            relative_rect=pygame.Rect(x + 242, y, 72, 34), text="Reset", manager=self.ui
        )
        self._label(pygame.Rect(x + 322, y, 40, 34), "Seed", self._preview_widgets)
        self.preview_seed_entry = UITextEntryLine(
            relative_rect=pygame.Rect(x + 362, y, 76, 34), initial_text="1", manager=self.ui
        )
        self._label(pygame.Rect(x + 446, y, 48, 34), "Count", self._preview_widgets)
        self.preview_instances_entry = UITextEntryLine(
            relative_rect=pygame.Rect(x + 496, y, 58, 34), initial_text="1", manager=self.ui
        )
        self._label(pygame.Rect(x + 562, y, 48, 34), "Speed", self._preview_widgets)
        self.preview_speed_dropdown = UIDropDownMenu(
            options_list=["0.25x", "1x", "2x", "4x"],
            starting_option="1x",
            relative_rect=pygame.Rect(x + 612, y, 82, 34),
            manager=self.ui,
        )
        self._preview_widgets.extend(
            (
                self.preview_run_button,
                self.preview_pause_button,
                self.preview_step_button,
                self.preview_reset_button,
                self.preview_seed_entry,
                self.preview_instances_entry,
                self.preview_speed_dropdown,
            )
        )

    def _property_labels(self) -> list[str]:
        return [f"{item.name} : {item.type}" for item in self.properties]

    def _refresh_property_widget(self) -> None:
        rect = self.property_list.relative_rect.copy()
        self.property_list.kill()
        self.property_list = UISelectionList(
            relative_rect=rect,
            item_list=self._property_labels(),
            manager=self.ui,
        )
        self._design_widgets.append(self.property_list)
        if self.active_tab != "design":
            self.property_list.hide()

    def _refresh_library_widget(self) -> None:
        self.catalog = self.store.scan()
        labels: list[str] = []
        self._library_labels.clear()
        search = self.search_text.casefold().strip()
        for project in self.catalog.projects:
            label = f"{project.definition.name}  [{project.definition.id}]"
            if search and search not in label.casefold():
                continue
            labels.append(label)
            self._library_labels[label] = project.definition.id
        old = self.library_list
        rect = old.relative_rect.copy()
        old.kill()
        self.library_list = UISelectionList(
            relative_rect=rect, item_list=labels, manager=self.ui
        )
        self._persistent_widgets.append(self.library_list)

    def _set_tab(self, tab: str) -> None:
        self.active_tab = tab
        if self.current is None:
            for widget in self._design_widgets:
                widget.hide()
            for widget in self._behavior_widgets:
                widget.hide()
            for widget in self._preview_widgets:
                widget.hide()
            self.code_editor.focused = False
            return
        for widget in self._design_widgets:
            (widget.show() if tab == "design" else widget.hide())
        for widget in self._behavior_widgets:
            (widget.show() if tab == "behaviors" else widget.hide())
        for widget in self._preview_widgets:
            (widget.show() if tab == "preview" else widget.hide())
        self.code_editor.focused = tab == "code"

    def _load_project(self, project: EntityProject) -> None:
        self.preview.stop()
        self.preview_definition = None
        self.preview_terrain = None
        self.preview_terrain_renderer = None
        self.preview_camera = None
        self.current = project
        self.saved_behavior = project.behavior_source
        self.properties = list(project.definition.properties)
        self.tags = list(project.definition.tags)
        self.attachments = list(project.definition.behaviors)
        self.selected_attachment = (
            self.attachments[0].attachment_id if self.attachments else None
        )
        self.selected_property = None
        self.code_editor.set_text(project.behavior_source)
        self.code_editor.set_diagnostics(())
        self.dirty = False
        self.status_message = f"Loaded {project.definition.name}."
        self.status_is_error = False
        self._build_design_widgets()
        self._build_behavior_widgets()
        self.preview_seed_entry.set_text(str(project.definition.preview.seed))
        self.preview_instances_entry.set_text(str(project.definition.preview.instances))
        self._sync_project_ui()

    def _project_by_id(self, project_id: str) -> EntityProject | None:
        return self.catalog.get(project_id)

    @staticmethod
    def _parse_default(property_type: str, text: str) -> object:
        import json

        if property_type == "float":
            return float(text)
        if property_type == "int":
            return int(text)
        if property_type == "bool":
            lowered = text.strip().casefold()
            if lowered not in ("true", "false"):
                raise ValueError("boolean defaults must be true or false")
            return lowered == "true"
        if property_type == "str":
            return text
        return json.loads(text)

    def _commit_behavior_parameters(self) -> None:
        if self.selected_attachment is None or not self.behavior_parameter_entries:
            return
        index = next(
            (
                index
                for index, item in enumerate(self.attachments)
                if item.attachment_id == self.selected_attachment
            ),
            None,
        )
        if index is None:
            return
        attachment = self.attachments[index]
        project = self.behavior_registry.require(attachment.behavior_id)
        values: dict[str, object] = {}
        for parameter in project.definition.parameters:
            entry = self.behavior_parameter_entries.get(parameter.name)
            if entry is None:
                continue
            if hasattr(entry, "get_text"):
                text = entry.get_text()
            else:
                text = entry.selected_option[0]
                if text == "<none>":
                    text = ""
            values[parameter.name] = self._parse_default(parameter.type, text)
        normalized = project.definition.normalized_config(values)
        self.attachments[index] = BehaviorAttachment(
            attachment.attachment_id,
            attachment.behavior_id,
            attachment.enabled,
            dict(normalized),
        )

    def _definition_from_forms(self) -> EntityProjectDefinition:
        if self.current is None:
            raise EntityProjectValidationError("select or create a project first")
        self._commit_behavior_parameters()
        appearance = AppearanceDefinition.from_mapping(
            {
                "kind": self.appearance_kind,
                "size": [float(self.width_entry.get_text()), float(self.height_entry.get_text())],
                "fill_color": list(self.fill_color),
                "outline_color": list(self.outline_color),
                "outline_width": int(self.outline_width_entry.get_text()),
                "rotation_degrees": float(self.rotation_entry.get_text()),
                "scale": [float(self.scale_x_entry.get_text()), float(self.scale_y_entry.get_text())],
                "visible": self.visible_option == "Yes",
                "sprite": self.sprite_path if self.appearance_kind == "sprite" else None,
            },
            self.current.directory,
        )
        preview = PreviewSettings.from_mapping(
            {
                "seed": int(self.preview_seed_entry.get_text()),
                "instances": int(self.preview_instances_entry.get_text()),
            }
        )
        definition = EntityProjectDefinition(
            id=self.current.definition.id,
            name=self.name_entry.get_text().strip(),
            description=self.description_entry.get_text(),
            collision_radius=float(self.radius_entry.get_text()),
            properties=tuple(self.properties),
            tags=tuple(
                dict.fromkeys(
                    tag.strip()
                    for tag in self.tags_entry.get_text().split(",")
                    if tag.strip()
                )
            ),
            behaviors=tuple(self.attachments),
            appearance=appearance,
            preview=preview,
        )
        return EntityProjectDefinition.from_json(
            definition.to_json(), self.current.directory
        )

    def _set_error(self, message: str) -> None:
        self.status_message = message
        self.status_is_error = True

    def _set_success(self, message: str) -> None:
        self.status_message = message
        self.status_is_error = False

    def apply(self) -> bool:
        try:
            definition = self._definition_from_forms()
            self.entity_registry.refresh()
            validation = self.entity_registry.validate(definition)
            diagnostics = validate_behavior_source(self.code_editor.text)
            self.code_editor.set_diagnostics(diagnostics)
            if diagnostics:
                first = diagnostics[0]
                raise EntityProjectValidationError(
                    f"behavior.py:{first.line}:{first.column + 1}: {first.message}"
                )
            assert self.current is not None
            self.preview.apply(
                definition,
                self.code_editor.text,
                self.current.directory,
            )
            self.preview_definition = definition
            self._prepare_preview_scene(definition.preview.seed)
            if validation.warnings:
                self._set_success(
                    "Applied draft. " + " ".join(validation.warnings)
                )
            else:
                self._set_success("Applied draft to isolated preview.")
            return True
        except Exception as exc:
            self._set_error(str(exc))
            return False

    def save(self) -> bool:
        try:
            definition = self._definition_from_forms()
            self.entity_registry.refresh()
            self.entity_registry.validate(definition)
            saved = self.store.save(definition, self.code_editor.text)
            self.current = saved
            self.saved_behavior = saved.behavior_source
            self.dirty = False
            self._refresh_library_widget()
            self.entity_registry.refresh()
            if self.apply():
                self._set_success(f"Saved {saved.definition.name}.")
            return True
        except Exception as exc:
            self._set_error(str(exc))
            return False

    def _prepare_preview_scene(self, seed: int) -> None:
        terrain = TerrainMap(
            seed,
            width=PREVIEW_MAP_TILES,
            height=PREVIEW_MAP_TILES,
            tile_size=16,
        )
        self.preview_terrain = terrain
        self.preview_terrain_renderer = TerrainRenderer(terrain, chunk_tiles=16)
        rect = self._preview_rect()
        fit_zoom = 0.92 * min(
            rect.width / terrain.pixel_width,
            rect.height / terrain.pixel_height,
        )
        self.preview_camera = Camera2D(
            terrain.pixel_width / 2,
            terrain.pixel_height / 2,
            rect.width,
            rect.height,
            zoom=max(0.25, min(4.0, fit_zoom)),
            min_zoom=0.25,
            max_zoom=4.0,
            world_width=terrain.pixel_width,
            world_height=terrain.pixel_height,
        )
        self.preview_camera.clamp()

    def _show_prompt(self, kind: str) -> None:
        if self.prompt_window is not None:
            self.prompt_window.kill()
        width, height = self.surface_size
        self.prompt_kind = kind
        self.prompt_window = UIWindow(
            rect=pygame.Rect(width // 2 - 190, height // 2 - 125, 380, 250),
            manager=self.ui,
            window_display_title="New entity" if kind == "new" else "Duplicate entity",
            object_id="#entity_prompt",
        )
        container = self.prompt_window
        UILabel(pygame.Rect(16, 22, 90, 30), "Entity ID", self.ui, container=container)
        self.prompt_id_entry = UITextEntryLine(
            pygame.Rect(112, 22, 230, 32), self.ui, container=container
        )
        UILabel(pygame.Rect(16, 66, 90, 30), "Name", self.ui, container=container)
        self.prompt_name_entry = UITextEntryLine(
            pygame.Rect(112, 66, 230, 32), self.ui, container=container
        )
        if kind == "duplicate" and self.current is not None:
            self.prompt_id_entry.set_text(f"{self.current.definition.id}_copy")
            self.prompt_name_entry.set_text(f"{self.current.definition.name} Copy")
        self.prompt_ok_button = UIButton(
            pygame.Rect(112, 128, 110, 36), "Create", self.ui, container=container
        )

    def _complete_prompt(self) -> None:
        if self.prompt_id_entry is None or self.prompt_name_entry is None:
            return
        project_id = self.prompt_id_entry.get_text().strip()
        name = self.prompt_name_entry.get_text().strip()
        try:
            if self.prompt_kind == "duplicate" and self.current is not None:
                project = self.store.duplicate(self.current.definition.id, project_id, name)
            else:
                project = self.store.create_default(project_id, name)
            self._refresh_library_widget()
            self._load_project(project)
            self._set_success(f"Created {name}.")
            if self.prompt_window is not None:
                self.prompt_window.kill()
            self.prompt_window = None
        except Exception as exc:
            self._set_error(str(exc))

    def _confirm(self, action: str, argument: str | None, message: str) -> None:
        self.pending_action = (action, argument)
        width, height = self.surface_size
        self.confirmation = UIConfirmationDialog(
            rect=pygame.Rect(width // 2 - 210, height // 2 - 100, 420, 200),
            manager=self.ui,
            window_title="Confirm",
            action_long_desc=message,
            action_short_name="Confirm",
            blocking=True,
        )

    def request_exit(self, kind: str = "back") -> EntityEditorAction | None:
        if self.dirty:
            self._confirm(kind, None, "Discard unsaved changes?")
            return None
        return EntityEditorAction(kind)

    def _execute_pending(self) -> EntityEditorAction | None:
        pending = self.pending_action
        self.pending_action = None
        self.confirmation = None
        if pending is None:
            return None
        action, argument = pending
        if action in ("back", "quit"):
            return EntityEditorAction(action)
        if action == "open" and argument is not None:
            project = self._project_by_id(argument)
            if project is not None:
                self._load_project(project)
        elif action == "archive" and self.current is not None:
            archived_name = self.current.definition.name
            self.store.archive(self.current.definition.id)
            self.current = None
            self.preview.stop()
            self._refresh_library_widget()
            if self.catalog.projects:
                self._load_project(self.catalog.projects[0])
            else:
                self.code_editor.set_text(DEFAULT_BEHAVIOR_SOURCE)
                self._build_design_widgets()
                self._build_behavior_widgets()
                self._sync_project_ui()
            self._set_success(f"Archived {archived_name}; it can be recovered from .trash.")
        elif action == "add_behavior" and argument is not None:
            try:
                self._attach_behavior(argument, add_requirements=True)
            except Exception as exc:
                self._set_error(str(exc))
        return None

    def _clear_property_form(self) -> None:
        self.selected_property = None
        self.property_name_entry.set_text("")
        self.property_default_entry.set_text("0.0")
        self.property_type = "float"
        self.property_inspector_option = "Yes"
        self.property_type_dropdown = self._replace_dropdown(
            self.property_type_dropdown, sorted(PROPERTY_TYPES), self.property_type
        )
        self.property_inspector_dropdown = self._replace_dropdown(
            self.property_inspector_dropdown, ["Yes", "No"], self.property_inspector_option
        )

    def _replace_dropdown(
        self, dropdown: UIDropDownMenu, options: list[str], selected: str
    ) -> UIDropDownMenu:
        """Replace a pygame_gui dropdown so its displayed selection is updated."""
        index = self._design_widgets.index(dropdown)
        rect = dropdown.relative_rect.copy()
        visible = int(bool(dropdown.visible))
        dropdown.kill()
        replacement = UIDropDownMenu(
            options_list=options,
            starting_option=selected,
            relative_rect=rect,
            manager=self.ui,
            visible=visible,
        )
        self._design_widgets[index] = replacement
        return replacement

    def _select_property(self, label: str) -> None:
        name = label.split(" : ", 1)[0]
        item = next((prop for prop in self.properties if prop.name == name), None)
        if item is None:
            return
        self.selected_property = item.name
        self.property_name_entry.set_text(item.name)
        self.property_type = item.type
        self.property_inspector_option = "Yes" if item.inspector else "No"
        self.property_type_dropdown = self._replace_dropdown(
            self.property_type_dropdown, sorted(PROPERTY_TYPES), self.property_type
        )
        self.property_inspector_dropdown = self._replace_dropdown(
            self.property_inspector_dropdown, ["Yes", "No"], self.property_inspector_option
        )
        if isinstance(item.default, str):
            default_text = item.default
        else:
            import json

            default_text = json.dumps(item.default)
        self.property_default_entry.set_text(default_text)

    def _add_or_update_property(self) -> None:
        try:
            default = self._parse_default(
                self.property_type, self.property_default_entry.get_text()
            )
            item = PropertyDefinition.from_mapping(
                {
                    "name": self.property_name_entry.get_text().strip(),
                    "type": self.property_type,
                    "default": default,
                    "inspector": self.property_inspector_option == "Yes",
                }
            )
            existing = next(
                (index for index, prop in enumerate(self.properties) if prop.name == self.selected_property),
                None,
            )
            if existing is None:
                if any(prop.name == item.name for prop in self.properties):
                    raise ValueError(f"property {item.name!r} already exists")
                self.properties.append(item)
            else:
                if any(
                    index != existing and prop.name == item.name
                    for index, prop in enumerate(self.properties)
                ):
                    raise ValueError(f"property {item.name!r} already exists")
                self.properties[existing] = item
            self.selected_property = item.name
            self.dirty = True
            self._refresh_property_widget()
            self._set_success(f"Updated property {item.name}.")
        except Exception as exc:
            self._set_error(str(exc))

    def _remove_property(self) -> None:
        if self.selected_property is None:
            return
        self.properties = [
            item for item in self.properties if item.name != self.selected_property
        ]
        self._clear_property_form()
        self._refresh_property_widget()
        self.dirty = True

    def _unique_attachment_id(self, behavior_id: str) -> str:
        used = {item.attachment_id for item in self.attachments}
        if behavior_id not in used:
            return behavior_id
        suffix = 2
        while f"{behavior_id}_{suffix}" in used:
            suffix += 1
        return f"{behavior_id}_{suffix}"

    def _attach_behavior(self, behavior_id: str, *, add_requirements: bool) -> None:
        project = self.behavior_registry.require(behavior_id)
        definition = project.definition
        if not definition.allow_multiple and any(
            item.behavior_id == behavior_id for item in self.attachments
        ):
            raise EntityProjectValidationError(
                f"{definition.name} can only be attached once"
            )
        existing = {item.name: item for item in self.properties}
        missing = [
            item for item in definition.required_properties if item.name not in existing
        ]
        mismatched = [
            item
            for item in definition.required_properties
            if item.name in existing and existing[item.name].type != item.type
        ]
        if mismatched:
            item = mismatched[0]
            raise EntityProjectValidationError(
                f"property {item.name!r} must have type {item.type} for {definition.name}"
            )
        if missing and not add_requirements:
            names = ", ".join(f"{item.name} ({item.type})" for item in missing)
            self._confirm(
                "add_behavior",
                behavior_id,
                f"{definition.name} requires {names}. Add the missing properties?",
            )
            return
        if missing:
            self.properties.extend(missing)
            self._refresh_property_widget()
        attachment = BehaviorAttachment(
            self._unique_attachment_id(behavior_id), behavior_id, True, {}
        )
        self.attachments.append(attachment)
        self.selected_attachment = attachment.attachment_id
        self.dirty = True
        self._build_behavior_widgets()
        self._set_tab("behaviors")
        self._set_success(f"Attached {definition.name}.")

    def _selected_attachment_index(self) -> int | None:
        return next(
            (
                index
                for index, item in enumerate(self.attachments)
                if item.attachment_id == self.selected_attachment
            ),
            None,
        )

    def _remove_attachment(self) -> None:
        index = self._selected_attachment_index()
        if index is None:
            return
        removed = self.attachments.pop(index)
        self.selected_attachment = (
            self.attachments[min(index, len(self.attachments) - 1)].attachment_id
            if self.attachments
            else None
        )
        self.dirty = True
        self._build_behavior_widgets()
        self._set_success(f"Removed attachment {removed.attachment_id}.")

    def _move_attachment(self, direction: int) -> None:
        self._commit_behavior_parameters()
        index = self._selected_attachment_index()
        if index is None:
            return
        destination = max(0, min(len(self.attachments) - 1, index + direction))
        if destination == index:
            return
        attachment = self.attachments.pop(index)
        self.attachments.insert(destination, attachment)
        self.dirty = True
        self._build_behavior_widgets()

    def _toggle_attachment(self) -> None:
        self._commit_behavior_parameters()
        index = self._selected_attachment_index()
        if index is None:
            return
        item = self.attachments[index]
        self.attachments[index] = BehaviorAttachment(
            item.attachment_id, item.behavior_id, not item.enabled, item.parameters
        )
        self.dirty = True
        self._build_behavior_widgets()

    def _duplicate_attachment(self) -> None:
        self._commit_behavior_parameters()
        index = self._selected_attachment_index()
        if index is None:
            return
        item = self.attachments[index]
        project = self.behavior_registry.require(item.behavior_id)
        if not project.definition.allow_multiple:
            raise EntityProjectValidationError(
                f"{project.definition.name} does not allow multiple attachments"
            )
        copy = BehaviorAttachment(
            self._unique_attachment_id(item.behavior_id),
            item.behavior_id,
            item.enabled,
            dict(item.parameters),
        )
        self.attachments.insert(index + 1, copy)
        self.selected_attachment = copy.attachment_id
        self.dirty = True
        self._build_behavior_widgets()

    def _mark_form_dirty(self, event: pygame.event.Event) -> None:
        design_entries = {
            self.name_entry,
            self.description_entry,
            self.radius_entry,
            self.width_entry,
            self.height_entry,
            self.outline_width_entry,
            self.rotation_entry,
            self.scale_x_entry,
            self.scale_y_entry,
            self.tags_entry,
        }
        element = getattr(event, "ui_element", None)
        if element in design_entries or element in self.behavior_parameter_entries.values():
            self.dirty = True

    def _handle_gui_event(self, event: pygame.event.Event) -> EntityEditorAction | None:
        if event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            if event.ui_element == self.search_entry:
                self.search_text = event.text
                self._refresh_library_widget()
            elif event.ui_element == self.behavior_search_entry:
                try:
                    self._commit_behavior_parameters()
                except Exception as exc:
                    self._set_error(str(exc))
                    return None
                self.behavior_search_text = event.text
                self._build_behavior_widgets()
                self._set_tab("behaviors")
            else:
                self._mark_form_dirty(event)
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element == self.library_list:
                project_id = self._library_labels.get(event.text)
                if project_id is not None and (
                    self.current is None or project_id != self.current.definition.id
                ):
                    if self.dirty:
                        self._confirm("open", project_id, "Discard changes and open the selected project?")
                    else:
                        project = self._project_by_id(project_id)
                        if project is not None:
                            self._load_project(project)
            elif event.ui_element == self.property_list:
                self._select_property(event.text)
            elif event.ui_element == self.attachment_list:
                try:
                    self._commit_behavior_parameters()
                    self.selected_attachment = self._attachment_labels.get(event.text)
                    self._build_behavior_widgets()
                    self._set_tab("behaviors")
                except Exception as exc:
                    self._set_error(str(exc))
            elif event.ui_element == self.available_behavior_list:
                self.selected_behavior_project = self._available_behavior_labels.get(
                    event.text
                )
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.kind_dropdown:
                self.appearance_kind = event.text
                self.dirty = True
            elif event.ui_element == self.visible_dropdown:
                self.visible_option = event.text
                self.dirty = True
            elif event.ui_element == self.property_type_dropdown:
                self.property_type = event.text
            elif event.ui_element == self.property_inspector_dropdown:
                self.property_inspector_option = event.text
            elif event.ui_element == self.behavior_category_dropdown:
                try:
                    self._commit_behavior_parameters()
                except Exception as exc:
                    self._set_error(str(exc))
                    return None
                self.behavior_category = event.text
                self.selected_behavior_project = None
                self._build_behavior_widgets()
                self._set_tab("behaviors")
            elif event.ui_element == self.preview_speed_dropdown:
                self.preview_speed = float(event.text.rstrip("x"))
                self.preview.set_speed(self.preview_speed)
            elif event.ui_element in self.behavior_parameter_entries.values():
                self.dirty = True
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            element = event.ui_element
            if element == self.back_button:
                return self.request_exit("back")
            if element == self.new_button:
                if self.dirty:
                    self._set_error("Save or discard changes before creating another project.")
                else:
                    self._show_prompt("new")
            elif element == self.empty_new_button:
                self._show_prompt("new")
            elif element == self.duplicate_button and self.current is not None:
                if self.dirty:
                    self._set_error("Save or discard changes before duplicating this project.")
                else:
                    self._show_prompt("duplicate")
            elif element == self.archive_button and self.current is not None:
                self._confirm("archive", None, f"Archive {self.current.definition.name}? This moves it to .trash.")
            elif element == self.save_button:
                self.save()
            elif element == self.apply_button:
                self.apply()
            elif element == self.design_tab_button:
                self._set_tab("design")
            elif element == self.behaviors_tab_button:
                self._set_tab("behaviors")
            elif element == self.code_tab_button:
                self._set_tab("code")
            elif element == self.preview_tab_button:
                self._set_tab("preview")
                self.apply()
            elif element == self.fill_button:
                self.color_target = "fill"
                self.color_dialog = UIColourPickerDialog(
                    pygame.Rect(self.surface_size[0] // 2 - 195, 110, 390, 390),
                    self.ui,
                    initial_colour=pygame.Color(*self.fill_color),
                    window_title="Fill / tint color",
                )
            elif element == self.outline_button:
                self.color_target = "outline"
                self.color_dialog = UIColourPickerDialog(
                    pygame.Rect(self.surface_size[0] // 2 - 195, 110, 390, 390),
                    self.ui,
                    initial_colour=pygame.Color(*self.outline_color),
                    window_title="Outline color",
                )
            elif element == self.import_sprite_button and self.current is not None:
                self.file_dialog = UIFileDialog(
                    pygame.Rect(self.surface_size[0] // 2 - 320, 70, 640, 500),
                    self.ui,
                    window_title="Choose a PNG sprite",
                    initial_file_path=str(Path.cwd()),
                    allowed_suffixes={".png"},
                    allow_existing_files_only=True,
                    allow_picking_directories=False,
                )
            elif element == self.property_add_button:
                self._add_or_update_property()
            elif element == self.property_clear_button:
                self._clear_property_form()
            elif element == self.property_remove_button:
                self._remove_property()
            elif element == self.behavior_add_button:
                if self.selected_behavior_project is None:
                    self._set_error("Select a behavior from the library first.")
                else:
                    try:
                        self._attach_behavior(
                            self.selected_behavior_project, add_requirements=False
                        )
                    except Exception as exc:
                        self._set_error(str(exc))
            elif element == self.behavior_remove_button:
                self._remove_attachment()
            elif element == self.behavior_up_button:
                try:
                    self._move_attachment(-1)
                except Exception as exc:
                    self._set_error(str(exc))
            elif element == self.behavior_down_button:
                try:
                    self._move_attachment(1)
                except Exception as exc:
                    self._set_error(str(exc))
            elif element == self.behavior_toggle_button:
                try:
                    self._toggle_attachment()
                except Exception as exc:
                    self._set_error(str(exc))
            elif element == self.behavior_duplicate_attachment_button:
                try:
                    self._duplicate_attachment()
                except Exception as exc:
                    self._set_error(str(exc))
            elif element == self.behavior_open_button:
                behavior_id = self.selected_behavior_project
                index = self._selected_attachment_index()
                if index is not None:
                    behavior_id = self.attachments[index].behavior_id
                if behavior_id is None:
                    self._set_error("Select an attached or library behavior first.")
                elif self.dirty:
                    self._set_error(
                        "Save the entity before opening Behavior Studio so draft changes are not lost."
                    )
                else:
                    return EntityEditorAction("behavior_editor", behavior_id)
            elif element == self.preview_run_button:
                if self.preview.status.loaded or self.apply():
                    self.preview.pause(False)
            elif element == self.preview_pause_button:
                self.preview_paused = not self.preview_paused
                self.preview.pause(self.preview_paused)
            elif element == self.preview_step_button:
                self.preview.step()
            elif element == self.preview_reset_button:
                self._reset_preview()
            elif element == self.prompt_ok_button:
                self._complete_prompt()
        elif event.type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
            if event.ui_element == self.confirmation:
                return self._execute_pending()
        elif event.type == pygame_gui.UI_FILE_DIALOG_PATH_PICKED:
            if event.ui_element == self.file_dialog and self.current is not None:
                try:
                    self.sprite_path = self.store.import_sprite(
                        self.current.definition.id, Path(event.text)
                    )
                    self.dirty = True
                    self.appearance_renderer.clear()
                    self._set_success(f"Imported {self.sprite_path}.")
                except Exception as exc:
                    self._set_error(str(exc))
        elif event.type == pygame_gui.UI_COLOUR_PICKER_COLOUR_PICKED:
            if event.ui_element == self.color_dialog:
                color = tuple(event.colour)
                if self.color_target == "fill":
                    self.fill_color = color
                else:
                    self.outline_color = color
                self.dirty = True
        elif event.type == pygame_gui.UI_WINDOW_CLOSE:
            element = event.ui_element
            if element == self.confirmation:
                self.confirmation = None
                self.pending_action = None
            elif element == self.prompt_window:
                self.prompt_window = None
            elif element == self.file_dialog:
                self.file_dialog = None
            elif element == self.color_dialog:
                self.color_dialog = None
        return None

    def _reset_preview(self) -> None:
        try:
            seed = int(self.preview_seed_entry.get_text())
            instances = int(self.preview_instances_entry.get_text())
            settings = PreviewSettings.from_mapping({"seed": seed, "instances": instances})
            self.preview.reset(settings.seed, settings.instances)
            self._prepare_preview_scene(settings.seed)
        except Exception as exc:
            self._set_error(str(exc))

    def handle_event(self, event: pygame.event.Event) -> EntityEditorAction | None:
        self.ui.process_events(event)
        code_shortcut_handled = False
        find_was_active = self.code_editor.find_active
        if self.active_tab == "code":
            action = self.code_editor.handle_event(event)
            if action is not None:
                code_shortcut_handled = True
                if action.kind == "save":
                    self.save()
                elif action.kind == "apply":
                    self.apply()
        if event.type == pygame.KEYDOWN:
            if (
                event.key == pygame.K_ESCAPE
                and not find_was_active
                and self.prompt_window is None
                and self.confirmation is None
            ):
                return self.request_exit("back")
            if (
                not code_shortcut_handled
                and event.key == pygame.K_s
                and event.mod & pygame.KMOD_CTRL
            ):
                self.save()
            elif not code_shortcut_handled and event.key == pygame.K_F5:
                self.apply()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2 and self.active_tab == "preview":
            if self._preview_rect().collidepoint(event.pos):
                self._preview_dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._preview_dragging = False
        elif event.type == pygame.MOUSEMOTION and self._preview_dragging and self.preview_camera is not None:
            self.preview_camera.pan(
                -event.rel[0] / self.preview_camera.zoom,
                -event.rel[1] / self.preview_camera.zoom,
            )
        elif event.type == pygame.MOUSEWHEEL and self.active_tab == "preview" and self.preview_camera is not None:
            rect = self._preview_rect()
            mouse = pygame.mouse.get_pos()
            if rect.collidepoint(mouse):
                self.preview_camera.zoom_at(
                    1.15**event.y, mouse[0] - rect.x, mouse[1] - rect.y
                )
        return self._handle_gui_event(event)

    def update(self, real_dt: float) -> None:
        self.ui.update(real_dt)
        if self.current is not None and self.code_editor.text != self.saved_behavior:
            self.dirty = True
        status = self.preview.poll()
        if status.snapshot is not None:
            self.preview_paused = bool(status.snapshot.get("paused", False))
            self.preview_pause_button.set_text("Resume" if self.preview_paused else "Pause")
        if status.error is not None:
            message = str(status.error.get("message", "preview error"))
            if message != self.status_message:
                self._set_error(message)
                traceback_text = str(status.error.get("traceback", ""))
                matches = re.findall(r'behavior\.py", line (\d+)', traceback_text)
                if matches:
                    self.code_editor.set_diagnostics(
                        (BehaviorDiagnostic(int(matches[-1]), 0, message),)
                    )

    def _draft_for_design_preview(self) -> EntityProjectDefinition | None:
        try:
            return self._definition_from_forms()
        except Exception:
            return self.current.definition if self.current is not None else None

    def _draw_design(self, surface: pygame.Surface) -> None:
        workspace = self._workspace_rect()
        guide = self.small_font.render(
            "1. Design   2. Edit Code   3. Open Preview   4. Save",
            True,
            (142, 158, 174),
        )
        surface.blit(guide, (workspace.x + 18, workspace.y + 16))
        preview_rect = pygame.Rect(workspace.right - 245, workspace.bottom - 220, 220, 190)
        pygame.draw.rect(surface, (23, 28, 35), preview_rect, border_radius=8)
        pygame.draw.rect(surface, (73, 86, 100), preview_rect, width=1, border_radius=8)
        label = self.small_font.render("Appearance preview", True, (178, 190, 201))
        surface.blit(label, (preview_rect.x + 10, preview_rect.y + 8))
        definition = self._draft_for_design_preview()
        if definition is not None and self.current is not None:
            try:
                appearance = definition.appearance
                scaled_width = appearance.size[0] * appearance.scale[0]
                scaled_height = appearance.size[1] * appearance.scale[1]
                fit_zoom = min(
                    (preview_rect.width - 36) / max(1.0, scaled_width),
                    (preview_rect.height - 58) / max(1.0, scaled_height),
                )
                self.appearance_renderer.draw_at(
                    surface,
                    definition,
                    self.current.directory,
                    preview_rect.center,
                    zoom=max(0.1, min(10.0, fit_zoom)),
                )
            except Exception as exc:
                error = self.small_font.render(str(exc), True, (239, 104, 104))
                surface.blit(error, (preview_rect.x + 10, preview_rect.centery))

    def _draw_behaviors(self, surface: pygame.Surface) -> None:
        workspace = self._workspace_rect()
        guide = self.small_font.render(
            "Add components, arrange their execution order, then configure the selected attachment.",
            True,
            (142, 158, 174),
        )
        surface.blit(guide, (workspace.x + 18, workspace.y + 16))
        try:
            assert self.current is not None
            tags = tuple(
                tag.strip()
                for tag in self.tags_entry.get_text().split(",")
                if tag.strip()
            )
            draft = replace(
                self.current.definition,
                properties=tuple(self.properties),
                tags=tags,
                behaviors=tuple(self.attachments),
            )
            validation = self.behavior_registry.validate_entity(draft)
            stack_message = (
                "Stack valid. " + " ".join(validation.warnings)
                if validation.warnings
                else "Stack valid — Apply runs it in the isolated preview."
            )
            stack_color = (143, 192, 162) if not validation.warnings else (231, 180, 92)
        except Exception as exc:
            stack_message = str(exc)
            stack_color = (239, 104, 104)
        if len(stack_message) > 115:
            stack_message = stack_message[:112] + "..."
        surface.blit(
            self.small_font.render(stack_message, True, stack_color),
            (workspace.x + 18, workspace.bottom - 132),
        )
        selected = next(
            (
                item
                for item in self.attachments
                if item.attachment_id == self.selected_attachment
            ),
            None,
        )
        behavior_id = selected.behavior_id if selected is not None else self.selected_behavior_project
        if behavior_id is None:
            return
        project = self.behavior_registry.catalog.get(behavior_id)
        if project is None:
            return
        definition = project.definition
        lines = [
            f"{definition.name}  ·  {definition.category}",
            definition.description or "No description.",
        ]
        if definition.required_properties:
            lines.append(
                "Requires properties: "
                + ", ".join(item.name for item in definition.required_properties)
            )
        if definition.writes:
            lines.append("Writes: " + ", ".join(definition.writes))
        x = workspace.x + 18
        y = workspace.bottom - 104
        max_chars = max(36, (workspace.width - 36) // 9)
        for line in lines:
            words = line.split()
            current = ""
            wrapped: list[str] = []
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and len(candidate) > max_chars:
                    wrapped.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                wrapped.append(current)
            for item in wrapped[:2]:
                surface.blit(self.small_font.render(item, True, (174, 187, 199)), (x, y))
                y += 20

    def _draw_empty_state(self, surface: pygame.Surface) -> None:
        workspace = self._workspace_rect()
        heading = self.heading_font.render("Create your first entity", True, (241, 244, 248))
        explanation = self.font.render(
            "An entity project stores appearance, properties, and Python behavior.",
            True,
            (170, 182, 194),
        )
        steps = (
            "1. Choose a permanent entity ID and a display name.",
            "2. Design a shape or PNG and add state properties.",
            "3. Edit lifecycle code, then open Preview to run it.",
            "4. Save it under content/entities/ when it is ready.",
        )
        surface.blit(heading, heading.get_rect(center=(workspace.centerx, workspace.centery - 100)))
        surface.blit(
            explanation,
            explanation.get_rect(center=(workspace.centerx, workspace.centery - 58)),
        )
        for index, line in enumerate(steps):
            rendered = self.small_font.render(line, True, (143, 158, 173))
            surface.blit(
                rendered,
                rendered.get_rect(center=(workspace.centerx, workspace.centery - 18 + index * 25)),
            )

    def _draw_preview(self, surface: pygame.Surface) -> None:
        rect = self._preview_rect()
        pygame.draw.rect(surface, (15, 18, 22), rect)
        if (
            self.preview_terrain_renderer is None
            or self.preview_camera is None
            or self.preview_definition is None
            or self.current is None
        ):
            message = self.heading_font.render("Press Apply or Run to start preview", True, (182, 193, 204))
            surface.blit(message, message.get_rect(center=rect.center))
            return
        view = surface.subsurface(rect)
        self.preview_terrain_renderer.draw(view, self.preview_camera)
        snapshot = self.preview.status.snapshot
        if snapshot is not None:
            for entity in snapshot.get("entities", []):
                self.appearance_renderer.draw_snapshot(
                    view,
                    self.preview_definition,
                    self.current.directory,
                    self.preview_camera,
                    entity,
                )
            hud = self.small_font.render(
                f"Tick {snapshot.get('tick', 0)}   {len(snapshot.get('entities', []))} entities   "
                f"{snapshot.get('speed', 1):g}x   {snapshot.get('update_ms', 0):.2f} ms",
                True,
                (244, 246, 248),
            )
            panel = pygame.Surface((hud.get_width() + 16, hud.get_height() + 10), pygame.SRCALPHA)
            panel.fill((7, 9, 12, 190))
            panel.blit(hud, (8, 5))
            view.blit(panel, (8, 8))
        pygame.draw.rect(surface, (91, 105, 119), rect, width=1)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((17, 21, 27))
        pygame.draw.rect(surface, (22, 27, 34), (0, 52, 260, self.surface_size[1] - 52))
        workspace = self._workspace_rect()
        pygame.draw.rect(surface, (25, 30, 38), workspace, border_radius=8)
        title = "Entity Studio"
        if self.current is not None:
            title += f" — {self.current.definition.name}{' *' if self.dirty else ''}"
        surface.blit(self.heading_font.render(title, True, (241, 244, 248)), (610, 15))
        if self.current is None:
            self._draw_empty_state(surface)
        elif self.active_tab == "design":
            self._draw_design(surface)
        elif self.active_tab == "behaviors":
            self._draw_behaviors(surface)
        elif self.active_tab == "code":
            self.code_editor.draw(surface)
        else:
            self._draw_preview(surface)
        status_color = (239, 104, 104) if self.status_is_error else (142, 202, 165)
        status = self.small_font.render(self.status_message, True, status_color)
        surface.blit(status, (270, self.surface_size[1] - 30))
        if self.catalog.errors:
            warning = self.small_font.render(
                f"{len(self.catalog.errors)} invalid entity project(s)", True, (231, 180, 92)
            )
            surface.blit(warning, (12, self.surface_size[1] - 27))
        self.ui.draw_ui(surface)

    def resize(self, surface_size: tuple[int, int]) -> None:
        # pygame_gui does not re-anchor every custom editor element reliably;
        # rebuild while retaining the current draft text and project state.
        code = self.code_editor.text
        dirty = self.dirty
        try:
            self._commit_behavior_parameters()
        except Exception:
            pass
        self.surface_size = surface_size
        self.ui.set_window_resolution(surface_size)
        self.code_editor.resize(self._code_rect())
        self.code_editor.set_text(code, clear_history=False)
        self.library_list.set_dimensions((240, max(120, surface_size[1] - 152)))
        workspace = self._workspace_rect()
        self.empty_new_button.set_relative_position(
            (workspace.centerx - 105, workspace.centery + 80)
        )
        self._build_preview_widgets()
        self._build_behavior_widgets()
        self._sync_project_ui()
        self.dirty = dirty
        if self.preview_camera is not None:
            rect = self._preview_rect()
            self.preview_camera.resize(rect.width, rect.height)

    def close(self) -> None:
        pygame.key.stop_text_input()
        self.preview.stop()
        self.ui.clear_and_reset()


__all__ = ["EntityEditorAction", "EntityEditorScreen"]
