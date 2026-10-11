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


# --- identity hardening -------------------------------------------------------

import os
import stat

from ktrex.fs import _identity, remove_created


def test_undo_refuses_replaced_file_with_different_content(project):
    f = create_file(project, "a.txt")
    assert f is not None
    f.write_text("replaced entirely")

    assert undo_last() is False
    assert f.exists()
    assert state.history  # refused op stays in history


def test_undo_refuses_replaced_file_with_matching_size(project):
    f = create_file(project, "a.txt")
    assert f is not None
    f.write_text("original")
    original_size = f.stat().st_size
    f.write_text("killedxxx"[:original_size])  # same size, different bytes

    assert undo_last() is False
    assert f.exists()


def test_undo_refuses_replaced_file_with_matching_size_and_mtime(project):
    f = create_file(project, "a.txt")
    assert f is not None
    st_before = f.stat()
    f.write_text("zzzzzzzz"[: f.stat().st_size or 8])
    os.utime(f, ns=(st_before.st_atime_ns, st_before.st_mtime_ns))

    assert undo_last() is False
    assert f.exists()


def test_undo_refuses_externally_modified_file(project):
    f = create_file(project, "a.txt")
    assert f is not None
    with f.open("a") as fh:
        fh.write("more")

    assert undo_last() is False
    assert f.read_text().endswith("more")


def test_undo_drops_missing_target_cleanly(project):
    f = create_file(project, "gone.txt")
    assert f is not None
    f.unlink()

    assert undo_last() is True
    assert state.history == []


def test_undo_refuses_regular_file_substituted_for_symlink_op(project):
    # KTrex created a dir; a regular file now sits at the same path.
    d = create_dir(project, "thing")
    assert d is not None
    d.rmdir()
    d.write_text("now a file")

    assert undo_last() is False
    assert d.is_file()


def test_undo_refuses_one_symlink_replaced_with_another(project, tmp_path):
    f = create_file(project, "a.txt")
    assert f is not None
    real = tmp_path / "real.txt"
    real.write_text("x")
    f.unlink()
    f.symlink_to(real)
    other = tmp_path / "other.txt"
    other.write_text("y")
    f.unlink()
    f.symlink_to(other)

    assert undo_last() is False
    assert f.is_symlink()
    assert other.exists()


def test_undo_refuses_dir_swapped_for_symlink_to_file(project, tmp_path):
    d = create_dir(project, "d")
    assert d is not None
    d.rmdir()
    (tmp_path / "f.txt").write_text("x")
    d.symlink_to(tmp_path / "f.txt")

    assert undo_last() is False
    assert d.is_symlink()
    assert (tmp_path / "f.txt").exists()


def test_undo_refuses_when_identity_differs_but_metadata_matches(project, monkeypatch):
    f = create_file(project, "a.txt")
    assert f is not None
    # Forge a history entry whose identity points elsewhere, like a
    # same-size, same-mtime replacement with a different inode would.
    op = state.history[-1]
    old_ident = op.get("ident") or {}
    op["ident"] = {
        "dev": old_ident.get("dev", 0),
        "ino": old_ident.get("ino", 0) + 1,
        "mode": stat.S_IFREG,
    }

    assert undo_last() is False
    assert f.exists()


def test_undo_falls_back_when_inodes_are_unsupported(project, monkeypatch):
    f = create_file(project, "a.txt")
    assert f is not None
    # Filesystems without inode support report st_ino == 0: undo must still
    # work through the metadata fallback.
    op = state.history[-1]
    old_ident = op.get("ident") or {}
    op["ident"] = {"dev": old_ident.get("dev", 0), "ino": 0, "mode": old_ident.get("mode", 0)}

    assert undo_last() is True
    assert not f.exists()
    assert state.history == []


