"""Verify registry isolation before the engine registry is implemented."""

from contextlib import contextmanager
import sys
from types import ModuleType, SimpleNamespace

import pytest

from tests.conftest import clean_components


@pytest.mark.parametrize("fails", [False, True])
def test_clean_components_restores_registry(monkeypatch, fails):
    original = {"Kept": object(), "Replaced": object(), "Removed": object()}
    entries = original.copy()
    registry = SimpleNamespace(
        items=entries.items,
        names=lambda: list(entries),
        unregister=entries.pop,
        register=lambda name, item, *, replace=False: entries.__setitem__(name, item),
    )
    module = ModuleType("simworld.registry")
    module.COMPONENTS = registry
    monkeypatch.setitem(sys.modules, "simworld.registry", module)

    def edit_registry():
        with contextmanager(clean_components.__wrapped__)():
            entries["Added"] = object()
            entries["Replaced"] = object()
            del entries["Removed"]
            if fails:
                raise RuntimeError("test body failed")

    if fails:
        with pytest.raises(RuntimeError, match="test body failed"):
            edit_registry()
    else:
        edit_registry()

    assert entries == original


def test_clean_components_does_not_hide_dependency_errors(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "simworld.registry":
            raise ModuleNotFoundError("missing registry dependency", name="missing_dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    with pytest.raises(ModuleNotFoundError, match="missing registry dependency"):
        next(clean_components.__wrapped__())
