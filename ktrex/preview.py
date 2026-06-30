"""Read-only file preview with bounded reads.

Kept out of fs.py on purpose: preview never touches the undo history and
never mutates the filesystem.
"""

PREVIEW_MAX_BYTES = 262144
PREVIEW_MAX_LINES = 2000


def read_preview(path, max_bytes: int = PREVIEW_MAX_BYTES, max_lines: int = PREVIEW_MAX_LINES):
    """Return ``(lines, error, truncated)`` for a file.

    Reads at most ``max_bytes`` from disk and keeps at most ``max_lines``
    decoded lines in memory, so a huge file costs the same as a small one.
    Symlinks are never followed.
    """
    try:
        if path.is_symlink():
            return None, "Symlink preview is disabled", False
        with open(path, "rb") as fh:
            data = fh.read(max_bytes + 1)
    except OSError as exc:
        return None, f"Cannot read file: {exc}", False

    truncated = len(data) > max_bytes
    data = data[:max_bytes]

    if b"\x00" in data[:8192]:
        return None, "Binary file: preview not available", False

    all_lines = data.decode("utf-8", errors="replace").splitlines()
    if len(all_lines) > max_lines:
        truncated = True
    return all_lines[:max_lines], None, truncated
