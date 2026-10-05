#!/usr/bin/env python3
"""Generate reviews.json entries (ADR §6.7.4 + §6.7.6).

Two entry kinds live in reviews.json, distinguished by `source`:

- `ci`   — official templates (`buz/*`). Trust model: the same org writes
  and reviews these, so a human sign-off adds no independent signal.
  Instead, green CI is the gate: step-validate + lint_runs + egress
  allowlist all passing on the exact content hash. Entries carry
  `source: "ci"` and are REGENERATED on every run — never hand-edited.
- `human`— community templates. Human review is mandatory (CI green is a
  prerequisite, never a substitute). Emit entries with the manual mode
  below AFTER reviewing the exact file contents; the entry binds the
  review to the content sha256, so any later content change invalidates
  it automatically.

Auto mode (official):

    python3 scripts/gen_reviews.py --auto [--commit <sha>] [--date YYYY-MM-DD]

Manual mode (community, human-reviewed):

    python3 scripts/gen_reviews.py \
        --date 2026-10-04 --commit $(git rev-parse --short HEAD) \
        someuser/notify/telegram ...

Both modes read plugins/ + index.json (run scripts/gen_index.py first).
Manual entries are always preserved; auto entries are rebuilt from the
current index on every run.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AUTO_SOURCE = "ci"
AUTO_SCOPE = "official-ci: validate + lint_runs + egress allowlist on green master"


def resolve(path: str) -> Path:
    """Resolve against the repo root so the script runs from any cwd."""
    root = Path(__file__).resolve().parent.parent
    p = Path(path)
    return p if p.is_absolute() else root / p


def load_index() -> dict[str, dict]:
    index_path = resolve("index.json")
    if not index_path.exists():
        raise SystemExit("index.json not found — run scripts/gen_index.py first")
    index = json.loads(index_path.read_text(encoding="utf-8"))

    by_id: dict[str, dict] = {}
    for step in index["steps"]:
        # Later entries win — gen_index sorts, so this keeps the highest
        # (id, version) pair for duplicate ids across versions.
        by_id[step["id"]] = step
    return by_id


def auto_entries(args: argparse.Namespace) -> list[dict]:
    by_id = load_index()
    official = {sid: step for sid, step in by_id.items() if sid.startswith("buz/")}
    if not official:
        raise SystemExit("no buz/* templates in index.json — nothing to auto-badge")
    return [
        {
            "id": sid,
            "version": step["version"],
            "sha256": step["sha256"],
            "reviewed_at": args.date,
            "review_commit": args.commit,
            "scope": AUTO_SCOPE,
            "source": AUTO_SOURCE,
        }
        for sid, step in sorted(official.items())
    ]


def manual_entries(args: argparse.Namespace) -> list[dict]:
    by_id = load_index()
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
    return reviews


def merge_and_write(new_entries: list[dict], keep_manual: bool) -> None:
    out_path = resolve("reviews.json")
    manual: list[dict] = []
    if keep_manual and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        known = {(r["id"], r["version"], r["sha256"]) for r in new_entries}
        manual = [
            r
            for r in existing.get("reviews", [])
            if r.get("source") != AUTO_SOURCE and (r["id"], r["version"], r["sha256"]) not in known
        ]
    merged = new_entries + manual
    out_path.write_text(
        json.dumps({"reviews": merged}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    auto_n = sum(1 for r in merged if r.get("source") == AUTO_SOURCE)
    print(f"reviews.json: {len(merged)} entr(ies) ({auto_n} ci, {len(manual)} human)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="regenerate entries for all buz/* templates (official CI gate)",
    )
    parser.add_argument("--date", help="review date, e.g. 2026-10-04 (auto: today UTC)")
    parser.add_argument(
        "--commit", help="review commit, e.g. short sha (auto: current HEAD)"
    )
    parser.add_argument(
        "--scope",
        default="static-lint + manual",
        help="what the human review covered (manual mode, shown to users)",
    )
    parser.add_argument(
        "ids", nargs="*", help="template ids to emit manual entries for"
    )
    args = parser.parse_args()

    if not args.date:
        if not args.auto:
            parser.error("--date is required for manual mode")
        args.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not args.commit:
        if not args.auto:
            parser.error("--commit is required for manual mode")
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode != 0:
            raise SystemExit("--commit required outside a git repository")
        args.commit = head.stdout.strip()

    if args.auto:
        if args.ids:
            parser.error("ids are manual-mode only — use --auto without ids")
        merge_and_write(auto_entries(args), keep_manual=True)
    else:
        if not args.ids:
            parser.error("manual mode needs at least one template id")
        merge_and_write(manual_entries(args), keep_manual=False)


if __name__ == "__main__":
    sys.exit(main())
