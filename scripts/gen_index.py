#!/usr/bin/env python3
"""Generate index.json for the buz-plugin step index (marketplace ADR §6.1).

Walks plugins/*.yaml|yml, extracts the `id` / `version` top-level scalars,
hashes each file, and emits:

    { "steps": [ { "id": ..., "version": ..., "file": ..., "sha256": ... } ] }

Stdlib only (no PyYAML dependency). Invalid or duplicate entries fail the
run — generation happens in CI after `buz step validate` has already gated
the merge, so reaching this point with a broken spec is a bug.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^id:\s*[\"']?([A-Za-z0-9/._-]+)[\"']?\s*$", re.MULTILINE)
VERSION_RE = re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)[\"']?\s*$", re.MULTILINE)


def extract(pattern: re.Pattern[str], raw: str, field: str, path: Path) -> str:
    match = pattern.search(raw)
    if not match:
        raise SystemExit(f"{path}: missing top-level `{field}:` — not a step spec")
    return match.group(1)


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
    args = parser.parse_args()

    plugin_dir = resolve(args.plugins_dir)
    files = sorted(
        p for p in plugin_dir.iterdir() if p.suffix in (".yaml", ".yml")
    )
    if not files:
        raise SystemExit(f"{plugin_dir}: no *.yaml/*.yml step specs found")

    steps = []
    seen: dict[tuple[str, str], str] = {}
    for path in files:
        raw = path.read_text(encoding="utf-8")
        step_id = extract(ID_RE, raw, "id", path)
        version = extract(VERSION_RE, raw, "version", path)
        key = (step_id, version)
        if key in seen:
            raise SystemExit(
                f"{path}: duplicate id+version {key} (already in {seen[key]})"
            )
        seen[key] = str(path)
        steps.append(
            {
                "id": step_id,
                "version": version,
                "file": str(path),
                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            }
        )

    steps.sort(key=lambda s: (s["id"], s["version"]))
    index = {"steps": steps}
    output = resolve(args.output)
    Path(output).write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"index.json: {len(steps)} step(s) written to {output}")


if __name__ == "__main__":
    sys.exit(main())
