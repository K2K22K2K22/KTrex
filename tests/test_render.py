import os

import pytest

from ktrex.render import collect_rows, format_row, render_tree
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


@pytest.mark.skipif(
    getattr(os, "geteuid", lambda: -1)() == 0, reason="root ignores directory permissions"
)
@pytest.mark.skipif(os.name == "nt", reason="Windows chmod cannot make a directory unreadable")
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


def test_collect_rows_collapsed_by_default(project):
    (project / "a").mkdir()
    (project / "a" / "f.txt").touch()

    rows = collect_rows(project, expanded=set())

    assert [r.name for r in rows] == ["a"]
    assert rows[0].is_dir is True
    assert rows[0].expanded is False


def test_collect_rows_expands_listed_dirs(project):
    (project / "a").mkdir()
    (project / "a" / "f.txt").touch()

    rows = collect_rows(project, expanded={project / "a"})

    assert [r.name for r in rows] == ["a", "f.txt"]
    assert rows[0].expanded is True


def test_format_row_arrow_reflects_expansion(project):
    (project / "a").mkdir()

    collapsed = collect_rows(project, expanded=set())[0]
    opened = collect_rows(project, expanded={project / "a"})[0]

    assert "[+] a" in format_row(collapsed)
    assert "[-] a" in format_row(opened)

