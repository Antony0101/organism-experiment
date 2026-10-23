"""Lifecycle behavior for this editable entity."""


def init(entity, world):
    """Called once when the entity becomes active."""
    pass


def update(entity, world, dt):
    """Called on each fixed simulation tick."""
    entity.x += entity.state["speed"] * dt
    pass


def delete(entity, world):
    """Called once before removal or world shutdown."""
    pass
