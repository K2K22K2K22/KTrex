import pytest

from ktrex.tree import InvalidTree, apply_tree, validate_tree


def dir_node(name, *children):
    return {"name": name, "type": "dir", "children": list(children)}


def file_node(name):
    return {"name": name, "type": "file"}


def test_valid_tree_passes():
    tree = dir_node("root", dir_node("src", file_node("main.py")), file_node("readme.md"))
    validate_tree(tree)


@pytest.mark.parametrize("name", ["../evil", "a/b", "/abs", "..", ""])
def test_rejects_bad_names(name):
    with pytest.raises(InvalidTree):
        validate_tree(dir_node("root", file_node(name)))


def test_rejects_bad_type():
    with pytest.raises(InvalidTree):
        validate_tree({"name": "x", "type": "socket"})


def test_rejects_children_on_file():
    with pytest.raises(InvalidTree):
        validate_tree(file_node("x") | {"children": [file_node("y")]})


def test_rejects_duplicate_names():
    with pytest.raises(InvalidTree):
        validate_tree(dir_node("root", file_node("a"), file_node("a")))


def test_rejects_non_list_children():
    with pytest.raises(InvalidTree):
        validate_tree({"name": "root", "type": "dir", "children": "nope"})


def test_rejects_tree_deeper_than_limit():
    node = file_node("leaf")
    for _ in range(70):
        node = dir_node("d", node)

    with pytest.raises(InvalidTree):
        validate_tree(node)


def test_apply_creates_tree(project):
    tree = dir_node("root", dir_node("src", file_node("main.py")), file_node("readme.md"))

    created = apply_tree(project, tree)

    assert (project / "src" / "main.py").is_file()
    assert (project / "readme.md").is_file()
    assert len(created) == 3


def test_apply_is_additive(project):
    (project / "src").mkdir()
    tree = dir_node("root", dir_node("src", file_node("main.py")))

    apply_tree(project, tree)

    assert (project / "src" / "main.py").is_file()


def test_apply_validates_before_creating(project):
    tree = dir_node("root", dir_node("src"), file_node("../evil"))

    with pytest.raises(InvalidTree):
        apply_tree(project, tree)

    assert list(project.iterdir()) == []


def test_apply_rolls_back_on_failure(project, monkeypatch):
    from ktrex import fs

    real = fs.create_file

    def failing(base, name):
        if name == "boom":
            raise OSError("disk full")
        return real(base, name)

    monkeypatch.setattr("ktrex.tree.create_file", failing)
    tree = dir_node("root", file_node("a.txt"), file_node("boom"), file_node("b.txt"))

    with pytest.raises(OSError):
        apply_tree(project, tree)

    assert list(project.iterdir()) == []
