import json

import pytest

from ktrex.presets import load_preset
from ktrex.tree import InvalidTree


def test_loads_builtin_preset(project):
    load_preset("ml_project", project)

    assert (project / "src" / "train.py").is_file()
    assert (project / "src" / "model.py").is_file()
    assert (project / "runs").is_dir()


def test_loads_preset_from_path(project, tmp_path):
    path = tmp_path / "custom.json"
    path.write_text(
        json.dumps({"name": "c", "type": "dir", "children": [{"name": "app.py", "type": "file"}]})
    )

    load_preset(path, project)

    assert (project / "app.py").is_file()


def test_missing_preset_raises(project):
    with pytest.raises(FileNotFoundError):
        load_preset("does_not_exist", project)


def test_invalid_json_raises(project, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")

    with pytest.raises(ValueError):
        load_preset(path, project)


def test_rejects_traversal_preset(project, tmp_path):
    path = tmp_path / "evil.json"
    path.write_text(
        json.dumps({"name": "e", "type": "dir", "children": [{"name": "../escape", "type": "file"}]})
    )

    with pytest.raises(InvalidTree):
        load_preset(path, project)

    assert not (project.parent / "escape").exists()
