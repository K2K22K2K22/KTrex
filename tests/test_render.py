import os

import pytest

from ktrex.render import render_tree
from ktrex.tree import build_tree


def test_symlink_loop_is_not_followed(project):
    (project / "real").mkdir()
    (project / "loop").symlink_to(project)

    lines = render_tree(project)

    assert any("loop" in line and "(link)" in line for line in lines)
    assert len(lines) < 50  # terminated instead of recursing forever


def test_build_tree_lists_symlink_without_following(project):
    (project / "real").mkdir()
    (project / "real" / "f.txt").touch()
    (project / "loop").symlink_to(project)

    tree = build_tree(project)
    kinds = {c["name"]: c["type"] for c in tree["children"]}

    assert kinds["loop"] == "file"
    assert kinds["real"] == "dir"
    nested = {c["name"]: c for c in tree["children"]}["real"]
    assert [c["name"] for c in nested["children"]] == ["f.txt"]


def test_render_marks_current_directory(project):
    (project / "src").mkdir()

    lines = render_tree(project, current=project / "src")

    assert any(line.endswith("src  ← current") for line in lines)


def test_render_sorts_dirs_then_names(project):
    (project / "zdir").mkdir()
    (project / "Adir").mkdir()
    (project / "zfile.txt").touch()

    lines = render_tree(project)

    assert lines[0].endswith("Adir")
    assert lines[1].endswith("zdir")
    assert lines[2].endswith("zfile.txt")


def test_render_large_tree_smoke(project):
    for i in range(100):
        (project / f"d{i:03d}").mkdir()
        (project / f"d{i:03d}" / "f.txt").touch()

    lines = render_tree(project)

    assert len(lines) == 200


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_unreadable_directory_is_reported(project):
    secret = project / "secret"
    secret.mkdir()
    (secret / "hidden.txt").touch()
    secret.chmod(0o000)
    try:
        lines = render_tree(project)
        tree = build_tree(project)
    finally:
        secret.chmod(0o755)

    assert any("cannot read" in line for line in lines)
    nested = {c["name"]: c for c in tree["children"]}["secret"]
    assert nested["children"] == []
