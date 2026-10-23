"""Top-level Pygame application and screen state machine."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from enum import Enum, auto
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from ..game.world_definition import MAX_ENTITY_COUNT, MAX_SEED, WorldLaunchOptions
from ..game.worlds.discovery import WorldCatalog, discover_worlds
from ..game.behavior_projects.registry import BehaviorProjectRegistry
from ..game.entity_projects.registry import EntityProjectRegistry
from ..game.quick_sandbox import (
    TERRAIN_PRESETS,
    QuickSandboxOptions,
    SandboxPopulation,
    create_quick_sandbox,
)
from .screens.behavior_editor import BehaviorEditorScreen
from .screens.gameplay import GameplayScreen
from .screens.entity_editor import EntityEditorScreen
from .screens.pause_menu import PauseMenuScreen
from .screens.project_hub import ProjectHubScreen
from .screens.quick_sandbox import QuickSandboxScreen
from .screens.world_selection import WorldSelectionScreen
from .user_state import UserState


class AppMode(Enum):
    PROJECT_HUB = auto()
    WORLD_SELECTION = auto()
    QUICK_SANDBOX = auto()
    GAMEPLAY = auto()
    PAUSE_MENU = auto()
    ENTITY_EDITOR = auto()
    BEHAVIOR_EDITOR = auto()


class SimulationApp:
    """Coordinate screen transitions and the active world session's lifetime.

    With no launch arguments this opens world selection. Supplying ``seed`` or
    ``entity_count`` directly retains the original Python API by launching
    ``wandering_plains``; the CLI explicitly requests menu prefill instead.
    """

    def __init__(
        self,
        seed: int | None = None,
        entity_count: int | None = None,
        window_size: tuple[int, int] = (1280, 720),
        *,
        world_id: str | None = None,
        start_in_menu: bool | None = None,
        open_editor: bool = False,
        open_behavior_editor: bool = False,
        initial_behavior_id: str | None = None,
        start_in_hub: bool = False,
        quick_sandbox_options: QuickSandboxOptions | None = None,
        catalog: WorldCatalog | None = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("2D Simulation Sandbox")
        self.surface = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        self.frame_clock = pygame.time.Clock()
        self.catalog = discover_worlds() if catalog is None else catalog
        self.gameplay: GameplayScreen | None = None
        self.hub_screen: ProjectHubScreen | None = None
        self.selection_screen: WorldSelectionScreen | None = None
        self.quick_sandbox_screen: QuickSandboxScreen | None = None
        self.pause_menu: PauseMenuScreen | None = None
        self.editor_screen: EntityEditorScreen | None = None
        self.behavior_editor_screen: BehaviorEditorScreen | None = None
        self.user_state = UserState()
        self.menu_seed_override = seed
        self.menu_entity_count_override = entity_count
        self.active_world_id: str | None = None
        self.launch_options: WorldLaunchOptions | None = None
        self.quick_sandbox_options: QuickSandboxOptions | None = None
        self.mode = AppMode.WORLD_SELECTION
        self.running = False
        self._paused_before_menu = False

        if start_in_menu is None:
            start_in_menu = world_id is None and seed is None and entity_count is None
        if quick_sandbox_options is not None:
            self._start_quick_sandbox(quick_sandbox_options)
        elif open_behavior_editor:
            self._show_behavior_editor(initial_behavior_id)
        elif open_editor:
            self._show_entity_editor()
        elif start_in_hub:
            self._show_project_hub()
        elif start_in_menu:
            self._show_world_selection(seed, entity_count)
        else:
            definition = self.catalog.require(world_id or "wandering_plains")
            options = WorldLaunchOptions(
                definition.default_seed if seed is None else seed,
                definition.default_entity_count if entity_count is None else entity_count,
            )
            self._start_world(definition.id, options)

    def _close_non_gameplay_screens(self) -> None:
        if self.editor_screen is not None:
            if self.editor_screen.current is not None:
                self.user_state.add_recent(
                    "entity", self.editor_screen.current.definition.id
                )
            self.editor_screen.close()
            self.editor_screen = None
        if self.behavior_editor_screen is not None:
            if self.behavior_editor_screen.current is not None:
                self.user_state.add_recent(
                    "behavior", self.behavior_editor_screen.current.definition.id
                )
            self.behavior_editor_screen.close()
            self.behavior_editor_screen = None
        self.hub_screen = None
        self.selection_screen = None
        self.quick_sandbox_screen = None
        self.pause_menu = None

    def _show_project_hub(self) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        self._close_non_gameplay_screens()
        recent = self.user_state.get("recent_projects", [])
        self.hub_screen = ProjectHubScreen(recent if isinstance(recent, list) else [])
        self.active_world_id = None
        self.launch_options = None
        self.quick_sandbox_options = None
        self.mode = AppMode.PROJECT_HUB

    def _show_world_selection(
        self,
        seed_override: int | None = None,
        entity_count_override: int | None = None,
    ) -> None:
        if seed_override is None:
            seed_override = self.menu_seed_override
        if entity_count_override is None:
            entity_count_override = self.menu_entity_count_override
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        self._close_non_gameplay_screens()
        self.active_world_id = None
        self.launch_options = None
        self.pause_menu = None
        self.selection_screen = WorldSelectionScreen(
            self.catalog.definitions,
            self.catalog.errors,
            seed_override,
            entity_count_override,
        )
        self.mode = AppMode.WORLD_SELECTION

    def _show_entity_editor(self) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        self._close_non_gameplay_screens()
        self.active_world_id = None
        self.launch_options = None
        self.editor_screen = EntityEditorScreen(self.surface.get_size())
        self.mode = AppMode.ENTITY_EDITOR

    def _show_behavior_editor(self, behavior_id: str | None = None) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        self._close_non_gameplay_screens()
        self.active_world_id = None
        self.launch_options = None
        self.behavior_editor_screen = BehaviorEditorScreen(
            self.surface.get_size(), initial_behavior_id=behavior_id
        )
        if behavior_id:
            self.user_state.add_recent("behavior", behavior_id)
        self.mode = AppMode.BEHAVIOR_EDITOR

    def _show_quick_sandbox(self, initial_entity_id: str | None = None, terrain: str = "standard") -> None:
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        self._close_non_gameplay_screens()
        self.active_world_id = None
        self.launch_options = None
        preferred = self.user_state.get("sandbox_terrain", terrain)
        selected_terrain = preferred if preferred in TERRAIN_PRESETS else terrain
        self.quick_sandbox_screen = QuickSandboxScreen(
            initial_entity_id=initial_entity_id, initial_terrain=selected_terrain
        )
        self.mode = AppMode.QUICK_SANDBOX

    def _start_world(self, world_id: str, options: WorldLaunchOptions) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
        self._close_non_gameplay_screens()
        definition = self.catalog.require(world_id)
        session = definition.create(options)
        self.gameplay = GameplayScreen(session, self.surface.get_size())
        self.selection_screen = None
        self.pause_menu = None
        self.active_world_id = definition.id
        self.launch_options = options
        self.quick_sandbox_options = None
        self.user_state.add_recent("world", definition.id)
        self.mode = AppMode.GAMEPLAY

    def _start_quick_sandbox(self, options: QuickSandboxOptions) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
        self._close_non_gameplay_screens()
        session = create_quick_sandbox(options)
        self.gameplay = GameplayScreen(session, self.surface.get_size())
        self.active_world_id = "quick_sandbox"
        self.launch_options = None
        self.quick_sandbox_options = options
        self.user_state.set("sandbox_terrain", options.terrain)
        for row in options.populations:
            self.user_state.add_recent("entity", row.entity_id)
        self.mode = AppMode.GAMEPLAY

    def _restart_world(self, options: WorldLaunchOptions | None = None) -> None:
        if self.quick_sandbox_options is not None:
            self._start_quick_sandbox(self.quick_sandbox_options)
            return
        if self.active_world_id is None or self.launch_options is None:
            raise RuntimeError("there is no active world to restart")
        self._start_world(self.active_world_id, options or self.launch_options)

    def _open_pause_menu(self) -> None:
        if self.gameplay is None:
            return
        self._paused_before_menu = self.gameplay.simulation_clock.paused
        if not self._paused_before_menu:
            self.gameplay.simulation_clock.toggle_pause()
        self.pause_menu = PauseMenuScreen()
        self.mode = AppMode.PAUSE_MENU

    def _resume_gameplay(self) -> None:
        if self.gameplay is None:
            return
        if not self._paused_before_menu and self.gameplay.simulation_clock.paused:
            self.gameplay.simulation_clock.toggle_pause()
        self.pause_menu = None
        self.mode = AppMode.GAMEPLAY

    def _apply_pause_action(self, action: str) -> None:
        if action == "resume":
            self._resume_gameplay()
        elif action == "restart":
            self._restart_world()
        elif action == "main_hub":
            self._show_project_hub()
        elif action == "world_selection":  # Compatibility for older integrations.
            self._show_world_selection()
        elif action == "quit":
            self.running = False

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if self.mode is AppMode.ENTITY_EDITOR and self.editor_screen is not None:
                    action = self.editor_screen.request_exit("quit")
                    if action is not None:
                        self.running = False
                elif self.mode is AppMode.BEHAVIOR_EDITOR and self.behavior_editor_screen is not None:
                    action = self.behavior_editor_screen.request_exit("quit")
                    if action is not None:
                        self.running = False
                else:
                    self.running = False
                continue
            if event.type == pygame.VIDEORESIZE:
                self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                if self.gameplay is not None:
                    self.gameplay.resize(*event.size)
                if self.editor_screen is not None:
                    self.editor_screen.resize(event.size)
                if self.behavior_editor_screen is not None:
                    self.behavior_editor_screen.resize(event.size)
                continue

            if self.mode is AppMode.PROJECT_HUB and self.hub_screen is not None:
                action = self.hub_screen.handle_event(event, self.surface.get_size())
                if action is not None:
                    if action.kind == "quit":
                        self.running = False
                    elif action.kind == "worlds":
                        self._show_world_selection()
                    elif action.kind == "sandbox":
                        self._show_quick_sandbox()
                    elif action.kind == "entity_editor":
                        self._show_entity_editor()
                    elif action.kind == "behavior_editor":
                        self._show_behavior_editor()
            elif self.mode is AppMode.WORLD_SELECTION and self.selection_screen is not None:
                action = self.selection_screen.handle_event(event, self.surface.get_size())
                if action is not None:
                    if action.kind in ("quit", "back"):
                        self._show_project_hub()
                    elif action.kind == "editor":
                        self._show_entity_editor()
                    elif (
                        action.kind == "start"
                        and action.world_id is not None
                        and action.options is not None
                    ):
                        self._start_world(action.world_id, action.options)
            elif self.mode is AppMode.QUICK_SANDBOX and self.quick_sandbox_screen is not None:
                action = self.quick_sandbox_screen.handle_event(event, self.surface.get_size())
                if action is not None:
                    if action.kind == "back":
                        self._show_project_hub()
                    elif action.kind == "start" and action.options is not None:
                        self._start_quick_sandbox(action.options)
            elif self.mode is AppMode.GAMEPLAY and self.gameplay is not None:
                if (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_ESCAPE
                    and self.gameplay.runtime_error is None
                ):
                    self._open_pause_menu()
                    continue
                action = self.gameplay.handle_event(event, self.surface.get_size())
                if action is not None:
                    if action.kind == "restart":
                        self._restart_world()
                    elif action.kind == "main_hub":
                        self._show_project_hub()
                    elif action.kind == "new_seed" and self.launch_options is not None:
                        self._restart_world(
                            WorldLaunchOptions(
                                (self.launch_options.seed + 1) & 0xFFFFFFFF,
                                self.launch_options.entity_count,
                            )
                        )
            elif self.mode is AppMode.PAUSE_MENU and self.pause_menu is not None:
                action = self.pause_menu.handle_event(event, self.surface.get_size())
                if action is not None:
                    self._apply_pause_action(action)
            elif self.mode is AppMode.ENTITY_EDITOR and self.editor_screen is not None:
                action = self.editor_screen.handle_event(event)
                if action is not None:
                    if action.kind == "back":
                        self._show_project_hub()
                    elif action.kind == "quit":
                        self.running = False
                    elif action.kind == "behavior_editor":
                        self._show_behavior_editor(action.value)
            elif self.mode is AppMode.BEHAVIOR_EDITOR and self.behavior_editor_screen is not None:
                action = self.behavior_editor_screen.handle_event(event)
                if action is not None:
                    if action.kind == "back":
                        self._show_project_hub()
                    elif action.kind == "quit":
                        self.running = False

    def _draw_frame(self, real_dt: float) -> None:
        mouse_position = pygame.mouse.get_pos()
        if self.mode is AppMode.PROJECT_HUB and self.hub_screen is not None:
            self.hub_screen.draw(self.surface, mouse_position)
        elif self.mode is AppMode.WORLD_SELECTION and self.selection_screen is not None:
            self.selection_screen.draw(self.surface, mouse_position)
        elif self.mode is AppMode.QUICK_SANDBOX and self.quick_sandbox_screen is not None:
            self.quick_sandbox_screen.draw(self.surface, mouse_position)
        elif self.mode is AppMode.ENTITY_EDITOR and self.editor_screen is not None:
            self.editor_screen.update(real_dt)
            self.editor_screen.draw(self.surface)
        elif self.mode is AppMode.BEHAVIOR_EDITOR and self.behavior_editor_screen is not None:
            self.behavior_editor_screen.update(real_dt)
            self.behavior_editor_screen.draw(self.surface)
        elif self.gameplay is not None:
            if self.mode is AppMode.GAMEPLAY:
                selected = self.gameplay.update(real_dt)
            else:
                selected = self.gameplay.follow_selected_entity(0.0)
            self.gameplay.draw(
                self.surface,
                self.frame_clock.get_fps(),
                mouse_position,
                selected,
            )
            if self.mode is AppMode.PAUSE_MENU and self.pause_menu is not None:
                self.pause_menu.draw(self.surface, mouse_position)
        pygame.display.flip()

    def shutdown(self) -> None:
        if self.gameplay is not None:
            self.gameplay.close()
            self.gameplay = None
        if self.editor_screen is not None:
            self.editor_screen.close()
            self.editor_screen = None
        if self.behavior_editor_screen is not None:
            self.behavior_editor_screen.close()
            self.behavior_editor_screen = None
        pygame.quit()

    def run(self, max_frames: int | None = None) -> None:
        self.running = True
        frames = 0
        quit_requested = False
        try:
            while self.running and (max_frames is None or frames < max_frames):
                real_dt = self.frame_clock.tick(120) / 1000.0
                self._handle_events()
                self._draw_frame(real_dt)
                frames += 1
            quit_requested = not self.running
        finally:
            self.running = False
            if quit_requested or max_frames is None:
                self.shutdown()

    # Compatibility helpers for code written against the original single-screen app.
    def _require_gameplay(self) -> GameplayScreen:
        if self.gameplay is None:
            raise RuntimeError("no world is currently running")
        return self.gameplay

    @property
    def world(self):
        return self._require_gameplay().world

    @property
    def camera(self):
        return self._require_gameplay().camera

    @property
    def renderer(self):
        return self._require_gameplay().renderer

    @property
    def simulation_clock(self):
        return self._require_gameplay().simulation_clock

    @property
    def selected_entity_id(self) -> int | None:
        return self._require_gameplay().selected_entity_id

    @selected_entity_id.setter
    def selected_entity_id(self, value: int | None) -> None:
        self._require_gameplay().selected_entity_id = value

    @property
    def follow_selected(self) -> bool:
        return self._require_gameplay().follow_selected

    @follow_selected.setter
    def follow_selected(self, value: bool) -> None:
        self._require_gameplay().follow_selected = value

    @property
    def _held_camera_action(self) -> str | None:
        return self._require_gameplay().held_camera_action

    def _select_at_cursor(self, screen_position: tuple[int, int]) -> bool:
        return self._require_gameplay().select_at_cursor(screen_position)

    def _follow_selected_entity(self, real_dt: float):
        return self._require_gameplay().follow_selected_entity(real_dt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic 2D simulation sandbox"
    )
    parser.add_argument("--world", help="world ID to launch without the selection menu")
    parser.add_argument("--seed", type=int, help="world seed override")
    parser.add_argument("--entities", type=int, help="starting population override")
    parser.add_argument(
        "--editor", action="store_true", help="open the entity creation studio"
    )
    parser.add_argument(
        "--entity-editor", action="store_true", help="open the entity creation studio"
    )
    parser.add_argument(
        "--behavior-editor", action="store_true", help="open the behavior component studio"
    )
    parser.add_argument(
        "--sandbox", metavar="ENTITY_ID", help="launch a quick sandbox with this entity project"
    )
    parser.add_argument(
        "--terrain", choices=sorted(TERRAIN_PRESETS), default="standard",
        help="terrain size for --sandbox"
    )
    parser.add_argument(
        "--list-worlds", action="store_true", help="list discovered worlds and exit"
    )
    parser.add_argument("--list-entities", action="store_true", help="list entity projects and exit")
    parser.add_argument("--list-behaviors", action="store_true", help="list behavior components and exit")
    return parser


def _validate_cli_range(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.seed is not None and not 0 <= args.seed <= MAX_SEED:
        parser.error(f"--seed must be between 0 and {MAX_SEED}")
    if args.entities is not None and not 0 <= args.entities <= MAX_ENTITY_COUNT:
        parser.error(f"--entities must be between 0 and {MAX_ENTITY_COUNT}")


def _print_worlds(catalog: WorldCatalog) -> None:
    for definition in catalog.definitions:
        print(
            f"{definition.id}: {definition.name} "
            f"(seed={definition.default_seed}, entities={definition.default_entity_count})"
        )
    for error in catalog.errors:
        print(f"warning: {error.package}: {error.message}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_cli_range(parser, args)
    catalog = discover_worlds()
    if args.list_worlds:
        _print_worlds(catalog)
        return
    if args.list_entities:
        entity_catalog = EntityProjectRegistry(Path("content/entities")).catalog
        for project in entity_catalog.projects:
            print(f"{project.definition.id}: {project.definition.name}")
        for error in entity_catalog.errors:
            print(f"warning: {error.project}: {error.message}")
        return
    if args.list_behaviors:
        behavior_catalog = BehaviorProjectRegistry(Path("content/behaviors")).catalog
        for project in behavior_catalog.projects:
            marker = " [built-in]" if project.builtin else ""
            print(f"{project.definition.id}: {project.definition.name} ({project.definition.category}){marker}")
        for error in behavior_catalog.errors:
            print(f"warning: {error.project}: {error.message}")
        return
    entity_editor = args.editor or args.entity_editor
    direct_modes = sum(bool(value) for value in (args.world, entity_editor, args.behavior_editor, args.sandbox))
    if direct_modes > 1:
        parser.error("choose only one of --world, --entity-editor, --behavior-editor, or --sandbox")
    if not catalog.definitions and not (entity_editor or args.behavior_editor or args.sandbox):
        parser.error("no valid worlds were discovered")
    if args.world is not None and catalog.get(args.world) is None:
        available = ", ".join(item.id for item in catalog.definitions)
        parser.error(f"unknown world {args.world!r}; choose from: {available}")
    sandbox_options = None
    if args.sandbox:
        entities = EntityProjectRegistry(Path("content/entities"))
        if entities.catalog.get(args.sandbox) is None:
            available = ", ".join(project.definition.id for project in entities.catalog.projects) or "none"
            parser.error(f"unknown entity project {args.sandbox!r}; choose from: {available}")
        sandbox_options = QuickSandboxOptions(
            args.terrain,
            1 if args.seed is None else args.seed,
            (SandboxPopulation(args.sandbox, 1 if args.entities is None else args.entities),)
            if (args.entities is None or args.entities > 0)
            else (),
        )
    SimulationApp(
        seed=args.seed,
        entity_count=args.entities,
        world_id=args.world,
        start_in_menu=False,
        start_in_hub=not any((args.world, entity_editor, args.behavior_editor, args.sandbox)),
        open_editor=entity_editor,
        open_behavior_editor=args.behavior_editor,
        quick_sandbox_options=sandbox_options,
        catalog=catalog,
    ).run()


__all__ = ["AppMode", "SimulationApp", "build_parser", "main"]
