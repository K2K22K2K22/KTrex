# KTrex

**KTrex** is an interactive terminal application for building directory and
file structures. Point it at a folder, grow a tree with a few keystrokes,
undo mistakes, save the layout, and reuse it later as a preset on any new
project.

It runs as a curses TUI (tree on the left, actions on the right) and ships
as a plain command line tool with no runtime dependencies.

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
- A Unix-like terminal with `curses` (included in the standard library on Linux and macOS; Windows may need extra setup)

## Install

```bash
pip install KTrex
```

## Usage

Interactive session:

```bash
ktrex                # prompts for a directory
ktrex my-project     # create/open my-project
ktrex .              # work inside the current directory
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

## File preview

Press `v` on a file to read it without leaving KTrex or opening an editor:

- Header shows the filename and full path, clipped to the terminal width
- Footer shows `lines A-B/N` for a complete read, or `lines A-B/N+ (byte limit)`
  or `(line limit)` when truncated; the partial count is never shown as the total
- Empty files show a friendly note; binary files (containing NUL bytes) show a
  message instead of garbage; unreadable or missing files show the error
- Symlinked files are not previewed, matching the tree's symlink policy; the
  open itself refuses to follow a final symlink, and a file swapped between
  validation and reading is refused by an identity check
- Reading is bounded: at most 256 KiB and 2000 lines are held in memory, so a
  huge file previews instantly and scrolling never rescans the disk
- Preview is strictly read-only; it never touches the file or the undo history
- The preview redraws from the current terminal size, so resizing mid-preview
  is safe

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

or from the TUI: choose `Load Preset` and type a preset name. To use your own
preset, save it anywhere as a JSON file and enter its path in the same
prompt:

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

## Development

```bash
git clone git@github.com:K2K22K2K22/KTrex.git
cd KTrex
python -m pip install -e .
python -m pytest
```

## License

MIT License. See [LICENSE](./LICENSE).

## Sponsor

If you find this project useful and want to support its development:

[![Buy Me a Monster](https://img.shields.io/badge/Buy%20Me%20a%20Monster-ko--fi-red)](https://ko-fi.com/akris)
