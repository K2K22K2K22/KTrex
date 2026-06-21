import importlib
import importlib.metadata

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "ktrex",
        "ktrex.state",
        "ktrex.fs",
        "ktrex.tree",
        "ktrex.render",
        "ktrex.presets",
        "ktrex.tui",
        "ktrex.main",
    ],
)
def test_module_imports_cleanly(module):
    importlib.import_module(module)


def test_console_entry_points_registered():
    scripts = importlib.metadata.entry_points(group="console_scripts")
    names = {ep.name for ep in scripts}

    assert {"ktrex", "KTrex"} <= names
