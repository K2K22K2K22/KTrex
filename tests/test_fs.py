import pytest

from ktrex import state
from ktrex.fs import (
    InvalidName,
    _validate_windows_name,
    create_dir,
    create_file,
    undo_last,
    validate_name,
)


@pytest.mark.parametrize("bad", ["", "   "])
def test_rejects_empty_name(project, bad):
    with pytest.raises(InvalidName):
        create_dir(project, bad)


@pytest.mark.parametrize("bad", [".", ".."])
def test_rejects_dot_names(project, bad):
    with pytest.raises(InvalidName):
        create_file(project, bad)


@pytest.mark.parametrize("bad", ["/etc/passwd", "a/b", "a\\b", "sub/../x"])
def test_rejects_absolute_and_separators(project, bad):
    with pytest.raises(InvalidName):
        create_dir(project, bad)


def test_rejects_null_byte(project):
    with pytest.raises(InvalidName):
        create_file(project, "a\x00b")


def test_creates_dir_and_file(project):
    d = create_dir(project, "src")
    f = create_file(project, "main.py")

    assert d is not None and d.is_dir() and d == project / "src"
    assert f is not None and f.is_file() and f == project / "main.py"
    assert len(state.history) == 2
    assert state.history[0].get("path") == d
    assert state.history[1].get("path") == f


def test_existing_dir_is_skipped(project):
    create_dir(project, "src")
    assert create_dir(project, "src") is None


def test_existing_file_blocks_dir(project):
    create_file(project, "thing")
    assert create_dir(project, "thing") is None
    assert (project / "thing").is_file()


def test_symlink_is_not_overwritten(project):
    target = project / "target"
    target.mkdir()
    (project / "link").symlink_to(target)

    assert create_dir(project, "link") is None
    assert (project / "link").is_symlink()


def test_symlinked_base_cannot_escape_root(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    escape = project / "escape"
    escape.symlink_to(outside)

    with pytest.raises(InvalidName):
        create_dir(escape, "x")

    assert list(outside.iterdir()) == []


def test_undo_removes_file(project):
    create_file(project, "a.txt")

    assert undo_last() is True
    assert not (project / "a.txt").exists()


def test_undo_keeps_non_empty_dir(project):
    d = create_dir(project, "src")
    assert d is not None
    (d / "outside.txt").write_text("not tracked")  # keeps the dir non-empty

    assert undo_last() is False

    assert d.exists()
    assert len(state.history) == 1
    assert state.history[0].get("path") == d


# --- Windows name rules -------------------------------------------------------

@pytest.mark.parametrize("name", ["a<b", "a>b", "a:b", 'a"b', "a|b", "a?b", "a*b", "C:x"])
def test_windows_rejects_illegal_characters(name):
    with pytest.raises(InvalidName):
        _validate_windows_name(name)


@pytest.mark.parametrize(
    "name",
    ["trailing ", "trailing.", "con", "CON", "NUL", "nul.txt", "aux.log", "COM1", "Lpt9.bak"],
)
def test_windows_rejects_unstorable_names(name):
    with pytest.raises(InvalidName):
        _validate_windows_name(name)


@pytest.mark.parametrize("name", ["com10", "console", "contact.txt", "a", "v1.2", "nuls.txt", "sp ace"])
def test_windows_allows_everyday_names(name):
    assert _validate_windows_name(name) is None


def test_windows_rules_apply_only_on_windows(monkeypatch):
    # "con" is a perfectly legal directory name on Linux and stays that way.
    monkeypatch.setattr("ktrex.fs._is_windows", lambda: False)
    assert validate_name("con") == "con"
    assert validate_name("a:b") == "a:b"

    monkeypatch.setattr("ktrex.fs._is_windows", lambda: True)
    with pytest.raises(InvalidName):
        validate_name("con")
    with pytest.raises(InvalidName):
        validate_name("a:b")


def test_windows_rejects_reserved_name_before_touching_disk(project, monkeypatch):
    monkeypatch.setattr("ktrex.fs._is_windows", lambda: True)

    with pytest.raises(InvalidName):
        create_dir(project, "con")

    assert list(project.iterdir()) == []


def test_windows_rejects_trailing_dot_before_touching_disk(project, monkeypatch):
    monkeypatch.setattr("ktrex.fs._is_windows", lambda: True)

    with pytest.raises(InvalidName):
        create_file(project, "oops.")

    assert list(project.iterdir()) == []
