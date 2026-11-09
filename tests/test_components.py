"""Data component registration and reflection contracts."""

from __future__ import annotations

from contextlib import contextmanager
import dataclasses as dc

import pytest

import simworld
from simworld.errors import (
    DuplicateNameError,
    NotAComponentError,
    SerializationError,
    UnknownComponentError,
)
from simworld.registry import (
    COMPONENTS,
    ComponentInfo,
    FieldInfo,
    component,
    component_from_dict,
    component_name,
    component_to_dict,
    prop,
)
from tests.conftest import clean_components as component_cleanup


pytestmark = pytest.mark.usefixtures("clean_components")


def test_component_subclass_includes_new_fields_and_factories():
    @component
    class BaseStats:
        health: int = 10

    @component
    class MovingStats(BaseStats):
        speed: float = prop(2.0, min=0)
        history: list = prop(default_factory=list)

    first = MovingStats(health=8, speed=3.0)
    second = MovingStats()
    first.history.append(1)
    assert second.history == []
    assert [field.name for field in COMPONENTS.get("MovingStats").fields] == [
        "health", "speed", "history",
    ]
    assert COMPONENTS.get("MovingStats").fields[1].min == 0
    assert component_to_dict(first) == {"health": 8, "speed": 3.0, "history": [1]}
    assert component_from_dict("MovingStats", component_to_dict(first)) == first
    assert [field.name for field in COMPONENTS.get("BaseStats").fields] == ["health"]


@pytest.mark.parametrize("value", ["Position", simworld.Position])
def test_component_serialization_rejects_names_and_classes(value):
    with pytest.raises(NotAComponentError, match="component instance"):
        component_to_dict(value)


def test_component_builds_slotted_data_and_field_metadata():
    @component(category="testing")
    class Step010Stats:
        """Editable statistics."""

        speed: float = prop(
            1.25, min=0, max=20, tooltip="Movement speed", widget="slider", step=0.25
        )
        policy: object = prop(None, serialize=False, init=False)

    value = Step010Stats()
    assert dc.is_dataclass(Step010Stats)
    assert not hasattr(value, "__dict__")
    with pytest.raises(AttributeError):
        value.unlisted = 1
    assert value.speed == 1.25 and value.policy is None
    assert Step010Stats.__component_name__ == "Step010Stats"
    info = COMPONENTS.get("Step010Stats")
    assert isinstance(info, ComponentInfo) and info.cls is Step010Stats
    assert info.name == "Step010Stats" and info.category == "testing"
    assert info.doc == "Editable statistics."
    assert [field.name for field in info.fields] == ["speed", "policy"]
    speed, policy = info.fields
    assert isinstance(speed, FieldInfo)
    assert (speed.type, speed.default, speed.min, speed.max) == ("float", 1.25, 0, 20)
    assert speed.tooltip == "Movement speed" and speed.serialize is True
    assert speed.meta["widget"] == "slider" and speed.meta["step"] == 0.25
    assert policy.serialize is False
    assert dc.fields(Step010Stats)[1].init is False
    with pytest.raises(TypeError):
        Step010Stats(policy=object())
    value.policy = object()  # Runtime data still occupies a declared slot.


def test_factory_defaults_are_independent_from_instances_and_metadata():
    @component()
    class Step010Bag:
        values: list[int] = prop(default_factory=list)

    first, second = Step010Bag(), Step010Bag()
    default = COMPONENTS.get("Step010Bag").fields[0].default
    first.values.append(7)
    assert first.values == [7] and second.values == [] and default == []
    assert first.values is not second.values and second.values is not default
    field = dc.fields(Step010Bag)[0]
    assert field.default is dc.MISSING and field.default_factory is list


def test_plain_defaults_and_required_fields_keep_dataclass_semantics():
    @component
    class Step010Required:
        count: int
        enabled: bool = True

    with pytest.raises(TypeError):
        Step010Required()
    assert Step010Required(3).enabled is True
    required, plain = COMPONENTS.get("Step010Required").fields
    assert required.default is None
    assert (plain.type, plain.default, plain.min, plain.max) == ("bool", True, None, None)
    assert plain.tooltip == "" and plain.serialize is True


def test_existing_dataclass_is_not_rebuilt():
    @dc.dataclass(frozen=True)
    class Step010Existing:
        value: int = 3

    registered = component(Step010Existing)
    assert registered is Step010Existing
    assert COMPONENTS.get("Step010Existing").cls is Step010Existing
    with pytest.raises(dc.FrozenInstanceError):
        registered().value = 4


def test_custom_component_name_and_default_category():
    @component(name="Step010Alias")
    class LocalComponent:
        count: int = 2

    assert LocalComponent.__component_name__ == "Step010Alias"
    assert "LocalComponent" not in COMPONENTS
    info = COMPONENTS.get("Step010Alias")
    assert info.cls is LocalComponent and info.category == "general"


@pytest.mark.parametrize("different_identity", ["__module__", "__qualname__"])
def test_duplicate_name_from_another_class_is_rejected(different_identity):
    @component
    class Step010Collision:
        value: int = 1

    original = COMPONENTS.get("Step010Collision")
    other = type("Step010Collision", (), {
        "__module__": Step010Collision.__module__,
        "__qualname__": Step010Collision.__qualname__,
        "__annotations__": {"value": int},
        "value": 2,
    })
    setattr(other, different_identity, "different_identity")
    with pytest.raises(DuplicateNameError) as caught:
        component(other)
    assert "Pass @component(name=" in str(caught.value)
    assert COMPONENTS.get("Step010Collision") is original
    assert component(name="Step010Other")(other).__component_name__ == "Step010Other"


