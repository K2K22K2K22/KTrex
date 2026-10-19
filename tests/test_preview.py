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

    pv = read_preview(path)

    assert pv.error == ""
    assert pv.truncated is False
    assert pv.total_known is True
    assert pv.lines == ["héllo wörld", "日本語 line", "third"]

    screen = FakeScreen(10, 60, keys=[27])
    preview_screen(screen, path)
    assert "héllo wörld" in frame_text(screen.frames[0])
    # The header clips long paths instead of wrapping past the edge.
    assert str(path.parent) in frame_text(screen.frames[0])


def test_preview_empty_file(project):
    path = project / "empty.txt"
    path.write_text("")

    pv = read_preview(path)

    assert pv.lines == []
    assert pv.error == ""
    assert pv.truncated is False
    assert pv.total_known is True

    screen = FakeScreen(8, 40, keys=[27])
    preview_screen(screen, path)
    assert "(empty file)" in frame_text(screen.frames[0])


def test_preview_binary_file(project):
    path = project / "blob.bin"
    path.write_bytes(b"\x00\x01\x02binary\xff")

    pv = read_preview(path)

    assert pv.lines == []
    assert "Binary" in pv.error
    assert pv.truncated is False

    screen = FakeScreen(8, 40, keys=[27])
    preview_screen(screen, path)
    assert "Binary" in frame_text(screen.frames[0])


def test_preview_missing_file(project):
    pv = read_preview(project / "nope.txt")

    assert pv.lines == []
    assert "Cannot read file" in pv.error


@pytest.mark.skipif(getattr(os, "geteuid", lambda: -1)() == 0, reason="root ignores file permissions")
def test_preview_unreadable_file(project):
    path = project / "secret.txt"
    path.write_text("hidden")
    path.chmod(0o000)
    try:
        pv = read_preview(path)
    finally:
        path.chmod(0o644)

    assert pv.lines == []
    assert "Cannot read file" in pv.error


def test_preview_large_file_bounded_read(project, monkeypatch):
    """Reads are chunked and stop at max_bytes + 1, never the whole file."""
    path = project / "huge.txt"
    with path.open("wb") as fh:
        fh.write(b"a" * (PREVIEW_MAX_BYTES + 5_000_000))

    sizes = []
    real_read = os.read

    def spy_read(fd, n):
        sizes.append(n)
        return real_read(fd, n)

    monkeypatch.setattr("ktrex.preview.os.read", spy_read)

    pv = read_preview(path)

    assert pv.error == ""
    assert pv.truncated is True
    assert pv.total_known is False
    assert len(pv.lines) <= PREVIEW_MAX_LINES
    assert sizes and max(sizes) <= 65536  # chunked, never one giant request
    assert sum(sizes) == PREVIEW_MAX_BYTES + 1  # exactly the bounded window


def test_preview_truncates_and_flags_position(project):
    path = project / "big.txt"
    path.write_text("\n".join(f"L{i}" for i in range(3000)))

    pv = read_preview(path)

    assert pv.error == ""
    assert pv.truncated is True
    assert pv.reason == "line limit"
    assert len(pv.lines) == PREVIEW_MAX_LINES

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

    assert prompt(screen, "Name: ") is None
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

    pv = read_preview(link)

    assert pv.lines == []
    assert "Symlink" in pv.error


# --- race hardening -----------------------------------------------------------

import errno


def test_preview_refuses_symlink_to_directory(project, tmp_path):
    outside = tmp_path / "dir"
    outside.mkdir()
    link = project / "ldir"
    link.symlink_to(outside)

    pv = read_preview(link)

    assert pv.lines == []
    assert "Symlink" in pv.error


def test_preview_refuses_a_real_directory(project):
    pv = read_preview(project)

    assert pv.lines == []
    assert "regular file" in pv.error


def test_preview_rejects_identity_mismatch_in_fallback(project, monkeypatch, tmp_path):
    """Without O_NOFOLLOW, a swap between lstat and open must be caught."""
    path = project / "swap.txt"
    path.write_text("harmless")
    monkeypatch.setattr("ktrex.preview._HAS_NOFOLLOW", False)

    real_fstat = os.fstat
    real_lstat = os.lstat
    opened = {}

    def fake_lstat(p):
        st = real_lstat(p)
        opened["before"] = (st.st_dev, st.st_ino)
        return st

    def fake_fstat(fd):
        st = real_fstat(fd)
        # Simulate the entry being replaced: same file, forged identity.
        class Shifted:
            st_mode = st.st_mode
            st_dev = st.st_dev
            st_ino = st.st_ino + 1

        return Shifted()

    monkeypatch.setattr("ktrex.preview.os.lstat", fake_lstat)
    monkeypatch.setattr("ktrex.preview.os.fstat", fake_fstat)

    pv = read_preview(path)

    assert pv.lines == []
    assert "changed" in pv.error.lower()


