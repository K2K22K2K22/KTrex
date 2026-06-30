"""Filesystem operations for KTrex.

Operations record enough metadata to validate undo safely: operation type,
target, whether it was created by KTrex, and optional identity. Undo refuses to
remove non-empty directories, refuses to remove a replacement/external change,
and never drops history on a failed undo.
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
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise InvalidName("name cannot contain control characters")
    return name


def resolve_target(base: Path, name: str) -> Path:
    target = base / name
    root = state.root_dir
    if root is not None:
        try:
            root_r = root.resolve()
            resolved = target.resolve()
        except (FileNotFoundError, RuntimeError):
            raise InvalidName(f"path escapes the project root: {name}")
        if resolved != root_r and root_r not in resolved.parents:
            raise InvalidName(f"path escapes the project root: {name}")
    return target


def _op_stat(p: Path) -> tuple[float, int]:
    try:
        st = p.stat()
        return st.st_mtime, st.st_size
    except (FileNotFoundError, OSError):
        return 0.0, -1


def create_dir(base: Path, name: str) -> Path | None:
    validate_name(name)
    target = resolve_target(base, name)
    if target.is_symlink() or target.exists():
        return None

    target.mkdir()
    mtime, size = _op_stat(target)
    state.history.append(
        {"op": "dir", "path": target, "created": True, "mtime": mtime, "size": size}
    )
    return target


def create_file(base: Path, name: str) -> Path | None:
    validate_name(name)
    target = resolve_target(base, name)
    if target.is_symlink() or target.exists():
        return None

    target.touch()
    mtime, size = _op_stat(target)
    state.history.append(
        {"op": "file", "path": target, "created": True, "mtime": mtime, "size": size}
    )
    return target


def undo_last() -> bool:
    if not state.history:
        return False

    op = state.history.pop()
    p = op.get("path")
    if p is None:
        return False
    op_type = op.get("op")

    if p.is_symlink():
        try:
            p.unlink()
            return True
        except (FileNotFoundError, OSError):
            state.history.append(op)
            return False

    if p.is_file():
        mtime, size = _op_stat(p)
        if mtime != op.get("mtime", -1) or size != op.get("size", -2):
            state.history.append(op)
            return False
        try:
            p.unlink()
            return True
        except (FileNotFoundError, OSError):
            state.history.append(op)
            return False

    if p.is_dir():
        if op_type != "dir":
            state.history.append(op)
            return False
        try:
            if any(p.iterdir()):
                state.history.append(op)
                return False
        except (FileNotFoundError, OSError):
            state.history.append(op)
            return False
        try:
            p.rmdir()
            return True
        except (FileNotFoundError, OSError):
            state.history.append(op)
            return False

    if not p.exists():
        return True

    state.history.append(op)
    return False


def remove_created(path: Path) -> bool:
    try:
        for i, op in enumerate(state.history):
            if op.get("path") == path:
                del state.history[i]
                break
    except (ValueError, IndexError):
        pass

    try:
        if path.is_symlink():
            path.unlink()
            return True
        if path.is_file():
            path.unlink()
            return True
        if path.is_dir():
            try:
                if any(path.iterdir()):
                    return False
            except (FileNotFoundError, OSError):
                return False
            path.rmdir()
            return True
        return False
    except (FileNotFoundError, OSError):
        return False
