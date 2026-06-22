import pytest

from ktrex import state
from ktrex.fs import create_dir, create_file, undo_last
from ktrex.presets import load_preset
from ktrex.tree import apply_tree


def test_undo_empty_history(project):
    assert undo_last() is False


def test_undo_walks_back_a_preset(project):
    load_preset("ml_project", project)
    count = len(state.history)
    assert count > 0

    for _ in range(count):
        assert undo_last() is True

    assert state.history == []
    assert list(project.iterdir()) == []


def test_undo_walks_back_an_applied_tree(project):
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {"name": "a", "type": "dir", "children": [{"name": "x.txt", "type": "file"}]},
            {"name": "b.txt", "type": "file"},
        ],
    }
    apply_tree(project, tree)

    assert undo_last() is True  # b.txt
    assert undo_last() is True  # a/x.txt
    assert undo_last() is True  # a, now empty
    assert list(project.iterdir()) == []
    assert undo_last() is False


def test_rollback_leaves_history_empty(project, monkeypatch):
    from ktrex import fs

    real = fs.create_file

    def failing(base, name):
        if name == "boom":
            raise OSError("disk full")
        return real(base, name)

    monkeypatch.setattr("ktrex.tree.create_file", failing)
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {"name": "a.txt", "type": "file"},
            {"name": "boom", "type": "file"},
        ],
    }

    with pytest.raises(OSError):
        apply_tree(project, tree)

    assert state.history == []
    assert list(project.iterdir()) == []


def test_undo_stops_at_non_empty_dir(project):
    d = create_dir(project, "src")
    assert d is not None
    create_file(d, "gen.py")
    (d / "manual.txt").write_text("user file")

    assert undo_last() is True  # removes gen.py
    assert undo_last() is False  # src holds manual.txt, stays

    assert (d / "manual.txt").is_file()
