import json
from pathlib import Path

from .tree import apply_tree


def _builtin_preset_path(name: str) -> Path:
    # Resolve a preset bundled inside the KTrex package. The name must be a
    # single segment so it cannot walk out of the presets directory.
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError(f"invalid preset name: {name!r}")
    return Path(__file__).parent / "presets" / f"{name}.json"


def builtin_presets() -> list[str]:
    """Names of the presets shipped inside the KTrex package."""
    folder = Path(__file__).parent / "presets"
    if not folder.is_dir():
        return []
    return sorted(path.stem for path in folder.glob("*.json"))


def load_preset(preset: str | Path, base: Path):
    # Load a preset by name (builtin) or by explicit file path.
    if isinstance(preset, str):
        candidate = Path(preset)
        path = candidate if candidate.is_file() else _builtin_preset_path(preset)
    else:
        path = preset

    if not path.is_file():
        raise FileNotFoundError(f"preset not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path}: {e}") from e

    return apply_tree(base, data)
