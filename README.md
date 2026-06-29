# KTrex

**KTrex** is an interactive, terminal-based directory and file structure builder.
It lets you create, navigate, undo, save, load, and reuse project layouts directly
from a curses TUI, safely and deterministically.

> Think: `mkdir` + `tree` + `undo` + `presets` + `resume`, all in one tool.

---

## Features

- Interactive terminal UI (keyboard driven)
- Move through the tree with a cursor, expand and collapse folders
- Create directories and files visually
- Safe undo (never deletes non-empty directories)
- Presets (builtin or external JSON)
- Save a project structure to JSON and load it back
- Non-destructive by design (no overwrites, no forced deletes)
- Works offline, zero runtime dependencies
- Non-interactive mode for scripts: list and apply presets from the command line

---

## Installation

### Using pip (recommended)

```bash
pip install KTrex
```

### Editable install (for development)

```bash
git clone https://github.com/K2K22K2K22/KTrex.git
cd KTrex
pip install -e .
```

---

## Usage

Start the interactive interface in any directory:

```bash
ktrex
```

You are dropped into a TUI that shows your project tree on the left and the
actions on the right.

You can also name the directory up front, or use `.` for the current one:

```bash
ktrex my-project
ktrex .
```

### Command line options

```text
ktrex [directory] [--version] [--list-presets] [--apply PRESET]
```

- `--version` prints the version and exits.
- `--list-presets` prints the bundled preset names and exits.
- `--apply PRESET` builds the preset in the directory and exits, without
  opening the interface. Defaults to the current directory when no directory
  is given.

```bash
ktrex --list-presets
ktrex --apply python_package my-lib
```

Exit code is `0` on success and `1` when the directory or preset is invalid.

---

## Controls

| Key                    | Action                              |
|------------------------|-------------------------------------|
| Tab                    | Switch focus between tree and menu  |
| ↑ / ↓                  | Move the cursor (tree or menu)      |
| → / Space              | Expand a folder                     |
| ← / Backspace          | Collapse a folder, or go to parent  |
| Enter                  | Enter a folder, or run the action   |
| PageUp / PageDown      | Move a page                         |
| Home / End             | Jump to the top or bottom           |
| Mouse Wheel            | Scroll the tree                     |
| Quit                   | Exit KTrex safely                   |

---

## Actions Explained

### Create Directory

- Creates a new directory in the current location
- Enters the new directory

### Create File

- Creates a file in the current directory
- Does not change navigation

### Undo

- Reverts the most recent create action
- Removes files and empty directories only
- Never deletes non-empty directories

### Load Preset

- Loads a structure by name or file path
- Presets are additive, never destructive

### Save Structure

- Serializes the entire project tree to a JSON file
- Useful for reuse, backups, or AI-generated layouts

### Load Structure

- Loads a previously saved structure JSON
- Applies safely without removing existing files

### Go Back

- Navigates to the parent directory
- Cannot escape the project root

### Help

- Shows the built-in documentation and keybindings

---

## Presets

### Built-in presets

```text
ml_project
python_package
web_project
```

Usage:

```text
Load Preset -> ml_project
```

### External presets

```text
Load Preset -> /path/to/custom_preset.json
```

The preset format is documented below.

---

## Preset / Structure Format

KTrex uses a simple, declarative JSON format:

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
    }
  ]
}
```

The same format is used by presets, saved structures, and generated layouts.

---

## Safety Guarantees

KTrex is designed to be safe by default:

- Never overwrites files
- Never deletes non-empty directories
- Never writes outside the project root
- Skips symbolic links and unreadable directories instead of crashing
- Rolls back a failed apply so disk and undo history stay in sync

---

## License

This project is licensed under the **MIT License**.
You are free to use, modify, and distribute this software with proper attribution.

See the [LICENSE](./LICENSE) file for details.

---

## Sponsor

If you find this project useful and want to support its development:

[![Ko-Fi](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ko--fi-red)](https://ko-fi.com/akris)

Your support helps keep this project alive and actively maintained.
