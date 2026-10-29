"""Name registration contracts and shared component-registry isolation."""

from contextlib import contextmanager

import pytest

from simworld.errors import DuplicateNameError, UnknownComponentError, UnknownNameError
from simworld.registry import COMPONENTS, Registry
from tests.conftest import clean_components as component_cleanup


def test_registration_returns_item_and_preserves_insertion_order():
    registry = Registry[object]("example")
    first, second = object(), object()
    assert registry.register("zeta", first) is first
    assert registry.register("alpha", second) is second
    assert registry.get("zeta") is first
    assert registry.names() == ["zeta", "alpha"]
    assert list(registry) == ["zeta", "alpha"]
    assert list(registry.items()) == [("zeta", first), ("alpha", second)]
    assert len(registry) == 2
    assert "alpha" in registry and "missing" not in registry


def test_duplicate_failure_leaves_the_original_registration_intact():
    registry = Registry("example")
    original = object()
    registry.register("kept", original)
    with pytest.raises(DuplicateNameError) as caught:
        registry.register("kept", object())
    assert "kept" in str(caught.value) and "example" in str(caught.value)
    assert registry.get("kept") is original
    assert registry.names() == ["kept"]
    with pytest.raises(DuplicateNameError):
        registry.register("kept", original)


def test_explicit_replacement_preserves_name_order():
    registry = Registry("example")
    registry.register("first", object())
    registry.register("second", object())
    replacement = object()
    assert registry.register("first", replacement, replace=True) is replacement
    assert registry.get("first") is replacement
    assert registry.names() == ["first", "second"]


def test_unregister_is_optional_and_reregister_appends():
    registry = Registry("example")
    first = registry.register("first", object())
    registry.register("second", object())
    assert registry.unregister("first") is first
    assert registry.unregister("first") is None
    assert "first" not in registry and len(registry) == 1
    registry.register("first", first)
    assert registry.names() == ["second", "first"]


def test_names_are_a_snapshot_and_items_are_a_live_view():
    registry = Registry("example")
    names, items = registry.names(), registry.items()
    registry.register("new", 1)
    assert names == []
    names.append("outside")
    assert registry.names() == ["new"]
    assert list(items) == [("new", 1)]


@pytest.mark.parametrize("value", [None, False, 0])
def test_false_values_are_not_missing(value):
    registry = Registry("example")
    registry.register("present", value)
    assert registry.get("present") is value
    assert "present" in registry


@pytest.mark.parametrize("error", [UnknownNameError, UnknownComponentError])
def test_unknown_lookup_uses_the_configured_error(error):
    registry = Registry("component", error)
    registry.register("Position", object())
    registry.register("Appearance", object())
    with pytest.raises(error) as caught:
        registry.get("Positon")
    message = str(caught.value)
    assert "Positon" in message and "Position" in message
    assert "Appearance" in message and "did you mean" in message.lower()
    assert registry.names() == ["Position", "Appearance"]


def test_registry_instances_do_not_share_entries():
    first, second = Registry("example"), Registry("example")
    first.register("local", object())
    assert len(second) == 0
    with pytest.raises(UnknownNameError):
        second.get("local")


@pytest.mark.parametrize("fails", [False, True])
def test_real_component_registry_is_restored(clean_components, fails):
    COMPONENTS.register("Step009Kept", object())
    COMPONENTS.register("Step009Removed", object())
    before = dict(COMPONENTS.items())

    def mutate():
        with contextmanager(component_cleanup.__wrapped__)():
            COMPONENTS.register("Step009Added", object())
            COMPONENTS.register("Step009Kept", object(), replace=True)
            COMPONENTS.unregister("Step009Removed")
            if fails:
                raise RuntimeError("registry cleanup probe")

    if fails:
        with pytest.raises(RuntimeError, match="registry cleanup probe"):
            mutate()
    else:
        mutate()
    assert dict(COMPONENTS.items()) == before
