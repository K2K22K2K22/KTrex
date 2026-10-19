import curses

import pytest

from ktrex.render import collect_rows
from ktrex.tui import (
    clamp_viewport,
    find_row,
    location_label,
    menu_geometry,
    put,
    stack_for,
    too_small,
)


class FakeScreen:
    """Minimal stand-in for a curses window, with real edge behaviour.

    ``frames`` records one list per ``clear()`` (one TUI frame), each entry
    ``(y, x, text, attr)``. ``keys`` feeds ``getch()``; an empty queue
    returns ESC so loops terminate instead of hanging tests.
    """

    def __init__(self, h: int = 24, w: int = 80, keys: list[int] | None = None):
        self.h = h
        self.w = w
        self.writes: list[tuple[int, int, str]] = []
        self.frames: list[list[tuple[int, int, str, int]]] = []
        self.keys: list[int] = list(keys or [])
        self._frame = None

    def getmaxyx(self):
        return (self.h, self.w)

    def addnstr(self, y, x, text, n, attr=0):
        if y < 0 or y >= self.h or x < 0 or x >= self.w:
            raise curses.error("out of bounds")
        if y == self.h - 1 and x + min(n, len(text)) >= self.w:
            raise curses.error("bottom right corner")
        chunk = text[:n]
        self.writes.append((y, x, chunk))
        if self._frame is not None:
            self._frame.append((y, x, chunk, attr))

    def clear(self):
        self._frame = []
        self.frames.append(self._frame)

    def refresh(self):
        pass

    def move(self, y, x):
        pass

    def keypad(self, value):
        pass

    def getch(self):
        return self.keys.pop(0) if self.keys else 27


def test_put_writes_inside(project):
    screen = FakeScreen(10, 20)

    put(screen, 3, 2, "hello", width=10)

    assert screen.writes == [(3, 2, "hello")]


def test_put_truncates_to_width(project):
    screen = FakeScreen(10, 20)

    put(screen, 3, 0, "abcdef", width=4)

    assert screen.writes == [(3, 0, "abcd")]


@pytest.mark.parametrize("y,x", [(-1, 0), (0, -1), (10, 0), (0, 20), (99, 99)])
def test_put_ignores_out_of_bounds(project, y, x):
    screen = FakeScreen(10, 20)

    put(screen, y, x, "text")

    assert screen.writes == []


def test_put_never_reaches_bottom_right_corner(project):
    screen = FakeScreen(10, 20)

    put(screen, 9, 0, "x" * 40)

    # One column is kept free, so curses never raises on the last cell.
    assert screen.writes == [(9, 0, "x" * 19)]


def test_put_on_last_row_with_room(project):
    screen = FakeScreen(10, 20)

    put(screen, 9, 0, "ok", width=4)

    assert screen.writes == [(9, 0, "ok")]


@pytest.mark.parametrize(
    "w,expected_x,expected_width",
    [(80, 56, 24), (20, 10, 10), (200, 176, 24), (60, 40, 20)],
)
def test_menu_geometry(project, w, expected_x, expected_width):
    x, width = menu_geometry(24, w)

    assert (x, width) == (expected_x, expected_width)


def test_too_small():
    assert too_small(5, 80) is True
    assert too_small(24, 27) is True
    assert too_small(24, 28) is False
    assert too_small(6, 28) is False


def test_location_label(project):
    assert location_label(project, project) == "."
    assert location_label(project, project / "src") == "src"
    assert location_label(project / "other", project) == str(project)


def test_stack_for_builds_path_from_root(project):
    (project / "a" / "b").mkdir(parents=True)

    stack = stack_for(project, project / "a" / "b")

    assert stack == [project, project / "a", project / "a" / "b"]


def test_stack_for_root_is_single(project):
    assert stack_for(project, project) == [project]


def test_find_row(project):
    (project / "a").mkdir()
    (project / "b").mkdir()
    rows = collect_rows(project, expanded=set())

    assert find_row(rows, project / "b") == 1
    assert find_row(rows, project / "missing") is None


def test_clamp_viewport():
    assert clamp_viewport(0, 0, 0, 10) == 0
    assert clamp_viewport(0, 0, 5, 10) == 0
    assert clamp_viewport(12, 0, 20, 5) == 8  # cursor pulls the view down
    assert clamp_viewport(0, 50, 20, 5) == 0  # top is clamped to the last page
    assert clamp_viewport(2, 10, 20, 5) == 2  # cursor above the top page


def frame_text(frame) -> str:
    return "\n".join(text for _, _, text, _ in frame)


def reverse_rows(frame) -> list[int]:
    return [y for y, x, _, attr in frame if x == 0 and attr == curses.A_REVERSE]


