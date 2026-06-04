from pathlib import Path
from .state import history

def create_dir(base: Path, name: str) -> Path | None:
    if not name:
        return None

    p = base / name
    if p.exists():
        return None

    p.mkdir()
    history.append(p)
    return p


def create_file(base: Path, name: str) -> Path | None:
    if not name:
        return None

    p = base / name
    if p.exists():
        return None

    p.touch()
    history.append(p)
    return p


def undo_last():
    if not history:
        return False

    p = history.pop()

    if p.is_file():
        p.unlink()
        return True

    if p.is_dir():
        # SAFE UNDO: only remove empty dirs
        if any(p.iterdir()):
            history.append(p)  # rollback undo
            return False
        p.rmdir()
        return True

    return False

