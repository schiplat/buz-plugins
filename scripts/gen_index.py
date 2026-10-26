#!/usr/bin/env python3
"""Generate index.json for the buz-plugin step index (marketplace ADR §6.1).

Recursively walks visible plugins/**/*.yaml|yml specs, extracts the `id` / `version` top-level scalars,
hashes each file, and emits the full scalar meta alongside the entry:

    { "steps": [ { "id": ..., "version": ..., "file": ..., "sha256": ...,
                   "category": ..., "requires_buz": ..., "engine": ..., ... } ] }

Stdlib only (no PyYAML dependency). Invalid or duplicate entries fail the
run — generation happens in CI after `buz step validate` has already gated
the merge, so reaching this point with a broken spec is a bug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^id:\s*[\"']?([a-z0-9-]+/[a-z0-9-]+)[\"']?\s*$", re.MULTILINE)
VERSION_RE = re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)[\"']?\s*$", re.MULTILINE)
CATEGORY_LINE_RE = re.compile(r"^category:\s*(.*?)\s*$", re.MULTILINE)
CATEGORY_RE = re.compile(r"[A-Za-z0-9 _-]+")

# Top-level scalar meta published alongside id/version/file/sha256 so the
# manager can list and compatibility-gate plugins without downloading every
# template (the `requires_buz` contract gate in particular). Only simple
# top-level scalars are indexed; block scalars and nested structures stay
# out — the full spec remains the single source of truth.
META_FIELDS = (
    "name",
    "description",
    "description_zh",
    "author",
    "publisher",
    "license",
    "source_repo",
    "engine",
    "default_timeout",
    "requires_buz",
)
REQUIRES_BUZ_RE = re.compile(r"^(>=)?\d+\.\d+\.\d+$")
# A scalar whose whole value is one of these forms is a block scalar header
# ("description: |"), not an inline value — skip the field.
BLOCK_SCALAR_RE = re.compile(r"[|>][-+0-9]*\s*#?.*$")


def extract_meta(raw: str) -> dict[str, str]:
    """Extract top-level scalar meta fields from a spec's raw text."""
    meta: dict[str, str] = {}
    for field in META_FIELDS:
        match = re.search(
            rf"^{field}:[ \t]+(\"[^\"]*\"|'[^']*'|[^#\n]*?)[ \t]*(?:#.*)?$",
            raw,
            re.MULTILINE,
        )
        if not match:
            continue
        value = match.group(1).strip()
        if not value or BLOCK_SCALAR_RE.fullmatch(value):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            meta[field] = value
    return meta


def check_requires_buz(meta: dict[str, str], path: Path) -> None:
    """Fail the build on a malformed contract gate (CI validates specs with
    `buz step validate` first; this mirrors the manager's accepted forms)."""
    requires = meta.get("requires_buz")
    if requires is not None and not REQUIRES_BUZ_RE.fullmatch(requires):
        raise SystemExit(
            f"{path}: requires_buz {requires!r} is not '>=X.Y.Z' or exact 'X.Y.Z'"
        )


def extract_category(raw: str) -> str | None:
    """Read the optional explicit category without inferring it from the ID/path."""
    match = CATEGORY_LINE_RE.search(raw)
    if not match:
        return None
    value = match.group(1).strip()
    quote = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote:
            if char == quote:
                if quote == "'" and index + 1 < len(value) and value[index + 1] == "'":
                    index += 1
                else:
                    quote = None
        elif char in "\\\"'":
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            value = value[:index].rstrip()
            break
        index += 1
    category = value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\\\"'" else value
    if not category.strip() or not CATEGORY_RE.fullmatch(category):
        raise SystemExit(f"category must be a simple label, got {category!r}")
    return category


def extract(pattern: re.Pattern[str], raw: str, field: str, path: Path) -> str:
    match = pattern.search(raw)
    if not match:
        raise SystemExit(f"{path}: missing top-level `{field}:` — not a step spec")
    return match.group(1)


def relative_file(path: Path, root: Path) -> str:
    """Return a portable repo-relative POSIX path for an indexed file."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        raise SystemExit(
            f"{path}: plugin files must be inside the repository root {root}"
        ) from None


def discover_plugin_files(plugin_dir: Path) -> list[Path]:
    """Return sorted YAML specs, excluding hidden paths and symlinks."""
    if plugin_dir.is_symlink() or not plugin_dir.is_dir():
        return []

    files: list[Path] = []
    for current, dirs, names in os.walk(plugin_dir, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".")
            and not (current_path / name).is_symlink()
        )
        for name in names:
            path = current_path / name
            if (
                name.startswith(".")
                or path.is_symlink()
                or path.suffix not in (".yaml", ".yml")
            ):
                continue
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(plugin_dir).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Paths resolve against the repo root (script's parent), so the script
    # behaves identically from any working directory.
    root = Path(__file__).resolve().parent.parent

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--output", default="index.json")
    parser.add_argument(
        "--no-meta",
        action="store_true",
        help="skip per-plugin meta.json output (CI dry runs)",
    )
    args = parser.parse_args()

    plugin_dir = resolve(args.plugins_dir)
    if not plugin_dir.is_symlink():
        plugin_dir = plugin_dir.resolve()
    try:
        plugin_dir.relative_to(root)
    except ValueError:
        raise SystemExit(f"{plugin_dir}: plugin directory must be inside repository root {root}") from None
    files = discover_plugin_files(plugin_dir)
    if not files:
        raise SystemExit(f"{plugin_dir}: no *.yaml/*.yml step specs found")

    steps = []
    seen: dict[tuple[str, str], str] = {}
    for path in files:
        raw = path.read_text(encoding="utf-8")
        step_id = extract(ID_RE, raw, "id", path)
        version = extract(VERSION_RE, raw, "version", path)
        category = extract_category(raw)
        meta = extract_meta(raw)
        check_requires_buz(meta, path)
        key = (step_id, version)
        if key in seen:
            raise SystemExit(
                f"{path}: duplicate id+version {key} (already in {seen[key]})"
            )
        seen[key] = str(path)
        entry = {
            "id": step_id,
            "version": version,
            "file": relative_file(path, root),
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
        if category:
            entry["category"] = category
        entry.update(meta)
        steps.append(entry)

    steps.sort(key=lambda s: (s["id"], s["version"]))
    index = {"steps": steps}
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"index.json: {len(steps)} step(s) written to {output}")

    # Per-plugin meta files (<plugin dir>/meta.json, repo-relative): the
    # manager's single-plugin refresh fetches one small file instead of the
    # whole index — cheap on intermittent networks. Same entry schema as the
    # index; file paths remain repo-relative.
    if args.no_meta:
        print("meta.json: skipped (--no-meta)")
    else:
        metas: dict[str, list[dict]] = {}
        for entry in steps:
            plugin_dir = (root / entry["file"]).parent
            metas.setdefault(str(plugin_dir), []).append(entry)
        for plugin_dir_str, entries in sorted(metas.items()):
            meta_path = Path(plugin_dir_str) / "meta.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "id": entries[0]["id"],
                        "versions": [
                            {key: value for key, value in e.items() if key != "id"}
                            for e in entries
                        ],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        print(f"meta.json: {len(metas)} plugin(s) written")


if __name__ == "__main__":
    sys.exit(main())
