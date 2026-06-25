import curses

import pytest

from ktrex.tui import location_label, menu_geometry, put, too_small


class FakeScreen:
    """Minimal stand-in for a curses window, with real edge behaviour."""

    def __init__(self, h: int = 24, w: int = 80):
        self.h = h
        self.w = w
        self.writes: list[tuple[int, int, str]] = []

    def getmaxyx(self):
        return (self.h, self.w)

    def addnstr(self, y, x, text, n, attr=0):
        if y < 0 or y >= self.h or x < 0 or x >= self.w:
            raise curses.error("out of bounds")
        if y == self.h - 1 and x + min(n, len(text)) >= self.w:
            raise curses.error("bottom right corner")
        self.writes.append((y, x, text[:n]))


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
