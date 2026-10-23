"""Packaged, read-only behavior presets used by the studios and runtime."""

from __future__ import annotations

from ..project_types import PropertyDefinition
from .model import BehaviorDefinition, BehaviorFieldDefinition


def field(
    name: str,
    kind: str,
    default: object,
    *,
    inspector: bool = False,
    editor: str = "value",
    choices: tuple[str, ...] = (),
) -> BehaviorFieldDefinition:
    return BehaviorFieldDefinition(name, kind, default, inspector, editor, choices)


def required(
    name: str, kind: str, default: object, inspector: bool = True
) -> PropertyDefinition:
    return PropertyDefinition(name, kind, default, inspector)


def definition(
    behavior_id: str,
    name: str,
    description: str,
    category: str,
    *,
    parameters: tuple[BehaviorFieldDefinition, ...] = (),
    state: tuple[BehaviorFieldDefinition, ...] = (),
    required_properties: tuple[PropertyDefinition, ...] = (),
    writes: tuple[str, ...] = (),
    allow_multiple: bool = False,
    exclusive_group: str | None = None,
) -> BehaviorDefinition:
    return BehaviorDefinition(
        id=behavior_id,
        name=name,
        description=description,
        category=category,
        parameters=parameters,
        state=state,
        required_properties=required_properties,
        writes=writes,
        allow_multiple=allow_multiple,
        exclusive_group=exclusive_group,
    )


