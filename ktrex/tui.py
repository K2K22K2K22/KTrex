import curses
import json
import sys
from pathlib import Path

from . import state
from .fs import InvalidName, create_dir, create_file, undo_last
from .presets import load_preset
from .preview import read_preview
from .render import collect_rows, format_row
from .tree import apply_tree, build_tree

# PDCurses (windows-curses) returns Unicode code points from getch, while
# ncurses returns the bytes of a UTF-8 sequence; prompts must feed both.
_PDCURSES = sys.platform == "win32"
_KEY_CODES = frozenset(getattr(curses, name) for name in dir(curses) if name.startswith("KEY_"))
_KEY_MOUSE = getattr(curses, "KEY_MOUSE", None)

MENU_ITEMS = [
    "Create Directory",
    "Create File",
    "Undo",
    "Load Preset",
    "Save Structure",
    "Load Structure",
    "Go Back",
    "Help",
    "Quit",
]

HELP_TEXT = [
    "KTrex - Interactive Directory Builder",
    "",
    "Tree view:",
    "  Up / Down    Move the cursor",
    "  Right / Space  Expand a folder",
    "  Left / Backspace  Collapse or go to parent",
    "  Enter        Enter the folder (files are read-only here)",
    "  v            Preview the selected file",
    "  PageUp / PageDown  Move a page",
    "  Home / End   Jump to top or bottom",
    "",
    "Preview:",
    "  Up / Down / PageUp / PageDown / Home / End  Scroll",
    "  ESC or q     Close the preview, back to the tree",
    "",
    "Menu:",
    "  Tab          Switch focus between tree and menu",
    "  Enter        Run the highlighted action",
    "  ESC          Cancel a prompt or confirmation",
    "  ESC          On the main screen: show how to quit",
    "  q            Quit is a menu action (with confirmation)",
    "",
    "Actions:",
    "  Create Directory  - Create and enter a new folder",
    "  Create File       - Create a file in current directory",
    "  Undo              - Revert last create action (safe)",
    "  Load Preset       - Apply a preset by name or file path",
    "  Save Structure    - Save project structure to JSON",
    "  Load Structure    - Load structure from JSON",
    "  Go Back           - Move to parent directory",
    "",
    "Notes:",
    "  - KTrex never deletes non-empty directories",
    "  - Existing files are never overwritten",
    "  - Undo refuses replaced or modified entries and symlinks",
    "    swapped in for what KTrex created",
    "  - Preview reads at most 256 KiB and 2000 lines; the footer",
    "    marks truncated files with the reason",
    "  - Presets are additive",
    "",
    "Press any key to return",
]

MENU_WIDTH = 24
MIN_HEIGHT = 6
MIN_WIDTH = 28


def sanitize(text: str) -> str:
    """Replace control characters so a hostile name cannot inject escapes."""
    return "".join("?" if ord(ch) < 32 or ord(ch) == 127 else ch for ch in text)


def put(stdscr, y: int, x: int, text: str, attr: int = 0, width: int | None = None):
    """Write text without ever raising on the screen edge."""
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    room = w - x - 1 if width is None else min(width, w - x - 1)
    if room <= 0:
        return
    try:
        stdscr.addnstr(y, x, sanitize(text), room, attr)
    except curses.error:
        pass


