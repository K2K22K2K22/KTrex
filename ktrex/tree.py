from pathlib import Path


def build_tree(path: Path) -> dict:
    # Convert filesystem into a serializable tree structure
    node = {"name": path.name, "type": "dir", "children": []}

    for p in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name)):
        if p.is_dir():
            node["children"].append(build_tree(p))
        else:
            node["children"].append({"name": p.name, "type": "file"})

    return node


def apply_tree(base: Path, tree: dict):
    # Create filesystem structure from a tree model
    for child in tree.get("children", []):
        p = base / child["name"]

        if child["type"] == "dir":
            p.mkdir(exist_ok=True)
            apply_tree(p, child)
        else:
            p.touch(exist_ok=True)
