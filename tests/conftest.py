"""Shared fixtures for isolated simworld tests."""

import pytest


@pytest.fixture
def clean_components():
    """Restore component registrations after each requesting test."""
    try:
        from simworld.registry import COMPONENTS
    except ModuleNotFoundError as exc:
        if exc.name != "simworld.registry":
            raise
        # The scaffold has no registry yet; activate cleanup once it exists.
        yield
        return

    before = dict(COMPONENTS.items())
    try:
        yield
    finally:
        for name in COMPONENTS.names():
            if name not in before:
                COMPONENTS.unregister(name)
        for name, info in before.items():
            COMPONENTS.register(name, info, replace=True)


# The complete world fixture from BLUEPRINT.md §9.2 is deferred to Step 071
# (Phase 4), when World, BUILTIN_MODULES and terrain definitions are available.
