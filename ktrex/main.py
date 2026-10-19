import argparse
import sys
from pathlib import Path

from ktrex import __version__, state
from ktrex.presets import builtin_presets, load_preset
from ktrex.tree import RollbackError

try:
    import curses
except ImportError:  # Windows ships Python without curses
    curses = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ktrex",
        description="Build a directory structure, interactively or from a preset.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="project directory (default: ask, use . for the current directory)",
    )
    parser.add_argument("--version", action="version", version=f"ktrex {__version__}")
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="list the bundled presets and exit",
    )
    parser.add_argument(
        "--apply",
        metavar="PRESET",
        help="apply a preset to the directory and exit",
    )
    return parser


def prepare_root(directory: str | None) -> Path:
    """Resolve the project directory, create it, and reset the session state."""
    if directory is None:
        directory = input("Project directory name (or . for current): ").strip()
        if not directory:
            raise ValueError("Project directory name cannot be empty")

    root = Path.cwd() if directory == "." else Path(directory)
    root = root.expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    root.mkdir(parents=True, exist_ok=True)

    state.root_dir = root
    state.path_stack = [root]
    state.history.clear()
    return root


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_presets:
        for name in builtin_presets():
            print(name)
        return 0

    if args.apply and args.directory is None:
        args.directory = "."

    if not args.list_presets and not args.apply and curses is None:
        print("Error: KTrex needs the curses module, which this Python lacks.")
        print("On Windows, install a curses package such as windows-curses.")
        return 1

    try:
        root = prepare_root(args.directory)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except OSError as e:
        print(f"Error: cannot create project directory: {e}")
        return 1
    except KeyboardInterrupt:
        return 1

    if args.apply:
        try:
            load_preset(args.apply, root)
        except (ValueError, OSError, RollbackError) as e:
            print(f"Error: {e}")
            return 1
        except KeyboardInterrupt:
            return 1
        print(f"Applied preset '{args.apply}' to {root}")
        return 0

    assert curses is not None  # interactive mode returned earlier when missing

    from ktrex.tui import tui_main

    # curses.wrapper restores the terminal even when tui_main fails or the
    # user aborts, so both leave a clean console behind.
    try:
        curses.wrapper(tui_main)
    except KeyboardInterrupt:
        return 1
    except curses.error as e:
        print(f"Error: terminal initialization failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