def test_preview_descriptor_closed_on_all_paths(project, monkeypatch):
    path = project / "closed.txt"
    path.write_text("data")
    closed = []
    real_close = os.close

    def spy_close(fd):
        closed.append(fd)
        return real_close(fd)

    monkeypatch.setattr("ktrex.preview.os.close", spy_close)

    read_preview(path)  # success path
    read_preview(project)  # directory path (not a regular file)
    read_preview(project / "missing.txt")  # error path

    assert len(closed) >= 2  # success and directory paths closed their fd


def test_preview_never_creates_history_or_writes(project):
    path = project / "watched.txt"
    path.write_text("stable")
    before = path.read_bytes()
    stamp = path.stat().st_mtime_ns

    read_preview(path)
    read_preview(project / "missing.txt")
    read_preview(project)

    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == stamp
    assert state.history == []


def test_preview_invalid_utf8_is_replaced_safely(project):
    path = project / "bad.txt"
    path.write_bytes(b"ok\xff\xfeend")

    pv = read_preview(path)

    assert pv.error == ""
    assert any("\ufffd" in line for line in pv.lines)


# --- limits, accuracy and line-ending behavior --------------------------------

from ktrex.preview import Preview


def test_byte_limit_truncation_with_few_long_lines(project):
    path = project / "few.txt"
    path.write_text("x" * 4000 + "\n" + "y" * 4000)

    pv = read_preview(path, max_bytes=1000, max_lines=2000)

    assert pv.error == ""
    assert pv.truncated is True
    assert pv.reason == "byte limit"
    assert pv.total_known is False


def test_both_limits_reached_reports_byte_limit(project):
    path = project / "both.txt"
    path.write_text("\n".join("x" * 200 for _ in range(500)))

    pv = read_preview(path, max_bytes=1000, max_lines=10)

    assert pv.truncated is True
    assert pv.reason == "byte limit"  # the byte window cut first
    assert len(pv.lines) == 5  # 5 x 200 bytes fill the 1000-byte window


def test_single_line_larger_than_the_whole_limit(project):
    path = project / "one-line.txt"
    path.write_text("z" * 10_000)

    pv = read_preview(path, max_bytes=1000, max_lines=2000)

    assert pv.truncated is True
    assert pv.reason == "byte limit"
    assert pv.total_known is False
    assert pv.lines and pv.lines[0].startswith("z")


def test_final_line_without_newline_is_kept(project):
    path = project / "tail.txt"
    path.write_text("first\nsecond")

    pv = read_preview(path)

    assert pv.error == ""
    assert pv.lines == ["first", "second"]
    assert pv.total_known is True


def test_crlf_files_split_cleanly(project):
    path = project / "crlf.txt"
    path.write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")

    pv = read_preview(path)

    assert pv.lines == ["alpha", "beta", "gamma"]


def test_footer_reports_unknown_total_with_reason(project):
    path = project / "big.txt"
    path.write_text("\n".join(f"L{i}" for i in range(3000)))

    screen = FakeScreen(12, 70, keys=[27])
    preview_screen(screen, path)

    footer = "\n".join(text for y, x, text, _ in screen.frames[0] if y == 11)
    assert "/2000+ (line limit)" in footer
    assert "/3000" not in footer  # partial count never shown as the total


def test_footer_reports_complete_total_when_known(project):
    path = project / "small.txt"
    path.write_text("a\nb\nc\n")

    screen = FakeScreen(12, 70, keys=[27])
    preview_screen(screen, path)

    footer = "\n".join(text for y, x, text, _ in screen.frames[0] if y == 11)
    assert "lines 1-3/3" in footer


def test_scrolling_works_when_truncated(project):
    path = project / "many.txt"
    path.write_text("\n".join(f"L{i}" for i in range(3000)))

    screen = FakeScreen(12, 40, keys=[curses.KEY_END, curses.KEY_UP, 27])
    preview_screen(screen, path)

    last = frame_text(screen.frames[-1])
    assert "L1999" in last or "L199" in last  # scrolled within retained lines


def test_preview_model_defaults(project):
    pv = Preview(name="f.txt", path="/tmp/f.txt")

    assert pv.lines == []
    assert pv.truncated is False
    assert pv.reason == ""
    assert pv.total_known is True
    assert pv.error == ""
