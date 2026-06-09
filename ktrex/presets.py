import json
from pathlib import Path

from .tree import apply_tree


def _builtin_preset_path(name: str) -> Path:
    # Resolve a preset bundled inside the KTrex package.

    return Path(__file__).parent / "presets" / f"{name}.json"


def load_preset(preset: str | Path, base: Path):
    # Load a preset by name (builtin) or by explicit file path.

    if isinstance(preset, str):
        path = _builtin_preset_path(preset)
    else:
        path = preset

    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {path}")

    with open(path, "r") as f:
        data = json.load(f)

    apply_tree(base, data)
