import curses
import json
from pathlib import Path

from . import state
from .fs import create_dir, create_file, undo_last
from .presets import load_preset
from .render import render_tree
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
    "KTrex — Interactive Directory Builder",
    "",
    "Navigation:",
    "  ↑ / ↓     Move through menu",
    "  Enter     Select action",
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
    "Scrolling:",
    "  PageUp / PageDown  Scroll tree view",
    "  Ctrl + U / Ctrl + D  Scroll up / down",
    "  Mouse Wheel        Scroll tree",
    "",
    "Press any key to return",
]


def draw_menu(stdscr, selected: int):
    h, w = stdscr.getmaxyx()
    menu_width = min(24, max(10, w - 2))
    start_x = max(0, w - menu_width)
    start_y = 2

    if start_y >= h - 1:
        return

    stdscr.addnstr(start_y - 1, start_x, "Actions", menu_width, curses.A_BOLD)

    for i, item in enumerate(MENU_ITEMS):
        y = start_y + i
        if y >= h - 1:
            break
        attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
        stdscr.addnstr(y, start_x, item, menu_width, attr)


def draw_tree(stdscr, root: Path, current: Path, scroll_offset: int):
    h, w = stdscr.getmaxyx()
    stdscr.addnstr(0, 0, root.name, w - 2, curses.A_BOLD)

    lines = render_tree(root, current=current)

    visible_height = h - 2
    start = scroll_offset
    end = min(start + visible_height, len(lines))

    for idx, line in enumerate(lines[start:end], start=1):
        stdscr.addnstr(idx, 0, line, w - 2)

    if len(lines) > visible_height:
        indicator = f"[{start + 1}-{end}/{len(lines)}]"
        stdscr.addnstr(h - 1, 0, indicator, w - 2)


def draw_help(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    for i, line in enumerate(HELP_TEXT):
        y = i + 1
        if y >= h - 1:
            break
        stdscr.addnstr(y, 2, line, w - 4)

    stdscr.refresh()
    stdscr.getch()


def prompt(stdscr, message: str) -> str:
    h, w = stdscr.getmaxyx()
    y = h - 2
    if y < 0:
        return ""

    stdscr.move(y, 0)
    stdscr.clrtoeol()
    stdscr.addnstr(y, 0, message, w - 2)
    stdscr.refresh()

    curses.echo()
    value = stdscr.getstr(y, min(len(message), w - 3)).decode().strip()
    curses.noecho()
    return value


def notify(stdscr, message: str):
    h, w = stdscr.getmaxyx()
    y = h - 1
    if y < 0:
        return

    stdscr.move(y, 0)
    stdscr.clrtoeol()
    stdscr.addnstr(y, 0, message, w - 2)
    stdscr.refresh()
    stdscr.getch()


def tui_main(stdscr):
    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    stdscr.keypad(True)

    scroll_offset = 0
    root = state.root_dir
    assert root is not None
    selected = 0

    while True:
        current = state.path_stack[-1]

        lines = render_tree(root, current=current)
        h, _ = stdscr.getmaxyx()
        max_offset = max(0, len(lines) - (h - 2))
        scroll_offset = min(scroll_offset, max_offset)

        stdscr.clear()
        draw_tree(stdscr, root, current, scroll_offset)
        draw_menu(stdscr, selected)

        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            scroll_offset = 0

        elif key == curses.KEY_UP and selected > 0:
            selected -= 1

        elif key == curses.KEY_DOWN and selected < len(MENU_ITEMS) - 1:
            selected += 1

        elif key == curses.KEY_NPAGE:
            scroll_offset += 5

        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - 5)

        elif key == 4:
            scroll_offset += 5

        elif key == 21:
            scroll_offset = max(0, scroll_offset - 5)

        elif key == curses.KEY_MOUSE:
            try:
                _, _, _, _, mouse_state = curses.getmouse()
                if mouse_state & (curses.BUTTON4_PRESSED | curses.BUTTON4_RELEASED):
                    scroll_offset = max(0, scroll_offset - 3)
                elif mouse_state & (curses.BUTTON5_PRESSED | curses.BUTTON5_RELEASED):
                    scroll_offset += 3
            except curses.error:
                pass

        elif key in (10, 13):
            action = MENU_ITEMS[selected]
            scroll_offset = 0

            if action == "Create Directory":
                name = prompt(stdscr, "Directory name: ")
                if name:
                    new_dir = create_dir(current, name)
                    if new_dir:
                        state.path_stack.append(new_dir)

            elif action == "Create File":
                name = prompt(stdscr, "File name: ")
                if name:
                    create_file(current, name)

            elif action == "Undo":
                undone = undo_last()
                if undone and not current.exists():
                    state.path_stack.pop()

            elif action == "Load Preset":
                value = prompt(stdscr, "Preset name or path: ")
                if value:
                    try:
                        load_preset(value, current)
                    except Exception as e:
                        notify(stdscr, f"Error: {e}")

            elif action == "Save Structure":
                path_str = prompt(stdscr, "Save to (path): ")
                if path_str:
                    try:
                        tree = build_tree(root)
                        with open(Path(path_str), "w") as f:
                            json.dump(tree, f, indent=2)
                        notify(stdscr, "Structure saved successfully")
                    except Exception as e:
                        notify(stdscr, f"Error: {e}")

            elif action == "Load Structure":
                path_str = prompt(stdscr, "Load from (path): ")
                if path_str:
                    try:
                        with open(Path(path_str), "r") as f:
                            tree = json.load(f)
                        apply_tree(root, tree)
                    except Exception as e:
                        notify(stdscr, f"Error: {e}")

            elif action == "Go Back":
                if len(state.path_stack) > 1:
                    state.path_stack.pop()
                else:
                    notify(stdscr, "Already at project root")

            elif action == "Help":
                draw_help(stdscr)

            elif action == "Quit":
                break

        stdscr.refresh()
