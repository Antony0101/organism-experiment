"""Built-in component metadata and value behavior."""

from __future__ import annotations

import numpy as np
import pytest

import simworld
from simworld.components import Appearance, Parent, Position
from simworld.registry import COMPONENTS


pytestmark = pytest.mark.usefixtures("clean_components")


def test_core_components_are_registered_with_editor_metadata():
    assert COMPONENTS.get("Position").cls is Position
    assert COMPONENTS.get("Appearance").cls is Appearance
    assert COMPONENTS.get("Parent").cls is Parent

    appearance_fields = {field.name: field for field in COMPONENTS.get("Appearance").fields}
    assert appearance_fields["color"].default == (255, 255, 255)
    assert appearance_fields["color"].meta["widget"] == "color"
    assert appearance_fields["size"].default == 1
    assert appearance_fields["size"].min == 1

    parent = COMPONENTS.get("Parent").fields[0]
    assert parent.name == "entity" and parent.default == 0
    assert parent.meta["widget"] == "entity"


def test_position_keeps_supplied_numeric_types_without_coercion():
    integer_position = Position(1, 2)
    numpy_position = Position(np.float64(3.5), np.int64(4))

    assert (integer_position.x, integer_position.y) == (1, 2)
    assert type(integer_position.x) is int and type(integer_position.y) is int
    assert isinstance(numpy_position.x, np.float64)
    assert isinstance(numpy_position.y, np.int64)


def test_only_position_and_appearance_are_package_root_component_exports():
    assert simworld.Position is Position
    assert simworld.Appearance is Appearance
    assert "Position" in simworld.__all__ and "Appearance" in simworld.__all__
    assert "Parent" not in simworld.__all__
