from __future__ import annotations

from types import ModuleType, SimpleNamespace

import sim_sandbox.game.worlds.discovery as discovery
from sim_sandbox.game.world_definition import WorldDefinition


def _definition(world_id: str, order: int = 0) -> WorldDefinition:
    return WorldDefinition(
        id=world_id,
        name=world_id.title(),
        description="Test world",
        menu_order=order,
        default_seed=1,
        default_population=0,
        factory=lambda options: None,  # Discovery validates metadata, not execution.
    )


def test_discovery_reports_import_and_invalid_definition_errors(monkeypatch) -> None:
    root = ModuleType("fake_worlds")
    root.__path__ = []  # type: ignore[attr-defined]
    modules = {
        "fake_worlds.valid.definition": SimpleNamespace(WORLD_DEFINITION=_definition("valid", 2)),
        "fake_worlds.first.definition": SimpleNamespace(WORLD_DEFINITION=_definition("first", 1)),
        "fake_worlds.wrong.definition": SimpleNamespace(WORLD_DEFINITION=_definition("not_wrong")),
    }
    children = [
        SimpleNamespace(name="wrong", ispkg=True),
        SimpleNamespace(name="broken", ispkg=True),
        SimpleNamespace(name="valid", ispkg=True),
        SimpleNamespace(name="first", ispkg=True),
        SimpleNamespace(name="ignored.py", ispkg=False),
    ]

    def fake_import(name: str):
        if name == "fake_worlds":
            return root
        if name == "fake_worlds.broken.definition":
            raise RuntimeError("boom")
        return modules[name]

    monkeypatch.setattr(discovery.importlib, "import_module", fake_import)
    monkeypatch.setattr(discovery, "_package_children", lambda package: children)

    catalog = discovery.discover_worlds("fake_worlds")

    assert [item.id for item in catalog.definitions] == ["first", "valid"]
    assert [error.package for error in catalog.errors] == ["broken", "wrong"]
    assert "RuntimeError: boom" in catalog.errors[0].message
    assert "must match folder" in catalog.errors[1].message


def test_discovery_reports_duplicates_without_hiding_first(monkeypatch) -> None:
    root = ModuleType("duplicate_worlds")
    root.__path__ = []  # type: ignore[attr-defined]
    module = SimpleNamespace(WORLD_DEFINITION=_definition("same"))
    monkeypatch.setattr(
        discovery.importlib,
        "import_module",
        lambda name: root if name == "duplicate_worlds" else module,
    )
    monkeypatch.setattr(
        discovery,
        "_package_children",
        lambda package: [
            SimpleNamespace(name="same", ispkg=True),
            SimpleNamespace(name="same", ispkg=True),
        ],
    )

    catalog = discovery.discover_worlds("duplicate_worlds")

    assert [item.id for item in catalog.definitions] == ["same"]
    assert len(catalog.errors) == 1
    assert "duplicate world ID" in catalog.errors[0].message


def test_discovery_can_return_no_valid_worlds(monkeypatch) -> None:
    root = ModuleType("empty_worlds")
    root.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setattr(discovery.importlib, "import_module", lambda name: root)
    monkeypatch.setattr(discovery, "_package_children", lambda package: [])

    catalog = discovery.discover_worlds("empty_worlds")

    assert catalog.definitions == ()
    assert catalog.errors == ()
