"""Filesystem operations for KTrex.

Every entry is created through this module so the undo history stays in
sync with what is on disk. The contract is:

- create_dir and create_file append the new path to the undo history and
  never touch an existing path.
- undo_last removes the most recent entry: a file always, a directory only
  when it is empty. An empty history returns False without side effects.
- remove_created drops an entry again. apply_tree uses it to roll back
  everything a failed multi entry apply had created.
- Names are single path segments and every target stays inside the project
  root.
"""

from pathlib import Path

from . import state


class InvalidName(ValueError):
    """Raised when an entry name is not a valid single path segment."""


def validate_name(name: str) -> str:
    if not name or not name.strip():
        raise InvalidName("name cannot be empty")
    if name in (".", ".."):
        raise InvalidName(f"name cannot be '{name}'")
    if Path(name).is_absolute():
        raise InvalidName("name cannot be an absolute path")
    if "/" in name or "\\" in name:
        raise InvalidName("name cannot contain path separators")
    if "\x00" in name:
        raise InvalidName("name cannot contain null bytes")
    return name


def resolve_target(base: Path, name: str) -> Path:
    """Return base/name, rejecting anything that resolves outside the root."""
    target = base / name
    root = state.root_dir
    if root is not None:
        root = root.resolve()
        resolved = target.resolve()
        if resolved != root and root not in resolved.parents:
            raise InvalidName(f"path escapes the project root: {name}")
    return target


def create_dir(base: Path, name: str) -> Path | None:
    validate_name(name)
    target = resolve_target(base, name)
    if target.is_symlink() or target.exists():
        return None

    target.mkdir()
    state.history.append(target)
    return target


def create_file(base: Path, name: str) -> Path | None:
    validate_name(name)
    target = resolve_target(base, name)
    if target.is_symlink() or target.exists():
        return None

    target.touch()
    state.history.append(target)
    return target


def undo_last() -> bool:
    """Undo the most recent creation. Files are removed, directories only when empty."""
    if not state.history:
        return False

    p = state.history.pop()

    if p.is_file():
        p.unlink()
        return True

    if p.is_dir():
        # only remove empty directories, never data
        if any(p.iterdir()):
            state.history.append(p)  # put it back, nothing was undone
            return False
        p.rmdir()
        return True

    return False


def remove_created(path: Path) -> bool:
    """Drop a path created by apply_tree from disk and from the undo history."""
    try:
        state.history.remove(path)
    except ValueError:
        pass

    if path.is_symlink():
        return False
    if path.is_file():
        path.unlink()
        return True
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        return True
    return False
