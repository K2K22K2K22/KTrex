import builtins
import curses
import os
from pathlib import Path

import pytest

from ktrex import state
from ktrex.preview import PREVIEW_MAX_BYTES, PREVIEW_MAX_LINES, read_preview
from ktrex.tui import confirm, draw_help, preview_screen, prompt
from test_tui import FakeScreen


def frame_text(frame) -> str:
    return "\n".join(text for _, _, text, _ in frame)


def test_preview_normal_utf8_file(project):
    path = project / "notes.txt"
    path.write_text("héllo wörld\n日本語 line\nthird\n", encoding="utf-8")

    lines, error, truncated = read_preview(path)

    assert error is None
    assert truncated is False
    assert lines == ["héllo wörld", "日本語 line", "third"]

    screen = FakeScreen(10, 60, keys=[27])
    preview_screen(screen, path)
    assert "héllo wörld" in frame_text(screen.frames[0])
    # The header clips long paths instead of wrapping past the edge.
    assert str(path.parent) in frame_text(screen.frames[0])


def test_preview_empty_file(project):
    path = project / "empty.txt"
    path.write_text("")

    lines, error, truncated = read_preview(path)

    assert lines == []
    assert error is None
    assert truncated is False

    screen = FakeScreen(8, 40, keys=[27])
    preview_screen(screen, path)
    assert "(empty file)" in frame_text(screen.frames[0])


def test_preview_binary_file(project):
    path = project / "blob.bin"
    path.write_bytes(b"\x00\x01\x02binary\xff")

    lines, error, truncated = read_preview(path)

    assert lines is None
    assert error is not None and "Binary" in error
    assert truncated is False

    screen = FakeScreen(8, 40, keys=[27])
    preview_screen(screen, path)
    assert "Binary" in frame_text(screen.frames[0])


def test_preview_missing_file(project):
    lines, error, truncated = read_preview(project / "nope.txt")

    assert lines is None
    assert error is not None and "Cannot read file" in error


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_preview_unreadable_file(project):
    path = project / "secret.txt"
    path.write_text("hidden")
    path.chmod(0o000)
    try:
        lines, error, truncated = read_preview(path)
    finally:
        path.chmod(0o644)

    assert lines is None
    assert error is not None and "Cannot read file" in error


def test_preview_large_file_bounded_read(project, monkeypatch):
    """The reader may ask for max_bytes + 1, never the whole file."""

    class FakeFile:
        def __init__(self):
            self.reads = []

        def read(self, n=-1):
            self.reads.append(n)
            return b"a" * (n if n >= 0 else 10_000_000)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    handle = FakeFile()

    def fake_open(*args, **kwargs):
        return handle

    monkeypatch.setattr(builtins, "open", fake_open)

    lines, error, truncated = read_preview(Path("/fake/huge.txt"))

    assert handle.reads == [PREVIEW_MAX_BYTES + 1]
    assert truncated is True
    assert error is None
    assert lines is not None and len(lines) <= PREVIEW_MAX_LINES


def test_preview_truncates_and_flags_position(project):
    path = project / "big.txt"
    path.write_text("\n".join(f"L{i}" for i in range(3000)))

    lines, error, truncated = read_preview(path)

    assert error is None
    assert truncated is True
    assert lines is not None and len(lines) == PREVIEW_MAX_LINES

    screen = FakeScreen(12, 60, keys=[27])
    preview_screen(screen, path)
    footer = "\n".join(text for y, x, text, _ in screen.frames[0] if y == 11)
    assert "/" in footer and "+" in footer


def test_preview_scrolls_forward_and_backward(project):
    path = project / "scroll.txt"
    path.write_text("\n".join(f"L{i}" for i in range(100)))

    screen = FakeScreen(24, 60, keys=[curses.KEY_END, curses.KEY_UP, 27])
    preview_screen(screen, path)

    assert len(screen.frames) == 3
    first = frame_text(screen.frames[0])
    assert "L0" in first  # starts at the top
    at_end = frame_text(screen.frames[1])
    assert "L79" in at_end and "L0\n" not in at_end
    back = frame_text(screen.frames[2])
    assert "L78" in back  # one line back from the end


def test_preview_clips_long_lines(project):
    path = project / "long.txt"
    path.write_text("x" * 500 + "\nshort\n")

    class StrictScreen(FakeScreen):
        def addnstr(self, y, x, text, n, attr=0):
            if x + min(n, len(text)) > self.w:
                raise curses.error("wrote outside the terminal")
            super().addnstr(y, x, text, n, attr)

    screen = StrictScreen(10, 40, keys=[27])
    preview_screen(screen, path)  # must not raise

    assert all(len(text) <= 40 for _, _, text in screen.writes)


def test_preview_esc_returns(project):
    path = project / "f.txt"
    path.write_text("content")

    screen = FakeScreen(10, 40, keys=[27])
    preview_screen(screen, path)

    assert screen.keys == []  # the ESC was consumed, loop exited


def test_help_esc_returns(project):
    screen = FakeScreen(40, 60, keys=[27])
    draw_help(screen)

    assert screen.keys == []
    assert "ESC: Back" in frame_text(screen.frames[0])


def test_prompt_esc_cancels_without_value(project):
    screen = FakeScreen(10, 40, keys=[27])

    assert prompt(screen, "Name: ") == ""
    assert state.history == []


def test_prompt_enter_returns_text(project):
    screen = FakeScreen(10, 40, keys=[ord("a"), ord("b"), 10])

    assert prompt(screen, "Name: ") == "ab"


def test_confirm_esc_cancels(project):
    screen = FakeScreen(10, 40, keys=[27])

    assert confirm(screen, "Quit KTrex?") is False


def test_confirm_y_accepts(project):
    screen = FakeScreen(10, 40, keys=[ord("y")])

    assert confirm(screen, "Quit KTrex?") is True


def test_preview_arrow_keys_not_treated_as_esc(project):
    path = project / "f.txt"
    path.write_text("\n".join(f"L{i}" for i in range(50)))

    screen = FakeScreen(
        24, 60, keys=[curses.KEY_UP, curses.KEY_DOWN, curses.KEY_UP, curses.KEY_UP, 27]
    )
    preview_screen(screen, path)

    # All arrow keys scrolled; only the final ESC exited.
    assert screen.keys == []
    assert len(screen.frames) == 5


def test_preview_survives_resize(project):
    path = project / "f.txt"
    path.write_text("\n".join(f"L{i}" for i in range(50)))

    class ShrinkingScreen(FakeScreen):
        def getch(self):
            key = super().getch()
            self.h, self.w = 12, 40  # window shrinks mid-preview
            return key

    screen = ShrinkingScreen(24, 80, keys=[curses.KEY_DOWN, 27])
    preview_screen(screen, path)  # must not raise

    last = screen.frames[-1]
    assert all(0 <= y < 12 and 0 <= x < 40 for y, x, _, _ in last)


def test_preview_does_not_modify_file_or_history(project):
    path = project / "f.txt"
    path.write_text("stable")
    before = path.read_bytes()
    stamp = path.stat().st_mtime_ns

    screen = FakeScreen(10, 40, keys=[curses.KEY_DOWN, 27])
    preview_screen(screen, path)

    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == stamp
    assert state.history == []


def test_preview_refuses_symlink(project, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("secret")
    link = project / "link.txt"
    link.symlink_to(target)

    lines, error, truncated = read_preview(link)

    assert lines is None
    assert error is not None and "Symlink" in error
