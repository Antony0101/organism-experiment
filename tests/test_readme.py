"""Execute each marked README example as a self-contained program."""

from __future__ import annotations

from pathlib import Path
import re

import pytest


README = Path(__file__).resolve().parent.parent / "README.md"
BLOCKS = re.findall(
    r"<!-- run -->\s*```python\n(.*?)```",
    README.read_text(encoding="utf-8"),
    re.S,
)


def test_readme_has_runnable_blocks():
    # Raise this threshold to eight when the engine documentation is complete.
    assert len(BLOCKS) >= 1


@pytest.mark.parametrize("i", range(len(BLOCKS)))
def test_readme_block_runs(i, tmp_path, monkeypatch, clean_components):
    monkeypatch.chdir(tmp_path)
    exec(
        compile(BLOCKS[i], f"README block {i}", "exec"),
        {"__name__": "__readme__"},
    )