BUILTIN_BEHAVIORS: tuple[tuple[BehaviorDefinition, str], ...] = (
    (
        definition(
            "constant_velocity",
            "Constant Velocity",
            "Move by a fixed world-space velocity.",
            "movement",
            parameters=(
                field("velocity", "vec2", (30.0, 0.0)),
                field("respect_passability", "bool", True),
            ),
            writes=("position",),
        ),
        """def update(behavior, entity, world, dt):
    vx, vy = behavior.config["velocity"]
    nx = entity.x + vx * dt
    ny = entity.y + vy * dt
    if not behavior.config["respect_passability"] or world.terrain.is_passable(nx, ny):
        entity.x, entity.y = nx, ny
""",
    ),
    (
        definition(
            "wander",
            "Wander",
            "Move in deterministic, changing random directions.",
            "movement",
            parameters=(
                field("speed", "float", 40.0),
                field("change_interval", "float", 1.5),
                field("turn_jitter", "float", 1.5),
            ),
            state=(
                field("angle", "float", 0.0),
                field("timer", "float", 0.0),
            ),
            writes=("position",),
        ),
        """import math

def init(behavior, entity, world):
    behavior.state["angle"] = world.rng.random() * math.tau
    behavior.state["timer"] = world.rng.random() * max(0.01, behavior.config["change_interval"])

def update(behavior, entity, world, dt):
    behavior.state["timer"] -= dt
    if behavior.state["timer"] <= 0.0:
        behavior.state["timer"] = max(0.01, behavior.config["change_interval"])
        behavior.state["angle"] += world.rng.uniform(-behavior.config["turn_jitter"], behavior.config["turn_jitter"])
    angle = behavior.state["angle"]
    speed = max(0.0, behavior.config["speed"])
    nx = entity.x + math.cos(angle) * speed * dt
    ny = entity.y + math.sin(angle) * speed * dt
    if world.terrain.is_passable(nx, ny):
        entity.x, entity.y = nx, ny
    else:
        behavior.state["angle"] += math.pi
""",
    ),
    (
        definition(
            "seek_nearest",
            "Seek Nearest",
            "Move toward the nearest entity matching a tag and optional project.",
            "movement",
            parameters=(
                field("target_tag", "str", "target", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("range", "float", 200.0),
                field("speed", "float", 50.0),
                field("arrival_radius", "float", 5.0),
            ),
            writes=("position",),
        ),
        """import math

def update(behavior, entity, world, dt):
    tag = behavior.config["target_tag"]
    target = world.nearest_entity(entity.x, entity.y, max(0.0, behavior.config["range"]), required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id)
    if target is None:
        return
    dx, dy = target.x - entity.x, target.y - entity.y
    distance = math.hypot(dx, dy)
    if distance <= max(0.0, behavior.config["arrival_radius"]) or distance == 0.0:
        return
    step = min(distance, max(0.0, behavior.config["speed"]) * dt)
    nx, ny = entity.x + dx / distance * step, entity.y + dy / distance * step
    if world.terrain.is_passable(nx, ny):
        entity.x, entity.y = nx, ny
""",
    ),
    (
        definition(
            "flee_nearest",
            "Flee Nearest",
            "Move away from the nearest matching threat.",
            "movement",
            parameters=(
                field("target_tag", "str", "threat", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("range", "float", 160.0),
                field("speed", "float", 60.0),
            ),
            writes=("position",),
        ),
        """import math

def update(behavior, entity, world, dt):
    tag = behavior.config["target_tag"]
    target = world.nearest_entity(entity.x, entity.y, max(0.0, behavior.config["range"]), required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id)
    if target is None:
        return
    dx, dy = entity.x - target.x, entity.y - target.y
    distance = math.hypot(dx, dy)
    if distance == 0.0:
        angle = world.rng.random() * math.tau
        dx, dy, distance = math.cos(angle), math.sin(angle), 1.0
    step = max(0.0, behavior.config["speed"]) * dt
    nx, ny = entity.x + dx / distance * step, entity.y + dy / distance * step
    if world.terrain.is_passable(nx, ny):
        entity.x, entity.y = nx, ny
""",
    ),
    (
        definition(
            "orbit_nearest",
            "Orbit Nearest",
            "Orbit around the nearest matching entity.",
            "movement",
            parameters=(
                field("target_tag", "str", "target", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("range", "float", 250.0),
                field("orbit_radius", "float", 40.0),
                field("angular_speed", "float", 1.0),
            ),
            writes=("position",),
        ),
        """import math

def update(behavior, entity, world, dt):
    tag = behavior.config["target_tag"]
    target = world.nearest_entity(entity.x, entity.y, max(0.0, behavior.config["range"]), required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id)
    if target is None:
        return
    angle = math.atan2(entity.y - target.y, entity.x - target.x) + behavior.config["angular_speed"] * dt
    radius = max(1.0, behavior.config["orbit_radius"])
    nx, ny = target.x + math.cos(angle) * radius, target.y + math.sin(angle) * radius
    if world.terrain.is_passable(nx, ny):
        entity.x, entity.y = nx, ny
""",
    ),
    (
        definition(
            "keep_in_bounds",
            "Keep In Bounds",
            "Clamp the entity inside the bounded terrain.",
            "terrain",
            parameters=(field("margin", "float", 0.0),),
            writes=("position",),
        ),
        """def update(behavior, entity, world, dt):
    margin = max(entity.radius, behavior.config["margin"])
    entity.x = min(max(margin, entity.x), max(margin, world.terrain.pixel_width - margin))
    entity.y = min(max(margin, entity.y), max(margin, world.terrain.pixel_height - margin))
""",
    ),
    (
        definition(
            "avoid_blocked_terrain",
            "Avoid Blocked Terrain",
            "Undo movement that enters water, rock, or world exterior.",
            "terrain",
            writes=("position",),
        ),
        """def update(behavior, entity, world, dt):
    if not world.terrain.is_passable(entity.x, entity.y):
        entity.x, entity.y = entity.previous_x, entity.previous_y
""",
    ),
    (
        definition(
            "terrain_speed_modifier",
            "Terrain Speed Modifier",
            "Scale this tick's movement using the terrain movement cost.",
            "terrain",
            writes=("position",),
        ),
        """import math

def update(behavior, entity, world, dt):
    cost = world.terrain.movement_cost_at(entity.x, entity.y)
    if not math.isfinite(cost):
        entity.x, entity.y = entity.previous_x, entity.previous_y
        return
    entity.x = entity.previous_x + (entity.x - entity.previous_x) / max(1.0, cost)
    entity.y = entity.previous_y + (entity.y - entity.previous_y) / max(1.0, cost)
""",
    ),
    (
        definition(
            "maximum_lifetime",
            "Maximum Lifetime",
            "Remove the entity after a fixed duration.",
            "lifecycle",
            parameters=(field("seconds", "float", 10.0),),
            state=(field("age", "float", 0.0, inspector=True),),
            writes=("lifecycle",),
        ),
        """def update(behavior, entity, world, dt):
    behavior.state["age"] += dt
    if behavior.state["age"] >= max(0.0, behavior.config["seconds"]):
        world.remove(entity.entity_id)
""",
    ),
    (
        definition(
            "age_counter",
            "Age Counter",
            "Increment a shared age property in seconds.",
            "state",
            required_properties=(required("age", "float", 0.0),),
            writes=("state:age",),
        ),
        """def update(behavior, entity, world, dt):
    entity.state["age"] += dt
""",
    ),
    (
        definition(
            "health",
            "Health",
            "Clamp health and remove the entity when it reaches zero.",
            "state",
            parameters=(field("delete_at_zero", "bool", True),),
            required_properties=(
                required("health", "float", 100.0),
                required("max_health", "float", 100.0),
            ),
            writes=("state:health", "lifecycle"),
        ),
        """def update(behavior, entity, world, dt):
    entity.state["max_health"] = max(0.0, entity.state["max_health"])
    entity.state["health"] = min(entity.state["max_health"], entity.state["health"])
    if behavior.config["delete_at_zero"] and entity.state["health"] <= 0.0:
        world.remove(entity.entity_id)
""",
    ),
    (
        definition(
            "energy_metabolism",
            "Energy Metabolism",
            "Drain energy continuously and optionally remove exhausted entities.",
            "state",
            parameters=(
                field("drain_per_second", "float", 1.0),
                field("delete_at_zero", "bool", False),
            ),
            required_properties=(
                required("energy", "float", 100.0),
                required("max_energy", "float", 100.0),
            ),
            writes=("state:energy", "lifecycle"),
        ),
        """def update(behavior, entity, world, dt):
    entity.state["max_energy"] = max(0.0, entity.state["max_energy"])
    entity.state["energy"] = min(entity.state["max_energy"], entity.state["energy"] - max(0.0, behavior.config["drain_per_second"]) * dt)
    if behavior.config["delete_at_zero"] and entity.state["energy"] <= 0.0:
        world.remove(entity.entity_id)
""",
    ),
    (
        definition(
            "hunger",
            "Hunger",
            "Increase hunger and damage health above a threshold.",
            "state",
            parameters=(
                field("increase_per_second", "float", 1.0),
                field("damage_threshold", "float", 80.0),
                field("damage_per_second", "float", 2.0),
            ),
            required_properties=(
                required("hunger", "float", 0.0),
                required("max_hunger", "float", 100.0),
                required("health", "float", 100.0),
            ),
            writes=("state:hunger", "state:health"),
        ),
        """def update(behavior, entity, world, dt):
    entity.state["hunger"] = min(entity.state["max_hunger"], entity.state["hunger"] + max(0.0, behavior.config["increase_per_second"]) * dt)
    if entity.state["hunger"] >= behavior.config["damage_threshold"]:
        entity.state["health"] -= max(0.0, behavior.config["damage_per_second"]) * dt
""",
    ),
    (
        definition(
            "regeneration",
            "Regeneration",
            "Increase a selected numeric entity property up to a maximum.",
            "state",
            parameters=(
                field("property", "str", "health", editor="property"),
                field("per_second", "float", 1.0),
                field("maximum", "float", 100.0),
            ),
            writes=("state",),
            allow_multiple=True,
        ),
        """def update(behavior, entity, world, dt):
    name = behavior.config["property"]
    if name not in entity.state or not isinstance(entity.state[name], (int, float)) or isinstance(entity.state[name], bool):
        raise ValueError(f"regeneration property {name!r} is missing or non-numeric")
    entity.state[name] = min(behavior.config["maximum"], entity.state[name] + max(0.0, behavior.config["per_second"]) * dt)
""",
    ),
    (
        definition(
            "growth_over_time",
            "Growth Over Time",
            "Interpolate visual scale and collision radius over time.",
            "state",
            parameters=(
                field("duration", "float", 10.0),
                field("start_scale", "float", 0.5),
                field("end_scale", "float", 1.5),
                field("start_radius", "float", 3.0),
                field("end_radius", "float", 8.0),
            ),
            state=(field("elapsed", "float", 0.0, inspector=True),),
            writes=("visual", "radius"),
        ),
        """def update(behavior, entity, world, dt):
    behavior.state["elapsed"] += dt
    duration = max(0.0001, behavior.config["duration"])
    amount = min(1.0, max(0.0, behavior.state["elapsed"] / duration))
    scale = behavior.config["start_scale"] + (behavior.config["end_scale"] - behavior.config["start_scale"]) * amount
    entity.visual.scale_x = entity.visual.scale_y = max(0.001, scale)
    entity.radius = max(0.0, behavior.config["start_radius"] + (behavior.config["end_radius"] - behavior.config["start_radius"]) * amount)
""",
    ),
    (
        definition(
            "nearest_tag_sensor",
            "Nearest Tag Sensor",
            "Store the nearest matching entity ID and distance in shared properties.",
            "interaction",
            parameters=(
                field("target_tag", "str", "target", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("range", "float", 200.0),
            ),
            required_properties=(
                required("target_id", "int", 0),
                required("target_distance", "float", -1.0),
            ),
            writes=("state:target_id", "state:target_distance"),
        ),
        """import math

def update(behavior, entity, world, dt):
    tag = behavior.config["target_tag"]
    target = world.nearest_entity(entity.x, entity.y, max(0.0, behavior.config["range"]), required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id)
    if target is None:
        entity.state["target_id"] = 0
        entity.state["target_distance"] = -1.0
    else:
        entity.state["target_id"] = target.entity_id
        entity.state["target_distance"] = math.hypot(target.x - entity.x, target.y - entity.y)
""",
    ),
    (
        definition(
            "contact_damage",
            "Contact Damage",
            "Damage nearby matching entities that expose a health property.",
            "interaction",
            parameters=(
                field("target_tag", "str", "organism", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("damage_per_second", "float", 10.0),
                field("extra_range", "float", 0.0),
            ),
            writes=("other:state:health",),
        ),
        """def update(behavior, entity, world, dt):
    tag = behavior.config["target_tag"]
    radius = entity.radius + max(0.0, behavior.config["extra_range"])
    for target in world.query_radius(entity.x, entity.y, radius, required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id):
        if hasattr(target, "state") and "health" in target.state:
            target.state["health"] -= max(0.0, behavior.config["damage_per_second"]) * dt
""",
    ),
    (
        definition(
            "eat_nearby",
            "Eat Nearby",
            "Consume the nearest matching food and gain energy.",
            "interaction",
            parameters=(
                field("target_tag", "str", "food", editor="tag"),
                field("target_project", "str", "", editor="project"),
                field("range", "float", 12.0),
                field("nutrition", "float", 20.0),
                field("cooldown", "float", 0.5),
                field("consume_target", "bool", True),
            ),
            state=(field("cooldown", "float", 0.0),),
            required_properties=(
                required("energy", "float", 50.0),
                required("max_energy", "float", 100.0),
            ),
            writes=("state:energy", "other:lifecycle"),
        ),
        """def update(behavior, entity, world, dt):
    behavior.state["cooldown"] = max(0.0, behavior.state["cooldown"] - dt)
    if behavior.state["cooldown"] > 0.0:
        return
    tag = behavior.config["target_tag"]
    target = world.nearest_entity(entity.x, entity.y, max(0.0, behavior.config["range"]), required_tags=(() if not tag else (tag,)), project_id=(behavior.config["target_project"] or None), exclude_id=entity.entity_id)
    if target is None:
        return
    entity.state["energy"] = min(entity.state["max_energy"], entity.state["energy"] + max(0.0, behavior.config["nutrition"]))
    behavior.state["cooldown"] = max(0.0, behavior.config["cooldown"])
    if behavior.config["consume_target"]:
        world.remove(target.entity_id)
""",
    ),
    (
        definition(
            "reproduce",
            "Reproduce",
            "Spend energy to spawn an offspring after a cooldown.",
            "interaction",
            parameters=(
                field("offspring_project", "str", "", editor="project"),
                field("energy_threshold", "float", 80.0),
                field("energy_cost", "float", 40.0),
                field("cooldown", "float", 8.0),
                field("spawn_distance", "float", 16.0),
            ),
            state=(field("cooldown", "float", 0.0, inspector=True),),
            required_properties=(
                required("energy", "float", 100.0),
                required("max_energy", "float", 100.0),
            ),
            writes=("state:energy", "spawn"),
        ),
        """import math

def update(behavior, entity, world, dt):
    behavior.state["cooldown"] = max(0.0, behavior.state["cooldown"] - dt)
    if behavior.state["cooldown"] > 0.0 or entity.state["energy"] < behavior.config["energy_threshold"]:
        return
    angle = world.rng.random() * math.tau
    distance = max(entity.radius * 2.0, behavior.config["spawn_distance"])
    x, y = entity.x + math.cos(angle) * distance, entity.y + math.sin(angle) * distance
    if not world.terrain.is_passable(x, y):
        return
    project = behavior.config["offspring_project"] or entity.project_id
    try:
        world.spawn_project(project, x, y)
    except RuntimeError as exc:
        if "population limit" in str(exc):
            return
        raise
    entity.state["energy"] -= max(0.0, behavior.config["energy_cost"])
    behavior.state["cooldown"] = max(0.0, behavior.config["cooldown"])
""",
    ),
    (
        definition(
            "periodic_spawner",
            "Periodic Spawner",
            "Periodically spawn configured entity projects nearby.",
            "interaction",
            parameters=(
                field("project", "str", "", editor="project"),
                field("interval", "float", 5.0),
                field("count", "int", 1),
                field("radius", "float", 20.0),
            ),
            state=(field("timer", "float", 0.0, inspector=True),),
            writes=("spawn",),
            allow_multiple=True,
        ),
        """import math

def update(behavior, entity, world, dt):
    behavior.state["timer"] -= dt
    if behavior.state["timer"] > 0.0:
        return
    behavior.state["timer"] = max(0.01, behavior.config["interval"])
    project = behavior.config["project"] or entity.project_id
    for _ in range(max(0, behavior.config["count"])):
        angle = world.rng.random() * math.tau
        distance = world.rng.random() * max(0.0, behavior.config["radius"])
        x, y = entity.x + math.cos(angle) * distance, entity.y + math.sin(angle) * distance
        if not world.terrain.is_passable(x, y):
            continue
        try:
            world.spawn_project(project, x, y)
        except RuntimeError as exc:
            if "population limit" in str(exc):
                break
            raise
""",
    ),
    (
        definition(
            "spin",
            "Spin",
            "Rotate the entity continuously.",
            "visual",
            parameters=(field("degrees_per_second", "float", 90.0),),
            writes=("visual",),
        ),
        """def update(behavior, entity, world, dt):
    entity.visual.rotation_degrees = (entity.visual.rotation_degrees + behavior.config["degrees_per_second"] * dt) % 360.0
""",
    ),
    (
        definition(
            "pulse_scale",
            "Pulse Scale",
            "Animate visual scale with a sine wave.",
            "visual",
            parameters=(
                field("base_scale", "float", 1.0),
                field("amplitude", "float", 0.2),
                field("cycles_per_second", "float", 1.0),
            ),
            state=(field("phase", "float", 0.0),),
            writes=("visual",),
        ),
        """import math

def update(behavior, entity, world, dt):
    behavior.state["phase"] += math.tau * behavior.config["cycles_per_second"] * dt
    scale = behavior.config["base_scale"] + math.sin(behavior.state["phase"]) * behavior.config["amplitude"]
    entity.visual.scale_x = entity.visual.scale_y = max(0.001, scale)
""",
    ),
    (
        definition(
            "face_velocity",
            "Face Velocity",
            "Rotate the appearance to face this tick's movement direction.",
            "visual",
            parameters=(field("angle_offset", "float", 0.0),),
            writes=("visual",),
        ),
        """import math

def update(behavior, entity, world, dt):
    dx, dy = entity.x - entity.previous_x, entity.y - entity.previous_y
    if dx != 0.0 or dy != 0.0:
        entity.visual.rotation_degrees = math.degrees(math.atan2(dy, dx)) + behavior.config["angle_offset"]
""",
    ),
    (
        definition(
            "property_color_map",
            "Property Color Map",
            "Blend between two colors using a numeric entity property.",
            "visual",
            parameters=(
                field("property", "str", "energy", editor="property"),
                field("minimum", "float", 0.0),
                field("maximum", "float", 100.0),
                field("low_color", "color", (220, 50, 50, 255)),
                field("high_color", "color", (50, 220, 90, 255)),
            ),
            writes=("visual",),
            allow_multiple=True,
        ),
        """def update(behavior, entity, world, dt):
    name = behavior.config["property"]
    if name not in entity.state or not isinstance(entity.state[name], (int, float)) or isinstance(entity.state[name], bool):
        raise ValueError(f"color-map property {name!r} is missing or non-numeric")
    low, high = behavior.config["minimum"], behavior.config["maximum"]
    amount = 0.0 if high == low else min(1.0, max(0.0, (entity.state[name] - low) / (high - low)))
    a, b = behavior.config["low_color"], behavior.config["high_color"]
    entity.visual.color = tuple(round(a[index] + (b[index] - a[index]) * amount) for index in range(4))
""",
    ),
)


assert len(BUILTIN_BEHAVIORS) == 24


__all__ = ["BUILTIN_BEHAVIORS"]
