"""Engine errors and, in subsequent steps, entity/component contracts."""

import json

import pytest

import simworld
from simworld import errors
from simworld.ecs import EntityAllocator, entity_generation, entity_index


@pytest.mark.parametrize(
    ("name", "builtin"),
    [
        ("UnknownNameError", LookupError),
        ("UnknownComponentError", LookupError),
        ("UnknownLayerError", LookupError),
        ("UnknownTerrainError", LookupError),
        ("UnknownActionError", LookupError),
        ("UnknownModuleError", LookupError),
        ("UnknownBrainError", LookupError),
        ("UnknownPrefabError", LookupError),
        ("UnknownSystemError", LookupError),
        ("StaleEntityError", LookupError),
        ("MissingComponentError", LookupError),
        ("DuplicateNameError", ValueError),
        ("NotAComponentError", TypeError),
        ("OutOfBoundsError", IndexError),
        ("ConfigError", ValueError),
        ("ActionError", Exception),
        ("ActionRejected", Exception),
        ("PluginError", Exception),
        ("SerializationError", Exception),
    ],
)
def test_engine_errors_keep_builtin_ancestry(name, builtin):
    cls = getattr(errors, name)
    assert issubclass(cls, errors.SimWorldError)
    assert issubclass(cls, builtin)


def test_entity_ids_begin_at_generation_one_and_decode_to_slots():
    allocator = EntityAllocator()
    assert allocator.count_alive() == 0
    first, second = allocator.alloc(), allocator.alloc()
    assert first == 1 << 32 and second == (1 << 32) | 1
    assert (entity_index(first), entity_generation(first)) == (0, 1)
    assert (entity_index(second), entity_generation(second)) == (1, 1)
    assert allocator.is_alive(first) and allocator.is_alive(second)
    assert allocator.check(first) is None
    assert allocator.count_alive() == 2


def test_release_reuses_slots_in_lifo_order_with_new_generations():
    allocator = EntityAllocator()
    first, second, third = (allocator.alloc() for _ in range(3))
    allocator.release(first)
    allocator.release(third)
    assert allocator.count_alive() == 1
    assert not allocator.is_alive(first) and not allocator.is_alive(third)
    replacement_third, replacement_first = allocator.alloc(), allocator.alloc()
    assert replacement_third == (2 << 32) | 2
    assert replacement_first == 2 << 32
    assert allocator.is_alive(second)
    assert allocator.count_alive() == 3
    with pytest.raises(errors.StaleEntityError) as caught:
        allocator.check(first)
    message = str(caught.value)
    assert str(first) in message and "despawned" in message
    assert "generation 1" in message and "generation 2" in message
    assert "slot 0" in message


@pytest.mark.parametrize("invalid", [None, "4294967296", 1.5, -1, 0, True, [], 1, (1 << 32) | 99, 7 << 32])
def test_invalid_ids_are_safe_and_failed_release_preserves_allocation(invalid):
    allocator = EntityAllocator()
    live = allocator.alloc()
    before = (allocator.generations[:], allocator.alive[:], allocator.free[:])
    assert allocator.is_alive(invalid) is False
    with pytest.raises(errors.StaleEntityError):
        allocator.check(invalid)
    with pytest.raises(errors.StaleEntityError):
        allocator.release(invalid)
    assert (allocator.generations, allocator.alive, allocator.free) == before
    assert allocator.is_alive(live)


def test_releasing_dead_id_twice_does_not_duplicate_free_slot():
    allocator = EntityAllocator()
    old = allocator.alloc()
    allocator.release(old)
    with pytest.raises(errors.StaleEntityError, match="despawned"):
        allocator.release(old)
    new = allocator.alloc()
    assert new == 2 << 32
    assert entity_index(allocator.alloc()) == 1


def test_invalid_id_diagnostics_distinguish_types_and_unallocated_slots():
    allocator = EntityAllocator()
    with pytest.raises(errors.StaleEntityError, match="not an entity id"):
        allocator.check("bad")
    with pytest.raises(errors.StaleEntityError, match="never existed"):
        allocator.check(1 << 32)


def test_entity_helpers_are_exported_and_allocators_are_independent():
    first, second = EntityAllocator(), EntityAllocator()
    entity = first.alloc()
    assert not second.is_alive(entity)
    assert second.count_alive() == 0
    assert simworld.entity_index is entity_index
    assert simworld.entity_generation is entity_generation
    assert {"entity_index", "entity_generation"} <= set(simworld.__all__)


def test_fresh_allocations_undo_in_reverse_order_to_exact_empty_state():
    allocator = EntityAllocator()
    before = allocator.to_dict()
    first, second = allocator.alloc(), allocator.alloc()
    allocator.rollback_alloc(second)
    allocator.rollback_alloc(first)
    assert allocator.to_dict() == before
    assert allocator.alloc() == first


def test_recycled_allocations_undo_without_bumping_generations_or_free_order():
    allocator = EntityAllocator()
    first, second = allocator.alloc(), allocator.alloc()
    allocator.release(second)
    allocator.release(first)
    before = allocator.to_dict()
    reused_first, reused_second = allocator.alloc(), allocator.alloc()
    allocator.rollback_alloc(reused_second)
    allocator.rollback_alloc(reused_first)
    assert allocator.to_dict() == before
    assert allocator.alloc() == reused_first
    assert allocator.alloc() == reused_second


