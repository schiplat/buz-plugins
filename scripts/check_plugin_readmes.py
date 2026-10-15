#!/usr/bin/env python3
"""Repo rule: every plugin directory must ship a non-empty README.md.

A plugin directory is any directory under the plugins root that contains a
step-template YAML file (`.yaml`/`.yml`). Hidden directories are ignored,
matching how the index and validator scan specs.
"""

from __future__ import annotations

import sys
from pathlib import Path

TEMPLATE_SUFFIXES = {".yaml", ".yml"}


def plugin_dirs(plugins_root: Path) -> list[Path]:
    dirs = set()
    for path in plugins_root.rglob("*"):
        if path.suffix in TEMPLATE_SUFFIXES and path.is_file():
            if any(part.startswith(".") for part in path.relative_to(plugins_root).parts):
                continue
            if path.parent != plugins_root:
                dirs.add(path.parent)
    return sorted(dirs)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path("plugins")
    if not root.is_dir():
        raise SystemExit(f"{root}: plugins directory not found")
    dirs = plugin_dirs(root)
    missing = [
        str(directory / "README.md")
        for directory in dirs
        if not (directory / "README.md").is_file()
        or not (directory / "README.md").read_text(encoding="utf-8").strip()
    ]
    if missing:
        for path in missing:
            print(f"missing or empty README: {path}", file=sys.stderr)
        raise SystemExit(f"{len(missing)} plugin README(s) missing — every plugin needs one")
    print(f"plugin readmes: {len(dirs)} plugin dir(s) ok")


if __name__ == "__main__":
    sys.exit(main())
