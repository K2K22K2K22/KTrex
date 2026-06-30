import pytest

from ktrex.fs import InvalidName, create_dir, create_file, undo_last, validate_name
from ktrex.main import prepare_root
from ktrex.presets import load_preset
from ktrex.tui import sanitize
from test_tui import FakeScreen


@pytest.mark.parametrize("name", ["a\x1b[31m", "a\nb", "a\tb", "a\x00b", "a\x7fb"])
def test_validate_name_rejects_control_characters(name):
    with pytest.raises(InvalidName):
        validate_name(name)


def test_create_file_rejects_escape_sequence(project):
    with pytest.raises(InvalidName):
        create_file(project, "evil\x1b[2J")


def test_put_sanitizes_control_characters(project):
    screen = FakeScreen(10, 40)

    from ktrex.tui import put

    put(screen, 1, 0, "ok\x1b[31mbad\nafter")

    assert screen.writes == [(1, 0, "ok?[31mbad?after")]


def test_sanitize_keeps_printable_unicode():
    assert sanitize("café/naïve") == "café/naïve"


@pytest.mark.parametrize("name", ["../x", "a/b", "..", ".", "a\\b", ""])
def test_load_preset_rejects_traversal_names(project, name):
    with pytest.raises((ValueError, FileNotFoundError)):
        load_preset(name, project)


def test_undo_does_not_follow_symlinked_dir(project, tmp_path):
    d = create_dir(project, "a")
    assert d is not None
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").touch()

    d.rmdir()
    d.symlink_to(outside)

    assert undo_last() is True
    assert (outside / "keep.txt").is_file()  # target untouched
    assert not d.exists()  # the link itself was removed


def test_prepare_root_rejects_a_file(tmp_path):
    target = tmp_path / "plain.txt"
    target.write_text("x")

    with pytest.raises(ValueError):
        prepare_root(str(target))