def test_releases_revive_in_reverse_order_and_restore_original_ids():
    allocator = EntityAllocator()
    first, second = allocator.alloc(), allocator.alloc()
    before = allocator.to_dict()
    allocator.release(first)
    allocator.release(second)
    allocator.revive(second)
    allocator.revive(first)
    assert allocator.to_dict() == before
    assert allocator.is_alive(first) and allocator.is_alive(second)


def test_create_undo_sequence_restores_state_after_despawn():
    allocator = EntityAllocator()
    before = allocator.to_dict()
    entity = allocator.alloc()
    allocator.release(entity)
    allocator.revive(entity)
    allocator.rollback_alloc(entity)
    assert allocator.to_dict() == before
    assert allocator.alloc() == entity


def test_out_of_order_or_invalid_undo_is_atomic():
    allocator = EntityAllocator()
    first, second = allocator.alloc(), allocator.alloc()
    before = allocator.to_dict()
    with pytest.raises(errors.StaleEntityError, match="LIFO"):
        allocator.rollback_alloc(first)
    assert allocator.to_dict() == before
    allocator.release(first)
    allocator.release(second)
    before = allocator.to_dict()
    for invalid in [first, second + (1 << 32), None, 0, -1, 1 << 50]:
        with pytest.raises(errors.StaleEntityError):
            allocator.revive(invalid)
        assert allocator.to_dict() == before
    with pytest.raises(errors.StaleEntityError):
        allocator.rollback_alloc(second)
    assert allocator.to_dict() == before


def test_allocator_json_roundtrip_preserves_live_and_stale_ids_and_next_allocations():
    allocator = EntityAllocator()
    first, second, third = (allocator.alloc() for _ in range(3))
    allocator.release(third)
    allocator.release(first)
    restored = EntityAllocator.from_dict(json.loads(json.dumps(allocator.to_dict())))
    assert restored.to_dict() == allocator.to_dict()
    assert restored.is_alive(second)
    assert not restored.is_alive(first) and not restored.is_alive(third)
    assert [restored.alloc() for _ in range(3)] == [allocator.alloc() for _ in range(3)]


def test_allocator_serialized_lists_do_not_alias_live_state_or_input():
    allocator = EntityAllocator()
    entity = allocator.alloc()
    allocator.release(entity)
    data = allocator.to_dict()
    restored = EntityAllocator.from_dict(data)
    restored.alloc()
    assert allocator.to_dict() == data
    data["generations"][0] = 99
    data["alive"][0] = True
    data["free"].clear()
    assert allocator.generations == [2] and allocator.alive == [False] and allocator.free == [0]
    assert restored.generations == [2] and restored.alive == [True] and restored.free == []


@pytest.mark.parametrize(
    ("cls", "kind"),
    [
        (errors.UnknownComponentError, "component"),
        (errors.UnknownLayerError, "layer"),
        (errors.UnknownTerrainError, "terrain"),
        (errors.UnknownActionError, "action"),
        (errors.UnknownModuleError, "module"),
        (errors.UnknownBrainError, "brain"),
        (errors.UnknownPrefabError, "prefab"),
        (errors.UnknownSystemError, "system"),
    ],
)
def test_unknown_name_errors_describe_their_kind(cls, kind):
    message = str(cls("watre", ["water", "mud", "land"]))
    assert issubclass(cls, errors.UnknownNameError)
    assert f"unknown {kind}" in message.lower()
    assert "watre" in message
    assert all(name in message for name in ("water", "mud", "land"))
    assert "water" in message.lower().split("did you mean", 1)[1]


def test_unknown_name_supports_kind_override_and_hint():
    message = str(errors.UnknownSystemError(
        "updat", ["update", "late"], "stage", "Choose a registered stage."
    ))
    assert "unknown stage" in message.lower()
    assert "did you mean" in message.lower()
    assert "Choose a registered stage." in message


def test_unknown_name_handles_empty_registry_without_suggestions():
    message = str(errors.UnknownNameError("missing", []))
    assert "missing" in message
    assert "known" in message.lower()
    assert "none" in message.lower()
    assert "did you mean" not in message.lower()


def test_unknown_name_handles_single_use_nonstring_names():
    message = str(errors.UnknownNameError(12, iter([12, 23, 34])))
    assert all(str(name) in message for name in (12, 23, 34))
    assert "did you mean" in message.lower()


def test_unknown_name_does_not_suggest_unrelated_names():
    message = str(errors.UnknownNameError("zzzzz", ["water", "mud"]))
    assert "water" in message and "mud" in message
    assert "did you mean" not in message.lower()


@pytest.mark.parametrize(
    ("cls", "message"),
    [
        (errors.StaleEntityError, "Entity 4294967296 is stale: generation changed"),
        (errors.MissingComponentError, "Entity 4294967296 has no component 'Position'"),
        (errors.DuplicateNameError, "Name 'grazer' is already registered"),
    ],
)
def test_caller_supplied_error_details_are_preserved(cls, message):
    assert str(cls(message)) == message


def test_engine_errors_are_publicly_exported():
    public_errors = {
        name for name, cls in vars(errors).items()
        if isinstance(cls, type) and issubclass(cls, errors.SimWorldError)
    }
    assert len(public_errors) == 20
    assert set(errors.__all__) == public_errors
    assert public_errors <= set(simworld.__all__)
    for name in public_errors:
        assert getattr(simworld, name) is getattr(errors, name)
