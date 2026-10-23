from __future__ import annotations

import time
from pathlib import Path

from sim_sandbox.game.behavior_projects import (
    BehaviorAttachment,
    BehaviorDefinition,
    BehaviorFieldDefinition,
)
from sim_sandbox.game.entity_projects.model import EntityProjectDefinition
from sim_sandbox.game.entity_projects.registry import EntityProjectStore
from sim_sandbox.presentation.editor.preview import PreviewController


def _wait_for(controller: PreviewController, predicate, timeout: float = 6.0):
    deadline = time.monotonic() + timeout
    status = controller.poll()
    while time.monotonic() < deadline:
        status = controller.poll()
        if predicate(status):
            return status
        time.sleep(0.02)
    raise AssertionError(f"preview condition was not reached: {status}")


def test_preview_applies_steps_pauses_and_stops(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    project = store.create_default("preview_dot", "Preview Dot")
    behavior = "def update(entity, world, dt):\n    entity.x += 10 * dt\n"
    controller = PreviewController(timeout_seconds=4.0)
    try:
        controller.apply(project.definition, behavior, project.directory)
        status = _wait_for(
            controller,
            lambda item: item.loaded
            and item.snapshot is not None
            and item.snapshot.get("tick", 0) >= 2,
        )
        assert status.snapshot is not None
        tick = int(status.snapshot["tick"])
        controller.pause(True)
        _wait_for(
            controller,
            lambda item: item.snapshot is not None and item.snapshot.get("paused") is True,
        )
        controller.step()
        stepped = _wait_for(
            controller,
            lambda item: item.snapshot is not None and int(item.snapshot["tick"]) > tick,
        )
        assert len(stepped.snapshot["entities"]) == 1  # type: ignore[index]
    finally:
        controller.stop()
    assert controller.process is None


def test_preview_reports_runtime_errors(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    project = store.create_default("broken_dot", "Broken Dot")
    behavior = "def update(entity, world, dt):\n    raise RuntimeError('preview boom')\n"
    controller = PreviewController(timeout_seconds=4.0)
    try:
        controller.apply(project.definition, behavior, project.directory)
        status = _wait_for(controller, lambda item: item.error is not None)
        assert status.error is not None
        assert status.error["error_type"] == "RuntimeError"
        assert "preview boom" in str(status.error["message"])
        assert "behavior.py" in str(status.error["traceback"])
    finally:
        controller.stop()


def test_preview_terminates_an_infinite_update(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "entities")
    project = store.create_default("looping_dot", "Looping Dot")
    behavior = "def update(entity, world, dt):\n    while True:\n        pass\n"
    controller = PreviewController(timeout_seconds=0.5)
    try:
        controller.apply(project.definition, behavior, project.directory)
        status = _wait_for(controller, lambda item: item.timed_out, timeout=5.0)
        assert status.error is not None
        assert status.error["error_type"] == "PreviewTimeout"
    finally:
        controller.stop()


def test_preview_accepts_unsaved_behavior_drafts_and_tagged_fixtures(tmp_path: Path) -> None:
    store = EntityProjectStore(tmp_path / "content" / "entities")
    project = store.create_default("behavior_host", "Behavior Host")
    behavior = BehaviorDefinition(
        "draft_counter",
        "Draft Counter",
        state=(BehaviorFieldDefinition("ticks", "int", 0, True),),
    )
    host = EntityProjectDefinition(
        id=project.definition.id,
        name=project.definition.name,
        behaviors=(BehaviorAttachment("counter", behavior.id),),
    )
    source = 'def update(behavior, entity, world, dt):\n    behavior.state["ticks"] += 1\n'
    controller = PreviewController(timeout_seconds=4.0)
    try:
        controller.apply(
            host,
            project.behavior_source,
            project.directory,
            behavior_drafts=(
                {
                    "manifest": behavior.to_json(),
                    "source": source,
                    "directory": str(tmp_path / "content" / "behaviors" / behavior.id),
                },
            ),
            fixtures=({"project_id": "", "tags": ("food",), "count": 2},),
        )
        status = _wait_for(
            controller,
            lambda item: item.loaded
            and item.snapshot is not None
            and item.snapshot.get("tick", 0) >= 2,
        )
        assert status.snapshot is not None
        entities = status.snapshot["entities"]
        assert len(entities) == 3
        host_snapshot = next(item for item in entities if item["project_id"] == "behavior_host")
        assert host_snapshot["behaviors"][0]["state"]["ticks"] >= 1
        fixture_tags = [item["tags"] for item in entities if item["project_id"].startswith("preview_fixture_")]
        assert fixture_tags == [["food"], ["food"]]
    finally:
        controller.stop()
