import pytest

from ktrex import state


@pytest.fixture
def project(tmp_path):
    """An isolated project root wired into the module level state."""
    state.root_dir = tmp_path
    state.path_stack = [tmp_path]
    state.history.clear()
    yield tmp_path
    state.root_dir = None
    state.path_stack = []
    state.history.clear()
