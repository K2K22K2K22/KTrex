from pathlib import Path


def render_tree(
    root: Path,
    current: Path | None = None,
    prefix: str = "",
) -> list[str]:
    """
    Render a directory tree as a list of strings.

    Args:
        root: root directory to render
        current: directory to highlight (optional)
        prefix: internal prefix for recursion

    Returns:
        List of rendered lines
    """
    lines: list[str] = []

    items = sorted(
        root.iterdir(),
        key=lambda x: (x.is_file(), x.name.lower()),
    )

    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        branch = "└── " if is_last else "├── "
        marker = "  ← current" if current and item == current else ""

        lines.append(f"{prefix}{branch}{item.name}{marker}")

        if item.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(
                render_tree(
                    item,
                    current=current,
                    prefix=prefix + extension,
                )
            )

    return lines
