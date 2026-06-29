import curses
import json
from pathlib import Path

from . import state
from .fs import InvalidName, create_dir, create_file, undo_last
from .presets import load_preset
from .render import collect_rows, format_row
from .tree import apply_tree, build_tree

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
    "  ↑ / ↓        Move the cursor",
    "  → / Space    Expand a folder",
    "  ← / Backspace  Collapse or go to parent",
    "  Enter        Enter the folder",
    "  PageUp / Down  Move a page",
    "  Home / End   Jump to top or bottom",
    "",
    "Menu:",
    "  Tab          Switch focus between tree and menu",
    "  Enter        Run the highlighted action",
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
    "  • KTrex never deletes non-empty directories",
    "  • Existing files are never overwritten",
    "  • Presets are additive",
    "",
    "Press any key to return",
]

MENU_WIDTH = 24
MIN_HEIGHT = 6
MIN_WIDTH = 28


def put(stdscr, y: int, x: int, text: str, attr: int = 0, width: int | None = None):
    """Write text without ever raising on the screen edge."""
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    room = w - x - 1 if width is None else min(width, w - x - 1)
    if room <= 0:
        return
    try:
        stdscr.addnstr(y, x, text, room, attr)
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


def draw_menu(stdscr, selected: int, focus: str, menu_x: int, menu_width: int):
    put(stdscr, 0, menu_x, "Actions", curses.A_BOLD, width=menu_width)
    for i, item in enumerate(MENU_ITEMS):
        if 1 + i >= stdscr.getmaxyx()[0] - 1:
            break
        attr = curses.A_REVERSE if focus == "menu" and i == selected else curses.A_NORMAL
        put(stdscr, 1 + i, menu_x, item, attr, width=menu_width)


def draw_status(stdscr, message: str, location: str, scroll_info: str):
    h, w = stdscr.getmaxyx()
    label = message or location
    tail = max(0, w - len(scroll_info) - 2) if scroll_info else w
    put(stdscr, h - 1, 0, label, curses.A_DIM, width=tail)
    if scroll_info:
        put(stdscr, h - 1, max(0, w - len(scroll_info) - 1), scroll_info, curses.A_DIM)


def draw_help(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    for i, line in enumerate(HELP_TEXT):
        if i + 1 >= h - 1:
            break
        put(stdscr, i + 1, 2, line, width=w - 4)
    stdscr.refresh()
    stdscr.getch()


def prompt(stdscr, message: str) -> str:
    h, w = stdscr.getmaxyx()
    y = h - 2
    if y < 0:
        return ""

    put(stdscr, y, 0, message, width=w - 1)
    x = min(len(message), max(0, w - 2))
    stdscr.move(y, x)
    stdscr.refresh()

    curses.echo()
    try:
        value = stdscr.getstr(y, x, max(1, w - x - 1)).decode().strip()
    except curses.error:
        value = ""
    finally:
        curses.noecho()
    return value


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

    if mouse_state & (curses.BUTTON4_PRESSED | curses.BUTTON4_RELEASED):
        return max(0, top - 3)
    if mouse_state & (curses.BUTTON5_PRESSED | curses.BUTTON5_RELEASED):
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
    curses.curs_set(0)
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
    except curses.error:
        pass
    stdscr.keypad(True)

    root = state.root_dir
    assert root is not None

    selected = 0
    cursor = 0
    top = 0
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
            draw_menu(stdscr, selected, focus, menu_x, menu_width)
            draw_status(stdscr, message, location_label(root, current), scroll_info)
            stdscr.refresh()
            message = ""

            key = stdscr.getch()

            if key == 9:  # Tab switches focus
                focus = "menu" if focus == "tree" else "tree"

            elif key == curses.KEY_MOUSE:
                top = handle_mouse(stdscr, top)

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

            else:  # menu focus
                if key == curses.KEY_UP and selected > 0:
                    selected -= 1
                elif key == curses.KEY_DOWN and selected < len(MENU_ITEMS) - 1:
                    selected += 1
                elif key == curses.KEY_PPAGE:
                    top = max(0, top - 5)
                elif key == curses.KEY_NPAGE:
                    top += 5
                elif key in (10, 13):
                    if MENU_ITEMS[selected] == "Quit":
                        break
                    run_action(stdscr, current, selected)
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
        if not value:
            return ""
        try:
            load_preset(value, current)
        except Exception as e:
            return f"Error: {e}"
        return f"Preset applied: {value}"

    if action == "Save Structure":
        path_str = prompt(stdscr, "Save to (path): ")
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
