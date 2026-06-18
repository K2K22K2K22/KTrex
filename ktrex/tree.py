from pathlib import Path

from .fs import InvalidName, create_dir, create_file, remove_created, validate_name

MAX_DEPTH = 64


class InvalidTree(ValueError):
    """Raised when a structure or preset is not a valid tree."""


def build_tree(path: Path) -> dict:
    # Convert filesystem into a serializable tree structure
    node = {"name": path.name, "type": "dir", "children": []}

    for p in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name)):
        if p.is_dir():
            node["children"].append(build_tree(p))
        else:
            node["children"].append({"name": p.name, "type": "file"})

    return node


def validate_tree(node, depth: int = 0) -> None:
    """Check a structure or preset before it reaches the filesystem."""
    if depth > MAX_DEPTH:
        raise InvalidTree(f"tree is deeper than {MAX_DEPTH} levels")
    if not isinstance(node, dict):
        raise InvalidTree("every entry must be an object")

    name = node.get("name")
    if not isinstance(name, str):
        raise InvalidTree("every entry needs a name")
    try:
        validate_name(name)
    except InvalidName as e:
        raise InvalidTree(f"invalid entry name '{name}': {e}") from e

    kind = node.get("type")
    if kind not in ("dir", "file"):
        raise InvalidTree(f"entry '{name}' has invalid type {kind!r}")

    children = node.get("children")
    if kind == "file":
        if children:
            raise InvalidTree(f"file entry '{name}' cannot have children")
        return

    if children is None:
        return
    if not isinstance(children, list):
        raise InvalidTree(f"directory '{name}' needs a list of children")

    seen = set()
    for child in children:
        validate_tree(child, depth + 1)
        if child["name"] in seen:
            raise InvalidTree(f"duplicate name '{child['name']}' in '{name}'")
        seen.add(child["name"])


def apply_tree(base: Path, tree: dict) -> list[Path]:
    """Create the missing entries of tree under base and return them.

    The whole tree is validated first, so a bad entry never leaves a half
    written structure behind. Entries created by this call are removed
    again if a later one fails.
    """
    validate_tree(tree)
    created: list[Path] = []
    try:
        _apply_children(base, tree.get("children") or [], created)
    except BaseException:
        for path in reversed(created):
            remove_created(path)
        raise
    return created


def _apply_children(base: Path, children: list, created: list[Path]) -> None:
    for child in children:
        name = child["name"]

        if child["type"] == "dir":
            new = create_dir(base, name)
            if new is not None:
                created.append(new)
            _apply_children(base / name, child.get("children") or [], created)
        else:
            new = create_file(base, name)
            if new is not None:
                created.append(new)
