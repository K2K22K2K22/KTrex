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
- Presets and structures share one simple JSON format, so you can write your own
- Everything stays inside the project root; symlinks are never followed
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
- Footer shows `lines A-B/N`, or `N+` when the file was truncated by the limit
- Empty files show a friendly note; binary files (containing NUL bytes) show a
  message instead of garbage; unreadable or missing files show the error
- Symlinked files are not previewed, matching the tree's symlink policy
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

### Preset format

One JSON object per entry. Every entry needs `name` and `type`; a `dir` may
add `children`, which is a list of more entries. A `file` entry creates an
empty file.

```json
{
  "name": "project",
  "type": "dir",
  "children": [
    {
      "name": "src",
      "type": "dir",
      "children": [
        { "name": "main.py", "type": "file" }
      ]
    },
    { "name": "README.md", "type": "file" }
  ]
}
```

Rules:

- `name` must be a single path segment (no slashes, no `.`, no `..`)
- `type` is `"dir"` or `"file"`
- `children` only makes sense on `"dir"` entries
- Applying a preset never overwrites anything that already exists; new entries
  are added to the tree and become undoable like any other creation

The same format is used by `Save Structure` and `Load Structure`, so a saved
project layout is a preset you can edit by hand.

## Safety

- Existing files are never overwritten
- Non-empty directories are never deleted
- Undo only reverts entries KTrex created, and refuses if the file changed
  since creation
- Every path is checked to stay inside the project root
- Symbolic links are listed but never followed
- Unreadable directories render as a note instead of crashing
- A failed apply rolls back, keeping disk and undo history in sync

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
