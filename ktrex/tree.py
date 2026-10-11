from pathlib import Path

from .fs import InvalidName, create_dir, create_file, remove_created, validate_name

MAX_DEPTH = 64


class InvalidTree(ValueError):
    """Raised when a structure or preset is not a valid tree."""


class RollbackError(Exception):
    """A failed apply left artifacts behind after an incomplete rollback.

    Carries the original application error as __cause__ and lists the
    paths that could not be removed in ``leftover_paths``.
    """

    def __init__(self, message: str, leftover_paths: list[Path]):
        super().__init__(message)
        self.leftover_paths = leftover_paths


def build_tree(path: Path, depth: int = 0) -> dict:
    # Convert filesystem into a serializable tree structure.
    # Symlinked directories are listed but not followed, unreadable
    # directories come back empty, and very deep trees are cut off.
    node = {"name": path.name, "type": "dir", "children": []}
    if depth >= MAX_DEPTH:
        return node

    try:
        entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except OSError:
        return node

    for p in entries:
        if p.is_dir() and not p.is_symlink():
            node["children"].append(build_tree(p, depth + 1))
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


def _rollback(created: list[Path]) -> list[Path]:
    """Undo created paths in reverse order; report anything that survived.

    Only empty directories and unmodified files created by the failed
    operation are removed. Failures keep the history entry, so the user
    can still undo manually, and the surviving paths are returned.
    """
    leftovers: list[Path] = []
    for path in reversed(created):
        if not remove_created(path):
            leftovers.append(path)
    return leftovers


def apply_tree(base: Path, tree: dict) -> list[Path]:
    """Create the missing entries of tree under base and return them.

    The whole tree is validated first, so a bad entry never leaves a half
    written structure behind. Entries created by this call are removed
    again if a later one fails. When rollback cannot remove an entry, for
    example because the directory gained content meanwhile, RollbackError
    is raised from the original error and names the surviving paths.
    """
    validate_tree(tree)
    created: list[Path] = []
    try:
        _apply_children(base, tree.get("children") or [], created)
    except BaseException as original:
        leftovers = _rollback(created)
        if leftovers:
            names = ", ".join(str(p) for p in leftovers)
            raise RollbackError(
                f"apply failed ({original}) and rollback could not remove: {names}",
                leftovers,
            ) from original
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