def test_same_logical_class_can_reload_and_same_class_can_reregister():
    def define(default):
        @component
        class Step010Reload:
            value: int = default
        return Step010Reload

    first = define(1)
    old = first()
    second = define(2)
    assert first is not second and old.value == 1 and second().value == 2
    assert COMPONENTS.get("Step010Reload").cls is second
    assert COMPONENTS.get("Step010Reload").fields[0].default == 2
    assert component(second) is second


@pytest.mark.parametrize("fails", [False, True])
def test_cleanup_restores_reloaded_metadata_and_removes_new_types(fails):
    def define(default):
        @component
        class Step010Cleanup:
            value: int = default
        return Step010Cleanup

    original = define(1)
    before = dict(COMPONENTS.items())

    def change():
        with contextmanager(component_cleanup.__wrapped__)():
            define(2)

            @component
            class Step010Temporary:
                value: int = 0

            if fails:
                raise RuntimeError("component cleanup probe")

    if fails:
        with pytest.raises(RuntimeError, match="component cleanup probe"):
            change()
    else:
        change()
    assert dict(COMPONENTS.items()) == before
    assert COMPONENTS.get("Step010Cleanup").cls is original


def test_metadata_containers_have_independent_defaults():
    first, second = FieldInfo("first", "int"), FieldInfo("second", "int")
    first.meta["widget"] = "int"
    assert second.meta == {}
    one = ComponentInfo("One", type("One", (), {}))
    two = ComponentInfo("Two", type("Two", (), {}))
    one.fields.append(first)
    assert two.fields == []


def test_prop_rejects_conflicting_default_and_factory():
    with pytest.raises(ValueError):
        prop([], default_factory=list)


def test_component_api_is_exported_from_package_root():
    assert simworld.component is component and simworld.prop is prop
    assert simworld.COMPONENTS is COMPONENTS
    assert {"component", "prop", "COMPONENTS"} <= set(simworld.__all__)


def test_component_name_resolves_registered_names_classes_and_instances():
    @component
    class Step011Named:
        value: int = 1

    assert component_name("Step011Named") == "Step011Named"
    assert component_name(Step011Named) == "Step011Named"
    assert component_name(Step011Named()) == "Step011Named"
    with pytest.raises(UnknownComponentError):
        component_name("Step011Missing")
    with pytest.raises(NotAComponentError):
        component_name(object())
    with pytest.raises(NotAComponentError):
        component_name(type("Unregistered", (), {}))


def test_component_to_dict_converts_json_values_and_omits_excluded_fields():
    import numpy as np

    @component
    class Step011Serializable:
        point: tuple[int, int] = (3, 4)
        scalar: float = 0.0
        values: list = prop(default_factory=list)
        mapping: dict = prop(default_factory=dict)
        transient: object = prop(None, serialize=False)

    value = Step011Serializable(
        point=(8, 9), scalar=np.float64(2.5), values=[np.int64(3), (4, 5)],
        mapping={"answer": np.int32(42)}, transient=object(),
    )
    assert component_to_dict(value) == {
        "point": [8, 9], "scalar": 2.5, "values": [3, [4, 5]],
        "mapping": {"answer": 42},
    }


def test_component_to_dict_calls_serialization_guard_and_rejects_unsupported_values():
    @component
    class Step011Guarded:
        value: object = None

        def _check_serializable(self):
            raise SerializationError("guard rejected component")

    with pytest.raises(SerializationError, match="guard rejected"):
        component_to_dict(Step011Guarded())

    @component
    class Step011Unsupported:
        value: object

    with pytest.raises(SerializationError, match="Unsupported"):
        component_to_dict(Step011Unsupported(object()))


def test_component_from_dict_restores_defaults_and_tuple_fields():
    @component
    class Step011Restorable:
        point: tuple[int, int] = (1, 2)
        count: int = 7
        tags: list = prop(default_factory=list)

    value = component_from_dict("Step011Restorable", {"point": [5, 6], "tags": ["a"]})
    assert value == Step011Restorable(point=(5, 6), tags=["a"])
    assert isinstance(value.point, tuple)
    assert component_from_dict("Step011Restorable").count == 7


def test_component_from_dict_reports_unknown_fields_and_constructor_type_errors():
    @component
    class Step011Strict:
        value: int

    with pytest.raises(SerializationError, match="Unknown.*extra"):
        component_from_dict("Step011Strict", {"value": 1, "extra": 2})
    with pytest.raises(SerializationError, match="Step011Strict"):
        component_from_dict("Step011Strict", {"unexpected": 1})

    @component
    class Step011Typed:
        value: int

        def __init__(self, value):
            if not isinstance(value, int):
                raise TypeError("value must be an integer")
            self.value = value

    with pytest.raises(SerializationError, match="value must be an integer"):
        component_from_dict("Step011Typed", {"value": "wrong"})


def test_serialization_helpers_are_public_from_registry_module():
    assert callable(component_name) and callable(component_to_dict)
    assert callable(component_from_dict)
