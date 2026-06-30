from pathlib import Path
from typing import Literal, TypedDict

OpType = Literal["dir", "file"]

class Op(TypedDict, total=False):
    op: OpType
    path: Path
    created: bool
    mtime: float
    size: int

# Root directory of the session
root_dir: Path | None = None

# Stack-based navigation (no recursion)
path_stack: list[Path] = []

# Undo stack of operations (created by KTrex)
history: list[Op] = []

