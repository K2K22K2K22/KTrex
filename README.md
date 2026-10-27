# KTrex

**KTrex** is an interactive terminal application for building directory and
file structures. Point it at a folder, grow a tree with a few keystrokes,
undo mistakes, save the layout, and reuse it later as a preset on any new
project.

It runs as a curses TUI (tree on the left, actions on the right) and ships
as a plain command line tool. On Linux and macOS it uses the curses module
from the standard library; on Windows it installs the PDCurses-based
`windows-curses` package automatically, so a normal pip install is enough.

## Features

- Interactive tree view with cursor navigation, expandable folders, and a mouse-wheel friendly viewport
- In-app file preview (`v`) for any selected file, read-only, with scrolling and line numbers
- Safe undo: a failed or reckless undo can never delete real data
- Built-in presets for common project layouts (Python, Django, FastAPI, Flask, Go, Rust, Node, React, ML, static sites, and more)
- Save the current tree to JSON and load it back later, or load a preset by name or file path
- Presets and structures share one simple JSON format
- Everything stays inside the project root; symlinks are never followed
  (the final symlink check is atomic, parent directories cannot be made
  fully race-free)
- Works from the command line too: `ktrex --apply python_package my-lib`

## Requirements

- Python 3.10 or newer
- Windows 10/11 (PowerShell, Windows Terminal or the classic console),
  Linux, or macOS
- No manual terminal setup: the curses backend is installed automatically
  on Windows, everything else uses the standard library

## Install

```bash
pip install KTrex
```

On Windows use PowerShell, cmd, or Windows Terminal:

```powershell
py -m pip install KTrex
```

## Usage

Interactive session:

```bash
ktrex                # prompts for a directory
ktrex my-project     # create/open my-project
ktrex .              # work inside the current directory
```

PowerShell works the same way:

```powershell
ktrex my-project
```

Command line:

```text
ktrex [directory] [--version] [--list-presets] [--apply PRESET]
```

```bash
ktrex --version
ktrex --list-presets
ktrex --apply python_package my-lib
```

Exit codes: `0` on success, `1` on an error (bad preset, unwritable directory).

## Keyboard

Tree view (left pane):

| Key | Action |
|---|---|
| Up / Down | Move the cursor |
| Right / Space | Expand a folder |
| Left / Backspace | Collapse a folder, or go to the parent |
| Enter | Enter the selected folder |
| v | Preview the selected file |
| PageUp / PageDown | Move one page |
| Home / End | Jump to the top or bottom |
| Ctrl + / Ctrl - | Zoom the tree pane in or out |
| Mouse wheel | Scroll the tree |

Preview screen:

| Key | Action |
|---|---|
| Up / Down | Scroll one line |
| PageUp / PageDown | Scroll one page |
| Home / End | Jump to the first or last visible page |
| ESC / q | Close the preview and return to the tree |

Menu and prompts (right pane and bottom line):

| Key | Action |
|---|---|
| Tab | Switch focus between tree and menu |
| Up / Down | Move the selection |
| Enter | Run the highlighted action |
| ESC | Cancel the current prompt or confirmation |
| ESC (main screen) | Shows how to quit; it never exits on its own |
| y | Confirm a pending confirmation |

Quit from the menu (it asks for confirmation; ESC or anything except `y`
cancels it).

## Presets

A preset describes a starting tree. KTrex ships twelve:

```text
cli_tool, django_project, fastapi_project, flask_project, go_project,
ml_project, node_api, python_package, react_app, rust_project, static_site,
web_project
```

Use one from the command line:

```bash
ktrex --apply fastapi_project my-api
```

or from the TUI: choose `Load Preset` and pick one from the list with the
arrow keys. The last list entry, `Type a name or path...`, opens a prompt
instead, so a custom preset file still works:

```text
Preset name or path: /home/me/presets/rust_cli.json
```

## Safety

- Existing files are never overwritten
- Non-empty directories are never deleted
- Undo only reverts entries KTrex created, and refuses when the entry was
  replaced (different device or inode), a symlink was swapped in for it, or
  the file changed since creation; the refused entry stays in the history
- A target that vanished on its own is dropped from the history cleanly
- Every path is checked to stay inside the project root
- Symbolic links are listed but never followed
- Unreadable directories render as a note instead of crashing
- A failed apply rolls back in reverse order, keeping disk and undo history
  in sync; if a created directory gained content meanwhile, it is reported
  as a leftover instead of being deleted

## Troubleshooting

- `Error: KTrex needs the curses module` means this Python has no curses
  backend. On Windows a normal install pulls in `windows-curses`
  automatically; if you see this message, `pip install windows-curses`
  fixes it
- `Error: terminal initialization failed` means the terminal refused to
  enter curses mode. Try a different terminal, on Windows preferably
  Windows Terminal over the classic console
- Ctrl+C exits with code 1 and restores the terminal, it never leaves a
  broken console behind

## Known limitations

- Undo identity checks rely on device and inode numbers. On filesystems
  that report no usable inode numbers the check falls back to file type,
  size and mtime and is less strict
- Windows filename rules (illegal characters, reserved device names such
  as `CON` or `COM1`, trailing dot or space) are enforced on Windows only,
  so a name like `con` stays legal on Linux
- Duplicate names in presets and structures are compared case-insensitively
  on Windows and case-sensitively on Linux and macOS, matching each
  filesystem's behavior

## Development

```bash
git clone git@github.com:K2K22K2K22/KTrex.git
cd KTrex
python -m pip install -e ".[dev]"
python -m pytest
```

## License

MIT License. See [LICENSE](./LICENSE).

## Sponsor

If you find this project useful and want to support its development:

[![Buy Me a Monster](https://img.shields.io/badge/Buy%20Me%20a%20Monster-ko--fi-red)](https://ko-fi.com/akris)
