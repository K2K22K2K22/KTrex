import pytest

from ktrex import __version__, state
from ktrex.main import main, prepare_root


@pytest.fixture(autouse=True)
def clean_state():
    yield
    state.root_dir = None
    state.path_stack = []
    state.history.clear()


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_list_presets(capsys):
    code = main(["--list-presets"])

    assert code == 0
    assert "ml_project" in capsys.readouterr().out


def test_apply_preset_builds_the_structure(tmp_path, capsys):
    target = tmp_path / "proj"

    code = main(["--apply", "ml_project", str(target)])

    assert code == 0
    assert (target / "src" / "train.py").is_file()
    assert (target / "configs" / "train.yaml").is_file()
    assert (target / "runs").is_dir()
    assert "Applied preset" in capsys.readouterr().out


def test_apply_unknown_preset_fails(tmp_path, capsys):
    code = main(["--apply", "does_not_exist", str(tmp_path / "proj")])

    assert code == 1
    assert "Error" in capsys.readouterr().out


def test_empty_prompt_is_an_error(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "")

    code = main([])

    assert code == 1
    assert "Error" in capsys.readouterr().out


def test_prepare_root_accepts_dot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    root = prepare_root(".")

    assert root == tmp_path.resolve()
    assert state.path_stack == [root]


def test_prepare_root_prompts_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a: "made")

    root = prepare_root(None)

    assert root == (tmp_path / "made").resolve()
    assert root.is_dir()


def test_prepare_root_creates_nested_path(tmp_path):
    root = prepare_root(str(tmp_path / "a" / "b"))

    assert root.is_dir()
