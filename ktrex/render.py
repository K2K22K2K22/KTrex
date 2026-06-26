from dataclasses import dataclass
from pathlib import Path

from .tree import MAX_DEPTH


@dataclass
class Row:
    path: Path
    prefix: str
    name: str
    is_dir: bool
    is_link: bool
    expanded: bool


def collect_rows(root: Path, expanded: set[Path] | None = None, prefix: str = "", depth: int = 0) -> list[Row]:
    """Flatten a directory tree into rows for display and navigation.

    A directory is descended into when it is listed in ``expanded``; when
    ``expanded`` is None every directory is expanded. Symlinked directories
    are listed but never followed, unreadable ones become a note, and depth
    is capped.
    """
    rows: list[Row] = []
    if depth >= MAX_DEPTH:
        return rows

    try:
        items = sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except OSError:
        rows.append(Row(root, prefix, "[cannot read]", False, False, False))
        return rows

    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        branch = "└── " if is_last else "├── "
        is_dir = item.is_dir() and not item.is_symlink()
        is_link = item.is_symlink()
        is_open = is_dir and (expanded is None or item in expanded)

        rows.append(Row(item, prefix + branch, item.name, is_dir, is_link, is_open))

        if is_open:
            extension = "    " if is_last else "│   "
            rows.extend(collect_rows(item, expanded, prefix + extension, depth + 1))

    return rows


def format_row(row: Row, current: Path | None = None) -> str:
    marker = "  ← current" if current is not None and row.path == current else ""
    link = " (link)" if row.is_link else ""
    arrow = ""
    if row.is_dir:
        arrow = "[-] " if row.expanded else "[+] "
    return f"{row.prefix}{arrow}{row.name}{link}{marker}"


def format_rows(rows: list[Row], current: Path | None = None) -> list[str]:
    return [format_row(row, current) for row in rows]


def render_tree(root: Path, current: Path | None = None, expanded: set[Path] | None = None) -> list[str]:
    """Render a tree as plain lines. Kept as a convenience over the row model."""
    return format_rows(collect_rows(root, expanded), current)