def menu_geometry(h: int, w: int) -> tuple[int, int]:
    width = min(MENU_WIDTH, max(10, w // 3))
    return max(0, w - width), width


def too_small(h: int, w: int) -> bool:
    return h < MIN_HEIGHT or w < MIN_WIDTH


def draw_too_small(stdscr):
    stdscr.clear()
    put(stdscr, 0, 0, "KTrex: terminal too small")
    stdscr.refresh()


def draw_tree(stdscr, root: Path, rows, current: Path, cursor: int, top: int, tree_width: int, focus: str):
    put(stdscr, 0, 0, root.name, curses.A_BOLD, width=tree_width)

    visible = stdscr.getmaxyx()[0] - 2
    for i, row in enumerate(rows[top:top + visible]):
        index = top + i
        attr = curses.A_REVERSE if focus == "tree" and index == cursor else curses.A_NORMAL
        put(stdscr, 1 + i, 0, format_row(row, current), attr, width=tree_width)


def menu_offset(selected: int, offset: int, visible: int) -> int:
    """Scroll offset keeping the selected menu item on screen."""
    if visible <= 0:
        return 0
    if selected < offset:
        return selected
    if selected >= offset + visible:
        return selected - visible + 1
    return max(0, min(offset, len(MENU_ITEMS) - visible))


def draw_menu(stdscr, selected: int, focus: str, menu_x: int, menu_width: int, offset: int = 0):
    put(stdscr, 0, menu_x, "Actions", curses.A_BOLD, width=menu_width)
    h = stdscr.getmaxyx()[0]
    visible = max(1, h - 2)
    for row, i in enumerate(range(offset, min(offset + visible, len(MENU_ITEMS)))):
        attr = curses.A_REVERSE if focus == "menu" and i == selected else curses.A_NORMAL
        put(stdscr, 1 + row, menu_x, MENU_ITEMS[i], attr, width=menu_width)


def draw_status(stdscr, message: str, location: str, scroll_info: str):
    h, w = stdscr.getmaxyx()
    label = message or location
    tail = max(0, w - len(scroll_info) - 2) if scroll_info else w
    put(stdscr, h - 1, 0, label, curses.A_DIM, width=tail)
    if scroll_info:
        put(stdscr, h - 1, max(0, w - len(scroll_info) - 1), scroll_info, curses.A_DIM)


def draw_help(stdscr):
    """Modal help screen. Any key, including ESC, returns to the caller."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    for i, line in enumerate(HELP_TEXT):
        if i + 1 >= h - 1:
            break
        put(stdscr, i + 1, 2, line, width=w - 4)
    footer = "ESC: Back"
    put(stdscr, h - 1, max(0, w - len(footer) - 2), footer, curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()


def confirm(stdscr, message: str) -> bool:
    """Modal yes/no prompt. ESC or any key other than y/Y cancels."""
    h, w = stdscr.getmaxyx()
    y = h - 2
    if y < 0:
        return False
    put(stdscr, y, 0, f"{message} [y/N]", width=w - 1)
    stdscr.refresh()
    return stdscr.getch() in (ord("y"), ord("Y"))


def preview_screen(stdscr, path: Path):
    """Read-only file preview modal. ESC or q returns to the caller.

    Bounded read: only the first PREVIEW_MAX_BYTES are loaded and only
    PREVIEW_MAX_LINES are kept, so a huge file costs a fixed amount of
    memory and scrolling never rescans the file. When a limit was hit the
    footer says so and the total line count shows as unknown.
    """
    pv = read_preview(path)
    total = len(pv.lines)
    top = 0

    while True:
        h, w = stdscr.getmaxyx()
        if too_small(h, w):
            draw_too_small(stdscr)
            if stdscr.getch() in (ord("q"), 27):
                return
            continue

        stdscr.clear()
        put(stdscr, 0, 0, pv.name, curses.A_BOLD, width=w - 1)
        put(stdscr, 1, 0, pv.path, curses.A_DIM, width=w - 1)

        visible = max(1, h - 3)
        if pv.error:
            put(stdscr, 2, 2, pv.error, width=w - 4)
        elif total == 0:
            put(stdscr, 2, 2, "(empty file)", width=w - 4)
        else:
            top = max(0, min(top, max(0, total - visible)))
            for i, line in enumerate(pv.lines[top:top + visible]):
                put(stdscr, 2 + i, 0, line, width=w - 1)
            end = min(top + visible, total)
            if pv.total_known:
                pos = f"lines {top + 1}-{end}/{total}"
            else:
                pos = f"lines {top + 1}-{end}/{total}+ ({pv.reason})"
            put(stdscr, h - 1, max(0, w - len(pos) - 2), pos, curses.A_DIM)

        if pv.error or total == 0:
            put(stdscr, h - 1, max(0, w - 11), "ESC: Back", curses.A_DIM)
        else:
            put(stdscr, h - 1, 0, "ESC/q: Back", curses.A_DIM, width=w - 1)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (27, ord("q")):
            return
        if pv.error or total == 0:
            continue
        if key == curses.KEY_DOWN:
            top += 1
        elif key == curses.KEY_UP:
            top = max(0, top - 1)
        elif key == curses.KEY_NPAGE:
            top += visible
        elif key == curses.KEY_PPAGE:
            top = max(0, top - visible)
        elif key == curses.KEY_HOME:
            top = 0
        elif key == curses.KEY_END:
            top = max(0, total - visible)


def _utf8_len(b0: int) -> int:
    """Length of the UTF-8 sequence started by b0, 0 when it cannot start one."""
    if 0xC2 <= b0 <= 0xDF:
        return 2
    if 0xE0 <= b0 <= 0xEF:
        return 3
    if 0xF0 <= b0 <= 0xF4:
        return 4
    return 0


def prompt(stdscr, message: str) -> str | None:
    """Single line input.

    Returns the entered text (possibly empty) or ``None`` when ESC
    cancelled the prompt, so callers never confuse the two.
    """
    h, w = stdscr.getmaxyx()
    y = h - 2
    if y < 0:
        return None

    buf: list[str] = []
    pending = bytearray()  # bytes of a not yet complete UTF-8 sequence

    def feed(byte: int) -> str:
        if _utf8_len(byte):
            # A start byte supersedes any stale remainder: bytes arrive in
            # order, so an interrupted sequence can never complete anymore.
            pending.clear()
            pending.append(byte)
            return ""
        if not pending:
            return ""  # stray continuation byte
        pending.append(byte)
        expected = _utf8_len(pending[0])
        try:
            ch = pending.decode("utf-8")
        except UnicodeDecodeError:
            if len(pending) == expected:
                pending.clear()  # complete but invalid: never eat the next key
            return ""
        pending.clear()
        return ch

    def max_len() -> int:
        return max(1, w - len(message) - 2)

    while True:
        h, w = stdscr.getmaxyx()
        if y >= h:
            return None
        line = message + "".join(buf)
        put(stdscr, y, 0, line, width=w - 1)
        put(stdscr, y, min(len(line), w - 2), " ", curses.A_REVERSE)
        stdscr.move(y, min(len(line), w - 2))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13):
            return "".join(buf).strip()
        if key == 27:
            put(stdscr, y, 0, " " * (w - 1))
            return None
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if pending:
                pending.pop()
            elif buf:
                buf.pop()
        elif key == curses.KEY_DC and buf:
            buf.pop()  # the cursor always sits at the end of the buffer
        elif 32 <= key < 127 and len(buf) < max_len():
            buf.append(chr(key))
        elif 128 <= key <= 255:
            if _PDCURSES:
                if len(buf) < max_len():
                    buf.append(chr(key))
            else:
                ch = feed(key)
                if ch and len(buf) < max_len():
                    buf.append(ch)
        elif key > 255 and key not in _KEY_CODES and len(buf) < max_len():
            buf.append(chr(key))


def location_label(root: Path, current: Path) -> str:
    try:
        rel = current.relative_to(root)
    except ValueError:
        return str(current)
    return "." if str(rel) == "." else str(rel)


def find_row(rows, path: Path) -> int | None:
    for i, row in enumerate(rows):
        if row.path == path:
            return i
    return None


def stack_for(root: Path, target: Path) -> list[Path]:
    stack = [root]
    for part in target.relative_to(root).parts:
        stack.append(stack[-1] / part)
    return stack


def handle_mouse(stdscr, top: int) -> int:
    try:
        _, _, _, _, mouse_state = curses.getmouse()
    except curses.error:
        return top

    # Wheel constants are optional in some curses builds: without them the
    # wheel is simply inert and the keyboard keeps working.
    wheel_up = getattr(curses, "BUTTON4_PRESSED", 0) | getattr(curses, "BUTTON4_RELEASED", 0)
    wheel_down = getattr(curses, "BUTTON5_PRESSED", 0) | getattr(curses, "BUTTON5_RELEASED", 0)
    if mouse_state & wheel_up:
        return max(0, top - 3)
    if mouse_state & wheel_down:
        return top + 3
    return top


def clamp_viewport(cursor: int, top: int, count: int, visible: int) -> int:
    if count == 0:
        return 0
    top = max(0, min(top, max(0, count - visible)))
    if cursor < top:
        top = cursor
    elif cursor >= top + visible:
        top = cursor - visible + 1
    return top


def tui_main(stdscr):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    mouse_mask = getattr(curses, "ALL_MOUSE_EVENTS", 0)
    if mouse_mask:
        try:
            curses.mousemask(mouse_mask)
        except curses.error:
            pass
    try:
        # Short ESC delay: bare ESC answers fast, arrow keys still assemble.
        curses.set_escdelay(25)
    except (curses.error, AttributeError):
        pass
    stdscr.keypad(True)

    root = state.root_dir
    assert root is not None

    selected = 0
    cursor = 0
    top = 0
    menu_top = 0
    focus = "tree"
    expanded: set[Path] = set()
    message = ""
    desired: Path | None = None

    try:
        while True:
            h, w = stdscr.getmaxyx()
            if too_small(h, w):
                draw_too_small(stdscr)
                if stdscr.getch() in (ord("q"), 27):
                    break
                continue

            current = state.path_stack[-1]
            rows = collect_rows(root, expanded)

            if desired is not None:
                found = find_row(rows, desired)
                if found is not None:
                    cursor = found
                desired = None

            if rows:
                cursor = max(0, min(cursor, len(rows) - 1))
            else:
                cursor = 0

            visible = h - 2
            top = clamp_viewport(cursor, top, len(rows), visible)

            menu_x, menu_width = menu_geometry(h, w)
            tree_width = max(1, menu_x - 1)
            end = min(top + visible, len(rows))
            scroll_info = f"[{top + 1}-{end}/{len(rows)}]" if len(rows) > visible else ""

            stdscr.clear()
            draw_tree(stdscr, root, rows, current, cursor, top, tree_width, focus)
            menu_top = menu_offset(selected, menu_top, visible)
            draw_menu(stdscr, selected, focus, menu_x, menu_width, menu_top)
            draw_status(stdscr, message, location_label(root, current), scroll_info)
            stdscr.refresh()
            message = ""

            key = stdscr.getch()

            if key == 9:  # Tab switches focus
                focus = "menu" if focus == "tree" else "tree"

            elif _KEY_MOUSE is not None and key == _KEY_MOUSE:
                top = handle_mouse(stdscr, top)

            elif key == 27:  # bare ESC on the main screen never quits
                message = "Press q from the menu to quit"

            elif focus == "tree":
                if key == curses.KEY_UP:
                    cursor -= 1
                elif key == curses.KEY_DOWN:
                    cursor += 1
                elif key == curses.KEY_PPAGE:
                    cursor -= visible
                elif key == curses.KEY_NPAGE:
                    cursor += visible
                elif key == curses.KEY_HOME:
                    cursor = 0
                elif key == curses.KEY_END:
                    cursor = len(rows) - 1
                elif key in (curses.KEY_RIGHT, ord(" ")):
                    if rows and rows[cursor].is_dir:
                        expanded.add(rows[cursor].path)
                elif key in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, 8):
                    if rows and rows[cursor].is_dir and rows[cursor].path in expanded:
                        expanded.discard(rows[cursor].path)
                    else:
                        parent = find_row(rows, rows[cursor].path.parent) if rows else None
                        if parent is not None:
                            cursor = parent
                elif key in (10, 13):
                    if rows and rows[cursor].is_dir:
                        target = rows[cursor].path
                        state.path_stack = stack_for(root, target)
                        expanded.add(target)
                        desired = target
                elif key == ord("v") and rows and not rows[cursor].is_dir:
                    saved = (cursor, top, focus, list(state.path_stack))
                    preview_screen(stdscr, rows[cursor].path)
                    cursor, top, focus, state.path_stack = saved

            else:  # menu focus
                if key == curses.KEY_UP and selected > 0:
                    selected -= 1
                elif key == curses.KEY_DOWN and selected < len(MENU_ITEMS) - 1:
                    selected += 1
                elif key == curses.KEY_PPAGE:
                    selected = max(0, selected - visible)
                elif key == curses.KEY_NPAGE:
                    selected = min(len(MENU_ITEMS) - 1, selected + visible)
                elif key in (10, 13):
                    if MENU_ITEMS[selected] == "Quit":
                        if confirm(stdscr, "Quit KTrex?"):
                            break
                        message = "Quit cancelled"
                        continue
                    message = run_action(stdscr, current, selected)
                    desired = state.path_stack[-1]
    finally:
        try:
            curses.curs_set(1)
        except curses.error:
            pass


def run_action(stdscr, current: Path, selected: int) -> str:
    """Run the highlighted menu action and return a status message."""
    action = MENU_ITEMS[selected]
    root = state.root_dir
    assert root is not None

    if action == "Create Directory":
        name = prompt(stdscr, "Directory name: ")
        if name is None:
            return "Cancelled"
        if not name:
            return ""
        try:
            new_dir = create_dir(current, name)
        except InvalidName as e:
            return f"Error: {e}"
        if new_dir is None:
            return f"Already exists: {name}"
        state.path_stack.append(new_dir)
        return f"Created {name}"

    if action == "Create File":
        name = prompt(stdscr, "File name: ")
        if name is None:
            return "Cancelled"
        if not name:
            return ""
        try:
            created = create_file(current, name)
        except InvalidName as e:
            return f"Error: {e}"
        return f"Created {name}" if created else f"Already exists: {name}"

    if action == "Undo":
        if not undo_last():
            return "Nothing to undo"
        if not current.exists():
            state.path_stack.pop()
        return "Undone"

    if action == "Load Preset":
        value = prompt(stdscr, "Preset name or path: ")
        if value is None:
            return "Cancelled"
        if not value:
            return ""
        try:
            load_preset(value, current)
        except Exception as e:
            return f"Error: {e}"
        return f"Preset applied: {value}"

    if action == "Save Structure":
        path_str = prompt(stdscr, "Save to (path): ")
        if path_str is None:
            return "Cancelled"
        if not path_str:
            return ""
        try:
            tree = build_tree(root)
            with open(Path(path_str), "w", encoding="utf-8") as f:
                json.dump(tree, f, indent=2)
        except Exception as e:
            return f"Error: {e}"
        return f"Saved to {path_str}"

    if action == "Load Structure":
        path_str = prompt(stdscr, "Load from (path): ")
        if path_str is None:
            return "Cancelled"
        if not path_str:
            return ""
        try:
            with open(Path(path_str), "r", encoding="utf-8") as f:
                tree = json.load(f)
            apply_tree(root, tree)
        except Exception as e:
            return f"Error: {e}"
        return f"Loaded {path_str}"

    if action == "Go Back":
        if len(state.path_stack) > 1:
            state.path_stack.pop()
            return ""
        return "Already at project root"

    if action == "Help":
        draw_help(stdscr)
        return ""

    return ""
