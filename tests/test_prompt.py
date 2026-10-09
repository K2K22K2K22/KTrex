import curses

from ktrex import state
from ktrex.tui import prompt
from test_tui import FakeScreen, frame_text, run_tui


def test_backspace_on_empty_prompt_does_not_crash(project):
    screen = FakeScreen(10, 40, keys=[127, 10])

    assert prompt(screen, "Name: ") == ""


def test_backspace_on_one_character_prompt(project):
    screen = FakeScreen(10, 40, keys=[ord("a"), 127, 10])

    assert prompt(screen, "Name: ") == ""


def test_backspace_on_longer_prompt(project):
    screen = FakeScreen(10, 40, keys=[ord("a"), ord("b"), ord("c"), 127, 10])

    assert prompt(screen, "Name: ") == "ab"


def test_repeated_backspace_until_empty(project):
    keys = [ord("a"), ord("b"), 127, 127, 127, 127, 127, 10]

    screen = FakeScreen(10, 40, keys=keys)

    assert prompt(screen, "Name: ") == ""


def test_esc_cancellation_returns_none(project):
    screen = FakeScreen(10, 40, keys=[ord("a"), 27])

    assert prompt(screen, "Name: ") is None


def test_enter_with_empty_input_returns_empty_string(project):
    screen = FakeScreen(10, 40, keys=[10])

    assert prompt(screen, "Name: ") == ""


def test_unicode_input_and_deletion(project):
    # 'é' arrives as the two UTF-8 bytes C3 A9.
    screen = FakeScreen(10, 40, keys=[0xC3, 0xA9, ord("x"), 127, 10])

    assert prompt(screen, "Name: ") == "é"


def test_backspace_on_partial_utf8_sequence_drops_the_byte(project):
    screen = FakeScreen(10, 40, keys=[0xC3, 127, ord("a"), 10])

    assert prompt(screen, "Name: ") == "a"


def test_input_longer_than_available_width_is_capped(project):
    screen = FakeScreen(10, 40, keys=[ord("a")] * 40 + [10])

    value = prompt(screen, "Name: ")

    assert value is not None and len(value) == 32  # 40 - len("Name: ") - 2


def test_rendered_prompt_never_writes_outside_the_terminal(project):
    class StrictScreen(FakeScreen):
        def addnstr(self, y, x, text, n, attr=0):
            if x + min(n, len(text)) > self.w:
                raise curses.error("wrote outside the terminal")
            super().addnstr(y, x, text, n, attr)

    screen = StrictScreen(10, 20, keys=[ord("x")] * 40 + [10])

    prompt(screen, "Directory name: ")  # must not raise


def test_menu_cancelled_file_creation_leaves_state_untouched(project, monkeypatch):
    escdelay = []
    screen = FakeScreen(
        24,
        80,
        keys=[9, curses.KEY_DOWN, 10, 27, *[curses.KEY_DOWN] * 7, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert list(project.iterdir()) == []
    assert state.history == []
    assert any("Cancelled" in frame_text(f) for f in screen.frames)


def test_menu_cancelled_directory_creation_leaves_state_untouched(project, monkeypatch):
    escdelay = []
    screen = FakeScreen(
        24,
        80,
        keys=[9, 10, 27, *[curses.KEY_DOWN] * 8, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert list(project.iterdir()) == []
    assert state.history == []


def test_menu_cancelled_preset_application_leaves_state_untouched(project, monkeypatch):
    escdelay = []
    screen = FakeScreen(
        24,
        80,
        keys=[
            9,
            *[curses.KEY_DOWN] * 3,  # Load Preset
            10,
            27,  # cancel
            *[curses.KEY_DOWN] * 5,  # Quit
            10,
            ord("y"),
        ],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert list(project.iterdir()) == []
    assert state.history == []


def test_prompt_ignores_arrow_and_function_keys(project):
    keys = [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_F1, ord("a"), 10]

    screen = FakeScreen(10, 40, keys=keys)

    assert prompt(screen, "Name: ") == "a"
    assert screen.keys == []