def run_tui(monkeypatch, screen, escdelay_sink):
    monkeypatch.setattr(curses, "curs_set", lambda *a: None)
    monkeypatch.setattr(curses, "mousemask", lambda *a: (0, 0))
    monkeypatch.setattr(curses, "set_escdelay", lambda v: escdelay_sink.append(v))
    from ktrex.tui import tui_main

    tui_main(screen)


def test_main_screen_esc_does_not_quit_and_preview_keeps_selection(project, monkeypatch):
    (project / "docs").mkdir()
    (project / "readme.txt").write_text("hello preview")
    escdelay = []
    screen = FakeScreen(
        24,
        80,
        keys=[
            27,                    # ESC on main screen: must not exit
            curses.KEY_DOWN,        # cursor moves to readme.txt
            ord("v"),               # preview the file
            27,                    # back from preview
            9,                     # focus menu
            *[curses.KEY_DOWN] * 8,  # walk to Quit
            10,                    # Enter on Quit
            ord("y"),              # confirm
        ],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []  # every key was consumed, then quit confirmed
    assert escdelay == [25]

    # Main-screen ESC explained how to quit instead of exiting.
    assert "Press q from the menu to quit" in frame_text(screen.frames[1])

    # Frame 3 is the preview: filename, path and content are on screen.
    preview = frame_text(screen.frames[3])
    assert "readme.txt" in preview
    assert "hello preview" in preview

    # Selection before the preview and after returning is identical.
    assert reverse_rows(screen.frames[2]) == [2]
    assert reverse_rows(screen.frames[4]) == [2]

    # The confirmation dialog appeared and was accepted.
    assert "Quit KTrex? [y/N]" in frame_text(screen.frames[13])


def test_menu_help_returns_with_esc(project, monkeypatch):
    (project / "docs").mkdir()
    escdelay = []
    # Help sits at index 7, Quit at 8: one step down after returning.
    screen = FakeScreen(
        24,
        80,
        keys=[
            9,                     # focus menu
            *[curses.KEY_DOWN] * 7,  # Help
            10,                    # open Help
            27,                    # ESC returns from Help
            curses.KEY_DOWN,       # Quit
            10,
            ord("y"),
        ],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    texts = [frame_text(f) for f in screen.frames]
    assert any("Interactive Directory Builder" in t for t in texts)


def test_prompt_esc_via_menu_creates_nothing(project, monkeypatch):
    escdelay = []
    before = sorted(p.name for p in project.iterdir())
    screen = FakeScreen(
        24,
        80,
        keys=[
            9,                     # focus menu
            10,                    # Create Directory
            27,                    # ESC cancels the prompt
            *[curses.KEY_DOWN] * 8,
            10,
            ord("y"),
        ],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    assert sorted(p.name for p in project.iterdir()) == before
    from ktrex import state

    assert state.history == []


def test_function_keys_do_not_exit_or_act_as_esc(project, monkeypatch):
    (project / "f.txt").write_text("x")
    escdelay = []
    # A function key on the main screen must be inert; arrows still navigate.
    screen = FakeScreen(
        24,
        80,
        keys=[
            curses.KEY_F1,
            curses.KEY_DOWN,  # cursor -> f.txt
            ord("v"),
            curses.KEY_F1,    # inert inside preview
            27,               # back from preview
            9,
            *[curses.KEY_DOWN] * 8,
            10,
            ord("y"),
        ],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    texts = [frame_text(f) for f in screen.frames]
    assert any("Press q from the menu to quit" not in t for t in texts[:1])


def test_resize_during_main_screen_keeps_state_valid(project, monkeypatch):
    (project / "f.txt").write_text("x")
    escdelay = []

    class ShrinkingScreen(FakeScreen):
        def getch(self):
            key = super().getch()
            self.h, self.w = 12, 60
            return key

    screen = ShrinkingScreen(
        24,
        80,
        keys=[curses.KEY_DOWN, 27, 9, *[curses.KEY_DOWN] * 8, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    last = screen.frames[-1]
    assert all(0 <= y < 12 and 0 <= x < 60 for y, x, _, _ in last)


def test_esc_then_arrow_keys_still_navigate(project, monkeypatch):
    (project / "a.txt").write_text("x")
    (project / "b.txt").write_text("y")
    escdelay = []
    # ESC on the main screen shows a message; the next arrows move the cursor.
    screen = FakeScreen(
        24,
        80,
        keys=[27, curses.KEY_DOWN, 27, 9, *[curses.KEY_DOWN] * 8, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    # frame 2 is the draw after the first arrow: cursor on row y=2
    assert reverse_rows(screen.frames[2]) == [2]


def test_missing_curses_reports_a_useful_error(project, monkeypatch, capsys):
    import ktrex.main as main_mod

    monkeypatch.setattr(main_mod, "curses", None)

    assert main_mod.main([]) == 1
    out = capsys.readouterr().out
    assert "curses" in out


def test_menu_offset_keeps_selection_visible():
    from ktrex.tui import MENU_ITEMS, menu_offset

    # 9 items, 4 visible: walking down drags the window along.
    assert menu_offset(0, 0, 4) == 0
    assert menu_offset(3, 0, 4) == 0
    assert menu_offset(4, 0, 4) == 1
    assert menu_offset(8, 1, 4) == 5
    # Walking back up pulls it back.
    assert menu_offset(4, 5, 4) == 4
    assert menu_offset(0, 4, 4) == 0
    # Degenerate terminals.
    assert menu_offset(8, 0, 0) == 0
    assert menu_offset(3, 0, len(MENU_ITEMS)) == 0


def test_selected_menu_item_visible_on_short_terminal(project, monkeypatch):
    (project / "f.txt").write_text("x")
    escdelay = []
    # 10 rows -> 8 visible menu slots; walk to Quit (index 8) and run it.
    screen = FakeScreen(
        10,
        60,
        keys=[9, *[curses.KEY_DOWN] * 8, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    # The last frame before quit must show Quit highlighted on screen.
    quit_rows = [
        (y, x) for f in screen.frames for y, x, text, attr in f
        if text == "Quit" and attr == curses.A_REVERSE
    ]
    assert quit_rows, "Quit was selected while completely invisible"


def test_empty_project_renders(project, monkeypatch):
    escdelay = []
    screen = FakeScreen(24, 80, keys=[27, 9, *[curses.KEY_DOWN] * 8, 10, ord("y")])

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    assert any("Actions" in frame_text(f) for f in screen.frames)


def test_unicode_and_long_filenames_render_safely(project, monkeypatch):
    (project / "日本語ディレクトリ").mkdir()
    (project / "日本語ディレクトリ" / "файл.txt").write_text("x")
    (project / ("l" * 120 + ".txt")).write_text("x")
    escdelay = []
    screen = FakeScreen(24, 80, keys=[27, 9, *[curses.KEY_DOWN] * 8, 10, ord("y")])

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    last = screen.frames[-1]
    assert all(0 <= x < 80 for _, x, _, _ in last)
    assert all(0 <= y < 24 for y, _, _, _ in last)
    texts = "\n".join(frame_text(f) for f in screen.frames)
    assert "日本語ディレクトリ" in texts


def test_menu_page_keys_move_selection(project, monkeypatch):
    (project / "f.txt").write_text("x")
    escdelay = []
    # PPAGE from 0 clamps at 0, NPAGE jumps 22 -> clamps at Quit (8), run it.
    screen = FakeScreen(
        24,
        80,
        keys=[9, curses.KEY_PPAGE, curses.KEY_NPAGE, 10, ord("y")],
    )

    run_tui(monkeypatch, screen, escdelay)

    assert screen.keys == []
    assert any("Quit KTrex? [y/N]" in frame_text(f) for f in screen.frames)


# --- Windows compatibility ----------------------------------------------------

from ktrex.tui import handle_mouse, tui_main


def test_handle_mouse_scrolls_with_the_wheel(project, monkeypatch):
    monkeypatch.setattr(
        curses, "getmouse", lambda: (0, 0, 0, 0, curses.BUTTON4_PRESSED)
    )
    assert handle_mouse(None, 7) == 4

    monkeypatch.setattr(
        curses, "getmouse", lambda: (0, 0, 0, 0, curses.BUTTON5_PRESSED)
    )
    assert handle_mouse(None, 7) == 10


def test_handle_mouse_survives_missing_wheel_constants(project, monkeypatch):
    for name in ("BUTTON4_PRESSED", "BUTTON4_RELEASED", "BUTTON5_PRESSED", "BUTTON5_RELEASED"):
        monkeypatch.delattr(curses, name, raising=False)
    monkeypatch.setattr(curses, "getmouse", lambda: (0, 0, 0, 0, 0x80000))

    # The wheel is gone, but the viewport must not crash or jump.
    assert handle_mouse(None, 7) == 7


def test_handle_mouse_ignores_getmouse_failure(project, monkeypatch):
    def boom():
        raise curses.error("no mouse")

    monkeypatch.setattr(curses, "getmouse", boom)

    assert handle_mouse(None, 3) == 3


def test_tui_runs_when_optional_terminal_features_are_unavailable(project, monkeypatch):
    (project / "f.txt").write_text("x")

    def unavailable(*a):
        raise curses.error("unsupported")

    monkeypatch.setattr(curses, "curs_set", unavailable)
    monkeypatch.setattr(curses, "mousemask", unavailable)
    monkeypatch.setattr(curses, "set_escdelay", unavailable)
    monkeypatch.setattr("ktrex.tui._KEY_MOUSE", None)

    screen = FakeScreen(24, 80, keys=[27, 9, *[curses.KEY_DOWN] * 8, 10, ord("y")])
    tui_main(screen)

    assert screen.keys == []
