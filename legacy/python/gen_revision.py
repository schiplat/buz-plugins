#!/usr/bin/env python3
"""Derive `plugins/revision.json` from the catalog published in the index.

`revision.json` is the mirror drift sentinel: the manager fetches it from the
canonical source and from each mirror and compares the two values for
**equality** (`check_mirror` in `crates/manager/src/services/plugin_pool.rs`).
It therefore needs a stable identity for the catalog, not a build marker.

The value is catalog-derived: the first 16 hex characters of sha256 over the
sorted `(id, version, sha256)` triples in `index.json`. Two trees publishing
the same versions with the same content hashes produce the same revision no
matter when, where, or by which generator (`buz-plugin index` or
`gen_index.py`) the index was written. Consequences:

- the committed copy cannot trail `HEAD`: it changes exactly when a published
  version arrives, disappears, or changes content;
- a mirror serving a different catalog is detectable with two tiny GETs, no
  index download;
- no write-back race: regeneration from the same catalog is byte-identical, so
  a bot commit that lands late (or never) cannot leave the tree stale.

`updated_at` mirrors the index's `issued_at` — display only; mirrors compare
`revision` alone.

Write order stays index → per-plugin `meta.json` → `revision.json` last, so a
mirror that observes a new revision knows the index beside it is complete.

Usage:

    python3 scripts/gen_revision.py            # write plugins/revision.json
    python3 scripts/gen_revision.py --print    # print the derived value only

Exit codes: 0 = written (or printed), 1 = unusable index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def resolve(path: str) -> Path:
    """Resolve against the repo root so the script runs from any cwd."""
    root = Path(__file__).resolve().parent.parent
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def catalog_revision(index: dict) -> str:
    """Content identity of one catalog: sha256 over sorted (id, version, sha256).

    Deliberately ignores `sequence`, `issued_at`, entry order, and every
    scalar field outside the content triple: those describe a *build*, and a
    sentinel that moves on every build would trail its source again.
    """
    steps = index.get("steps")
    if not isinstance(steps, list):
        raise SystemExit("index.json: expected a `steps` array")
    material = sorted(
        f"{step.get('id')}\0{step.get('version')}\0{str(step.get('sha256', '')).lower()}"
        for step in steps
        if isinstance(step, dict)
    )
    return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="plugins/index.json")
    parser.add_argument("--output", default="plugins/revision.json")
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the derived revision without writing revision.json",
    )
    args = parser.parse_args(argv)

    index_path = resolve(args.index)
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SystemExit(f"{index_path}: cannot read: {error}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"{index_path}: invalid JSON: {error}") from None
    if not isinstance(index, dict):
        raise SystemExit(f"{index_path}: expected a JSON object")

    revision = catalog_revision(index)
    if args.print_only:
        print(revision)
        return 0

    output_path = resolve(args.output)
    output_path.write_text(
        json.dumps(
            {"revision": revision, "updated_at": index.get("issued_at")},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"revision.json: {revision} written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
