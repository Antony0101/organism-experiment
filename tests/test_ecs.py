"""Engine errors and, in subsequent steps, entity/component contracts."""

import pytest

import simworld
from simworld import errors


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
