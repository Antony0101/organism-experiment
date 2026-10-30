"""Core data components shared by the simulation engine and editor."""

from .registry import component, prop


@component(category="core")
class Position:
    """An entity's location in the flat 2D world."""

    x: float = 0.0
    y: float = 0.0


@component(category="core")
class Appearance:
    """An entity's display color and marker size."""

    color: tuple = prop((255, 255, 255), tooltip="Display color.", widget="color")
    size: int = prop(1, min=1, tooltip="Display size.")


@component(category="core")
class Parent:
    """Optional parent entity id; zero means that there is no parent."""

    entity: int = prop(0, tooltip="Parent entity; zero means none.", widget="entity")


__all__ = ["Position", "Appearance", "Parent"]