def test_undo_preserves_history_on_permission_failure(project, monkeypatch):
    f = create_file(project, "a.txt")
    assert f is not None

    def denied(_path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("ktrex.fs.Path.unlink", denied)
    assert undo_last() is False
    assert state.history  # history kept for a later retry
    monkeypatch.undo()
    assert undo_last() is True


def test_remove_created_refuses_unknown_path(project):
    stranger = project / "not-ours.txt"
    stranger.write_text("x")

    assert remove_created(stranger) is False
    assert stranger.exists()


def test_remove_created_refuses_replaced_path(project):
    f = create_file(project, "a.txt")
    assert f is not None
    f.write_text("replaced")

    assert remove_created(f) is False
    assert f.exists()
    assert state.history  # entry kept, rollback caller can report it


def test_remove_created_removes_recorded_file(project):
    f = create_file(project, "a.txt")
    assert f is not None

    assert remove_created(f) is True
    assert not f.exists()
    assert state.history == []


def test_identity_uses_lstat_not_stat(project, tmp_path):
    f = create_file(project, "a.txt")
    assert f is not None
    target = tmp_path / "elsewhere.txt"
    target.write_text("x")
    ident = _identity(f)
    assert ident is not None and ident["ino"] != 0

    link = tmp_path / "link.txt"
    link.symlink_to(target)
    link_ident = _identity(link)
    assert link_ident is not None
    # lstat sees the link itself, never the target.
    assert stat.S_IFMT(link_ident["mode"]) == stat.S_IFLNK


# --- rollback failure reporting ----------------------------------------------

from ktrex.tree import RollbackError


def test_apply_failure_rolls_back_in_reverse_and_keeps_error(project, monkeypatch):
    import ktrex.tree as tree_mod

    real = tree_mod.create_file

    def failing(base, name):
        if name == "boom":
            raise OSError("disk full")
        return real(base, name)

    monkeypatch.setattr(tree_mod, "create_file", failing)
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {"name": "d", "type": "dir", "children": [{"name": "x.txt", "type": "file"}]},
            {"name": "boom", "type": "file"},
        ],
    }

    with pytest.raises(OSError, match="disk full"):
        apply_tree(project, tree)

    assert list(project.iterdir()) == []
    assert state.history == []


def test_rollback_leftovers_are_reported_with_original_error(project, monkeypatch):
    import ktrex.tree as tree_mod
    from ktrex.fs import remove_created

    real_create = tree_mod.create_file
    real_remove = tree_mod.remove_created

    def failing(base, name):
        if name == "boom":
            raise OSError("disk full")
        return real_create(base, name)

    def refusing(path):
        if path.name == "stuck.txt":
            return False
        return real_remove(path)

    monkeypatch.setattr(tree_mod, "create_file", failing)
    monkeypatch.setattr(tree_mod, "remove_created", refusing)
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {"name": "stuck.txt", "type": "file"},
            {"name": "boom", "type": "file"},
        ],
    }

    with pytest.raises(RollbackError) as exc_info:
        apply_tree(project, tree)

    err = exc_info.value
    assert isinstance(err.__cause__, OSError)
    assert "disk full" in str(err.__cause__)
    assert err.leftover_paths == [project / "stuck.txt"]
    assert "stuck.txt" in str(err)
    assert (project / "stuck.txt").exists()  # artifact remains, user is told
    assert state.history  # its history entry stays for manual undo


def test_nonempty_created_dir_blocks_rollback_and_is_reported(project, monkeypatch):
    import ktrex.tree as tree_mod

    real_create = tree_mod.create_file

    def hook(base, name):
        result = real_create(base, name)
        if name == "filler.txt":
            # Another process drops a file into the directory meanwhile.
            (base / "inner.txt").write_text("user data")
        if name == "boom":
            raise OSError("disk full")
        return result

    monkeypatch.setattr(tree_mod, "create_file", hook)
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {
                "name": "outer",
                "type": "dir",
                "children": [
                    {"name": "filler.txt", "type": "file"},
                    {"name": "boom", "type": "file"},
                ],
            }
        ],
    }

    with pytest.raises(RollbackError) as exc_info:
        apply_tree(project, tree)

    err = exc_info.value
    assert (project / "outer" / "inner.txt").exists()  # user data preserved
    assert project / "outer" in err.leftover_paths
    assert isinstance(err.__cause__, OSError)


def test_rollback_history_consistent_after_failed_apply(project, monkeypatch):
    import ktrex.tree as tree_mod

    real = tree_mod.create_file

    def failing(base, name):
        if name == "boom":
            raise OSError("disk full")
        return real(base, name)

    monkeypatch.setattr(tree_mod, "create_file", failing)
    tree = {
        "name": "root",
        "type": "dir",
        "children": [
            {"name": "ok.txt", "type": "file"},
            {"name": "boom", "type": "file"},
        ],
    }

    with pytest.raises(OSError):
        apply_tree(project, tree)

    # Fully rolled back: no leftovers, no history, nothing on disk.
    assert state.history == []
    assert list(project.iterdir()) == []
