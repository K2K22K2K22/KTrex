# KTrex

**KTrex** is an interactive, terminal-based directory and file structure builder.
Create, navigate, undo, save, load, and reuse project layouts from a curses TUI.

## Install

```bash
pip install KTrex
```

## Usage

```bash
ktrex
ktrex my-project
ktrex .
```

CLI:
```text
ktrex [directory] [--version] [--list-presets] [--apply PRESET]
```

## Keys

| Key | Action |
|---|---|
| Tab | Switch tree/menu |
| Arrow keys | Move |
| Enter | Enter or run |
| Space | Expand |
| Backspace | Collapse or go up |
| PageUp/PageDown | Scroll |
| Home/End | Jump |
| Mouse wheel | Scroll |

## Presets

```bash
ktrex --list-presets
ktrex --apply python_package my-lib
```

Bundled: cli_tool, django_project, fastapi_project, flask_project, go_project,
ml_project, node_api, python_package, react_app, rust_project, static_site,
web_project.

## Notes

- Safe undo (never deletes non-empty dirs)
- Presets are additive, no overwrites
- Never writes outside project root
- Skips symlinks when traversing
- Unix-like; `curses` required (Windows may need extra setup)

MIT License. See [LICENSE](./LICENSE).

