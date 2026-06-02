from pathlib import Path

# Root directory of the session
root_dir: Path | None = None

# Stack-based navigation (no recursion)
path_stack: list[Path] = []

# Undo stack (only last-created leaf nodes)
history: list[Path] = []

