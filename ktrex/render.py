from pathlib import Path

from .tree import MAX_DEPTH


def render_tree(
    root: Path,
    current: Path | None = None,
    prefix: str = "",
    depth: int = 0,
) -> list[str]:
    """Render a directory tree as a list of lines.

    Symlinked directories are shown but not followed, unreadable
    directories render as a single note, and deep trees are cut off.
    """
    lines: list[str] = []
    if depth >= MAX_DEPTH:
        lines.append(f"{prefix}...")
        return lines

    try:
        items = sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except OSError:
        lines.append(f"{prefix}[cannot read]")
        return lines

    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        branch = "└── " if is_last else "├── "
        marker = "  ← current" if current and item == current else ""
        link = " (link)" if item.is_symlink() else ""

        lines.append(f"{prefix}{branch}{item.name}{link}{marker}")

        if item.is_dir() and not item.is_symlink():
            extension = "    " if is_last else "│   "
            lines.extend(
                render_tree(
                    item,
                    current=current,
                    prefix=prefix + extension,
                    depth=depth + 1,
                )
            )

    return lines
