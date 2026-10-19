from pathlib import Path

import pytest


def _pyproject() -> str:
    path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert path.is_file(), "pyproject.toml must ship with the source tree"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pyproject() -> str:
    return _pyproject()


def test_pypi_metadata_declares_py310_minimum(pyproject):
    assert 'requires-python = ">=3.10"' in pyproject


def test_pyproject_version_matches_package_version(pyproject):
    from ktrex import __version__

    assert f'version = "{__version__}"' in pyproject


def test_windows_curses_is_a_conditional_dependency(pyproject):
    assert 'windows-curses>=2.4.2; platform_system == "Windows"' in pyproject


def test_windows_dependency_marker_gates_on_platform_only(pyproject):
    # The marker must not leak onto Linux/macOS installs.
    line = next(l for l in pyproject.splitlines() if "windows-curses" in l)
    assert 'platform_system == "Windows"' in line
    assert ";" in line


def test_os_and_python_classifiers_match_support(pyproject):
    assert "Operating System :: Microsoft :: Windows" in pyproject
    for minor in (10, 11, 12, 13, 14):
        assert f"Programming Language :: Python :: 3.{minor}" in pyproject


def test_console_entry_points_declared(pyproject):
    assert 'ktrex = "ktrex.main:main"' in pyproject
    assert 'KTrex = "ktrex.main:main"' in pyproject


def test_bundled_presets_ship_as_package_data(pyproject):
    assert 'ktrex = ["presets/*.json"]' in pyproject
