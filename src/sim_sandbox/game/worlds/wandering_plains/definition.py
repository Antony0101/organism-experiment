"""Definition for the large wandering plains scenario."""

from ...entities import WanderingAgent
from ...terrain import TerrainMap
from ...world_definition import WorldDefinition, WorldLaunchOptions, WorldSession
from ....engine.world import World


def create_world(options: WorldLaunchOptions) -> WorldSession:
    terrain = TerrainMap(options.seed, width=256, height=256, tile_size=16)
    world = World(options.seed, terrain)
    for _ in range(options.entity_count):
        x, y = terrain.random_passable_position(world.rng)
        world.spawn(WanderingAgent(x, y))
    world.flush()
    return WorldSession(
        world=world,
        initial_camera_position=(terrain.pixel_width / 2, terrain.pixel_height / 2),
        initial_zoom=1.0,
    )


WORLD_DEFINITION = WorldDefinition(
    id="wandering_plains",
    name="Wandering Plains",
    description="A large procedural landscape populated by wandering agents.",
    menu_order=10,
    default_seed=1,
    default_population=1_000,
    factory=create_world,
)
