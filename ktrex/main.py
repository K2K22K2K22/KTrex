import curses
import sys
from pathlib import Path

from ktrex import __version__, state
from ktrex.tui import tui_main


def resolve_root(argv: list[str]) -> Path:
    # Resolve project root directory from CLI arguments.
    if len(argv) == 1:
        # No argument → ask user
        name = input("Project directory name (or . for current): ").strip()
        if not name:
            raise ValueError("Project directory name cannot be empty")
        return Path(name)

    arg = argv[1]

    if arg == "--version":
        print(f"ktrex {__version__}")
        sys.exit(0)

    if arg == ".":
        return Path.cwd()

    return Path(arg)


def main():
    try:
        root = resolve_root(sys.argv)
    except ValueError as e:
        print(f"Error: {e}")
        return

    root = root.expanduser().resolve()

    # Create directory only if it does not exist
    root.mkdir(parents=True, exist_ok=True)
    # Clean initialization
    state.root_dir = root
    state.path_stack = [root]
    state.history.clear()

    curses.wrapper(tui_main)


if __name__ == "__main__":
    main()
