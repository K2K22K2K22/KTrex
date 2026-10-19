"""Read-only file preview with bounded reads.

Kept out of fs.py on purpose: preview never touches the undo history and
never mutates the filesystem.

Symlink policy: preview never follows a symbolic link. Where the platform
supports O_NOFOLLOW the file is opened with it, so the check and the open
are one atomic step. Where it does not, preview lstats the path and compares
the identity of the opened descriptor, refusing on any mismatch. On
filesystems that report st_ino == 0 identity cannot be proven and the lstat
symlink inspection is the only guard. Race-free resolution of symlinked
*parent* directories is out of scope; opening a path inside a swapped
directory can still reach a different file, and identity checks catch it.

Truncation policy: at most PREVIEW_MAX_BYTES are read and at most
PREVIEW_MAX_LINES are kept. When a limit is hit the result is marked
truncated with the reason, and the total line count is reported as unknown,
so a partial count is never presented as the full file.
"""

import errno
import os
import stat
from dataclasses import dataclass, field

PREVIEW_MAX_BYTES = 262144
PREVIEW_MAX_LINES = 2000

_HAS_NOFOLLOW = hasattr(os, "O_NOFOLLOW")


@dataclass
class Preview:
    """Bounded snapshot of a file for display. Immutable intent, cheap copy."""

    name: str
    path: str
    lines: list[str] = field(default_factory=list)
    truncated: bool = False
    reason: str = ""  # "", "byte limit", or "line limit"
    total_known: bool = True
    error: str = ""  # "" when the file was read successfully


def _open_checked(path) -> int:
    """Open path read-only without following a final symlink.

    Returns a file descriptor. Raises OSError when the entry is a symlink
    (ELOOP with O_NOFOLLOW) or when the fallback identity check fails.
    """
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    if _HAS_NOFOLLOW:
        return os.open(path, flags | os.O_NOFOLLOW)

    # Fallback for platforms without O_NOFOLLOW: lstat the entry, open it,
    # then prove the descriptor still points at the inspected entry.
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode):
        raise OSError(errno.ELOOP, "Symbolic link not followed", str(path))
    fd = os.open(path, flags)
    after = os.fstat(fd)
    if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
        os.close(fd)
        raise OSError(errno.EIO, "File changed while opening", str(path))
    return fd


def _read_bounded(fd: int, max_bytes: int) -> bytes:
    """Read at most max_bytes bytes from fd in chunks."""
    chunks: list[bytes] = []
    remaining = max_bytes
    while remaining > 0:
        chunk = os.read(fd, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _error_preview(path, message: str) -> Preview:
    name = getattr(path, "name", str(path))
    return Preview(name=name, path=str(path), error=message)


def read_preview(
    path, max_bytes: int = PREVIEW_MAX_BYTES, max_lines: int = PREVIEW_MAX_LINES
) -> Preview:
    """Build a bounded Preview for path. Never mutates the file."""
    try:
        fd = _open_checked(path)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return _error_preview(path, "Symlink preview is disabled")
        return _error_preview(path, f"Cannot read file: {exc}")

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return _error_preview(path, "Not a regular file: preview not available")
        try:
            data = _read_bounded(fd, max_bytes + 1)
        except OSError as exc:
            return _error_preview(path, f"Cannot read file: {exc}")
    finally:
        os.close(fd)

    name = getattr(path, "name", str(path))
    truncated = len(data) > max_bytes
    reason = "byte limit" if truncated else ""
    data = data[:max_bytes]

    if b"\x00" in data[:8192]:
        return _error_preview(path, "Binary file: preview not available")

    all_lines = data.decode("utf-8", errors="replace").splitlines()
    if len(all_lines) > max_lines:
        truncated = True
        reason = "line limit"
    return Preview(
        name=name,
        path=str(path),
        lines=all_lines[:max_lines],
        truncated=truncated,
        reason=reason,
        total_known=not truncated,
    )
