#!/usr/bin/env python3
"""Decide whether the committed manifests materially differ from the specs.

Used by `.github/workflows/reconcile-manifests.yml`. A plain `git diff` is
too strict: `gen_reviews.py --auto` re-stamps every `ci` entry with today's
date and the current commit on each run, so byte comparison drifts daily
even when nothing in the catalog changed. Drift here means *material*
change:

- `index.json` or any `meta.json` changed (the catalog moved), or
- the review ledger gained/lost a `(id, version, sha256, source)` entry
  (a version arrived, disappeared, or its review was re-bound).

`reviewed_at` / `review_commit` / `scope` are deliberately ignored.

Exit codes: 0 = no material drift (safe to discard regeneration output),
1 = drift (as the workflow opens/updates the refresh PR).
"""

import json
import subprocess
import sys
from pathlib import Path


def resolve(path: str) -> Path:
    root = Path(__file__).resolve().parent.parent
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def ledger_material(data: dict) -> list[tuple[str, str, str, str]]:
    """The part of the ledger that binds reviews to content."""
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        raise SystemExit("reviews.json: expected a `reviews` array")
    return sorted(
        (
            str(entry.get("id")),
            str(entry.get("version")),
            str(entry.get("sha256", "")).lower(),
            str(entry.get("source", "")),
        )
        for entry in reviews
        if isinstance(entry, dict)
    )


def committed(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"cannot read HEAD:{path}: {result.stderr.strip()}")
    return result.stdout


def changed(pathspec: str) -> bool:
    """Whether regeneration touched `pathspec` — including untracked files.

    `git diff --quiet` ignores files that were never committed, so a missing
    `meta.json` (generated anew by `buz-plugin index`) would look clean. Porcelain
    status lists modified, staged, and untracked entries alike.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", pathspec],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def main() -> int:
    reasons: list[str] = []
    if changed("plugins/index.json"):
        reasons.append("index.json changed")
    if changed(":(glob)plugins/**/meta.json"):
        reasons.append("meta.json changed")

    old = ledger_material(json.loads(committed("plugins/reviews.json")))
    new = ledger_material(
        json.loads(resolve("plugins/reviews.json").read_text(encoding="utf-8"))
    )
    if old != new:
        added = [entry for entry in new if entry not in old]
        removed = [entry for entry in old if entry not in new]
        reasons.append(
            f"reviews.json material change (+{len(added)}/-{len(removed)} entries)"
        )
    if reasons:
        print("material drift: " + "; ".join(reasons))
        return 1
    print("no material drift — only regenerated timestamps differ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
