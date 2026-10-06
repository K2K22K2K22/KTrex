"""Read-only file preview with bounded reads.

Kept out of fs.py on purpose: preview never touches the undo history and
never mutates the filesystem.

Symlink policy: preview never follows a symbolic link. Where the platform
supports O_NOFOLLOW the file is opened with it, so the check and the open
are one atomic step. Where it does not, preview lstats the path and compares
the identity of the opened descriptor, refusing on any mismatch. Race-free
resolution of symlinked *parent* directories is out of scope; opening a path
inside a swapped directory can still reach a different file, and identity
checks catch it.
"""

import errno
import os
import stat

PREVIEW_MAX_BYTES = 262144
PREVIEW_MAX_LINES = 2000

_HAS_NOFOLLOW = hasattr(os, "O_NOFOLLOW")


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


def read_preview(path, max_bytes: int = PREVIEW_MAX_BYTES, max_lines: int = PREVIEW_MAX_LINES):
    """Return ``(lines, error, truncated)`` for a file.

    Reads at most ``max_bytes`` from disk and keeps at most ``max_lines``
    decoded lines in memory, so a huge file costs the same as a small one.
    Symlinks are never followed.
    """
    try:
        fd = _open_checked(path)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return None, "Symlink preview is disabled", False
        return None, f"Cannot read file: {exc}", False

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None, "Not a regular file: preview not available", False
        try:
            data = _read_bounded(fd, max_bytes + 1)
        except OSError as exc:
            return None, f"Cannot read file: {exc}", False
    finally:
        os.close(fd)

    truncated = len(data) > max_bytes
    data = data[:max_bytes]

    if b"\x00" in data[:8192]:
        return None, "Binary file: preview not available", False

    all_lines = data.decode("utf-8", errors="replace").splitlines()
    if len(all_lines) > max_lines:
        truncated = True
    return all_lines[:max_lines], None, truncated
