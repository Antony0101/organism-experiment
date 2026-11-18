"""Headless RGB composition and compact ASCII views of a simulation world."""

from math import floor, isfinite
from operator import index

import numpy as np


__all__ = ["render_rgb", "render_ascii"]


def _entity_cells(world):
    """Yield visible entity cells in Position-store insertion order."""
    for entity, position in world._stores.get("Position", {}).items():
        x, y = floor(position.x), floor(position.y)
        if 0 <= x < world.width and 0 <= y < world.height:
            yield entity, x, y


def render_rgb(world, *, fields=None, scale=1, entities=True, entity_color=None, field_alpha=0.6) -> np.ndarray:
    """Compose terrain, selected colored fields and one-cell entity markers."""
    scale = index(scale)
    if scale < 1:
        raise ValueError("Render scale must be a positive integer.")
    field_alpha = float(field_alpha)
    if not isfinite(field_alpha) or not 0 <= field_alpha <= 1:
        raise ValueError("field_alpha must be finite and in [0, 1].")

    rgb = np.full((world.height, world.width, 3), 40.0)
    terrain_layer = world.terrains.layer
    if terrain_layer is not None:
        lut = np.full((max(world.terrains.by_id, default=0) + 1, 3), 40.0)
        for terrain_id, terrain in world.terrains.by_id.items():
            lut[terrain_id] = terrain.color
        ids = terrain_layer.data
        valid = (ids >= 0) & (ids < len(lut))
        rgb[valid] = lut[ids[valid]]

    if fields is None:
        layers = list(world.layers.values())
    else:
        names = (fields,) if isinstance(fields, str) else fields
        layers = [world.layers[name] for name in names]
    for layer in layers:
        if layer.kind != "field" or layer.color is None:
            continue
        if layer.shape:
            raise ValueError(f"Field {layer.name!r} must be scalar to render.")
        if layer.data.size == 0:
            continue
        denominator = layer.max or layer.data.max()
        if denominator == 0:
            continue
        alpha = (np.clip(layer.data / denominator, 0, 1) * field_alpha)[..., None]
        rgb = rgb * (1 - alpha) + np.asarray(layer.color) * alpha

    if entities:
        appearances = world._stores.get("Appearance", {})
        for entity, x, y in _entity_cells(world):
            appearance = appearances.get(entity)
            if entity_color is not None:
                color = entity_color(world, entity)
            elif appearance is not None:
                color = appearance.color
            else:
                color = (255, 255, 255)
            rgb[y, x] = color
    pixels = np.clip(rgb, 0, 255).astype(np.uint8)
    if scale != 1:
        pixels = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
    return pixels


def render_ascii(world, max_width=100, entities=True) -> str:
    """Return terrain symbols with entity markers, downsampling square cells."""
    max_width = index(max_width)
    if max_width < 1:
        raise ValueError("max_width must be a positive integer.")
    if world.width == 0 or world.height == 0:
        return ""
    chars = np.full((world.height, world.width), ".", dtype="U1")
    terrain_layer = world.terrains.layer
    if terrain_layer is not None:
        lut = np.full(max(world.terrains.by_id, default=0) + 1, "?", dtype="U1")
        for terrain_id, terrain in world.terrains.by_id.items():
            lut[terrain_id] = str(terrain.props.get("char") or terrain.name[:1] or "?")[0]
        ids = terrain_layer.data
        chars[:] = "?"
        valid = (ids >= 0) & (ids < len(lut))
        chars[valid] = lut[ids[valid]]
    stride = max(1, (world.width + max_width - 1) // max_width)
    chars = chars[::stride, ::stride].copy()
    if entities:
        for _, x, y in _entity_cells(world):
            chars[y // stride, x // stride] = "o"
    return "\n".join("".join(row) for row in chars)
