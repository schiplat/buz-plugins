#!/usr/bin/env python3
"""Generate reviews.json entries for officially reviewed templates (ADR §6.7.4).

Run this AFTER a maintainer has reviewed the exact file contents — the
entry binds the review to the content sha256, so any later content change
invalidates it automatically.

    python3 scripts/gen_reviews.py \
        --date 2026-10-04 --commit $(git rev-parse --short HEAD) \
        notify/feishu notify/dingtalk ...

Reads plugins/ + index.json (run scripts/gen_index.py first, or let this
script regenerate it). Emits a reviews.json containing only the requested
ids at their currently-indexed hashes — merge entries into the existing
reviews.json rather than overwriting it when appending.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="review date, e.g. 2026-10-04")
    parser.add_argument("--commit", required=True, help="review commit (short sha)")
    parser.add_argument(
        "--scope",
        default="static-lint + manual",
        help="what the review covered (shown to users)",
    )
    parser.add_argument("ids", nargs="+", help="template ids to emit entries for")
    args = parser.parse_args()

    index_path = Path("index.json")
    if not index_path.exists():
        raise SystemExit("index.json not found — run scripts/gen_index.py first")
    index = json.loads(index_path.read_text(encoding="utf-8"))

    by_id: dict[str, dict] = {}
    for step in index["steps"]:
        # Later entries win — gen_index sorts, so this keeps the highest
        # (id, version) pair for duplicate ids across versions.
        by_id[step["id"]] = step

    reviews = []
    for step_id in args.ids:
        entry = by_id.get(step_id)
        if entry is None:
            raise SystemExit(f"id {step_id!r} not present in index.json")
        reviews.append(
            {
                "id": entry["id"],
                "version": entry["version"],
                "sha256": entry["sha256"],
                "reviewed_at": args.date,
                "review_commit": args.commit,
                "scope": args.scope,
            }
        )

    out_path = Path("reviews.json")
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        known = {(r["id"], r["version"], r["sha256"]) for r in existing.get("reviews", [])}
        reviews = [
            r
            for r in reviews
            if (r["id"], r["version"], r["sha256"]) not in known
        ] + existing.get("reviews", [])
    out_path.write_text(
        json.dumps({"reviews": reviews}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"reviews.json: {len(reviews)} entr(ies)")


if __name__ == "__main__":
    sys.exit(main())
