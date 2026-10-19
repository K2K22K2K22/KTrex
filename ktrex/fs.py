"""Filesystem operations for KTrex.

Operations record enough metadata to validate undo safely: operation type,
target, whether it was created by KTrex, initial mtime/size, and an lstat
identity (device, inode, file type). Undo refuses to remove non-empty
directories, refuses anything whose identity or metadata no longer matches
the recorded operation, and never drops history on a failed undo.

Identity is a strong hint, not a proof: inode numbers can be reused after
deletion and some filesystems report st_ino == 0. On those, undo falls back
to file type plus mtime/size and stays conservative.
"""

import os
import stat
from pathlib import Path

from . import state


class InvalidName(ValueError):
    """Raised when an entry name is not a valid single path segment."""


def _is_windows() -> bool:
    # Tests monkeypatch this seam instead of os.name, which would make
    # pathlib raise NotImplementedError on Python 3.10 and 3.11.
    return os.name == "nt"


_WIN_ILLEGAL = set('<>:"|?*')
_WIN_RESERVED = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def _validate_windows_name(name: str) -> None:
    """Reject names the Win32 namespace cannot store.

    Checked only when running on Windows: names legal on Linux, such as
    "con" or "a:b", stay legal there.
    """
    for c in name:
        if c in _WIN_ILLEGAL:
            raise InvalidName(f"name cannot contain {c!r} on Windows")
    if name.endswith((" ", ".")):
        raise InvalidName("name cannot end with a space or period on Windows")
    if name.split(".")[0].lower() in _WIN_RESERVED:
        raise InvalidName(f"name is a reserved Windows device name: {name}")


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
    if _is_windows():
        _validate_windows_name(name)
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


def _identity(p: Path) -> dict | None:
    """lstat identity of the directory entry itself, never its target."""
    try:
        st = p.lstat()
    except OSError:
        return None
    return {"dev": st.st_dev, "ino": st.st_ino, "mode": stat.S_IFMT(st.st_mode)}


def _identity_matches(op: state.Op, cur: os.stat_result) -> bool:
    """Compare a recorded operation identity against a fresh lstat result.

    A missing record (older entries) or a filesystem without inode support
    (st_ino == 0) degrades to type-only checking; mtime/size are checked
    separately for files.
    """
    ident = op.get("ident")
    if not ident:
        return True
    if cur.st_dev != ident["dev"]:
        return False
    if ident["ino"] and cur.st_ino and cur.st_ino != ident["ino"]:
        return False
    return stat.S_IFMT(cur.st_mode) == ident["mode"]


def create_dir(base: Path, name: str) -> Path | None:
    validate_name(name)
    target = resolve_target(base, name)
    if target.is_symlink() or target.exists():
        return None

    target.mkdir()
    mtime, size = _op_stat(target)
    state.history.append(
        {
            "op": "dir",
            "path": target,
            "created": True,
            "mtime": mtime,
            "size": size,
            "ident": _identity(target),
        }
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
        {
            "op": "file",
            "path": target,
            "created": True,
            "mtime": mtime,
            "size": size,
            "ident": _identity(target),
        }
    )
    return target


def undo_last() -> bool:
    """Remove the most recent entry, but only if it is still ours.

    The target must match the recorded identity (device, inode, file type).
    A file must also keep its recorded mtime and size. Anything replaced,
    modified, or substituted with a symlink is left alone and stays in the
    history. A target that vanished on its own is dropped cleanly.
    """
    if not state.history:
        return False

    op = state.history.pop()
    p = op.get("path")
    if p is None:
        return False

    try:
        cur = p.lstat()
    except FileNotFoundError:
        return True  # already gone: nothing to remove, history stays correct
    except OSError:
        state.history.append(op)
        return False

    if not _identity_matches(op, cur):
        state.history.append(op)
        return False

    if stat.S_ISLNK(cur.st_mode):
        # KTrex never creates symlinks, so a symlink here is a replacement.
        state.history.append(op)
        return False

    if stat.S_ISREG(cur.st_mode):
        mtime, size = _op_stat(p)
        if mtime != op.get("mtime", -1) or size != op.get("size", -2):
            state.history.append(op)
            return False
        try:
            p.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            state.history.append(op)
            return False

    if stat.S_ISDIR(cur.st_mode):
        if op.get("op") != "dir":
            state.history.append(op)
            return False
        try:
            if any(p.iterdir()):
                state.history.append(op)
                return False
            p.rmdir()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            state.history.append(op)
            return False

    # Sockets, fifos, devices: KTrex never creates these, never remove them.
    state.history.append(op)
    return False


def remove_created(path: Path) -> bool:
    """Remove a path that KTrex created and recorded, used for rollback.

    Returns False and keeps both the file and its history entry when the
    entry is unknown, was replaced, or can no longer be removed safely.
    """
    op = None
    for i, item in enumerate(state.history):
        if item.get("path") == path:
            op = state.history.pop(i)
            break

    if op is None:
        return False  # never delete anything KTrex did not record

    try:
        cur = path.lstat()
    except FileNotFoundError:
        return True  # already gone
    except OSError:
        state.history.append(op)
        return False

    if not _identity_matches(op, cur):
        state.history.append(op)
        return False

    try:
        if stat.S_ISREG(cur.st_mode):
            mtime, size = _op_stat(path)
            if mtime != op.get("mtime", -1) or size != op.get("size", -2):
                state.history.append(op)
                return False  # content changed after creation: not ours to drop
            path.unlink()
            return True
        if stat.S_ISDIR(cur.st_mode):
            if any(path.iterdir()):
                state.history.append(op)
                return False
            path.rmdir()
            return True
        state.history.append(op)
        return False
    except (FileNotFoundError, OSError):
        state.history.append(op)
        return False
