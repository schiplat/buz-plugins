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
        "someuser/telegram ...

Both modes read plugins/ + index.json (run scripts/gen_index.py first).
Manual entries are upserted by (id, version): a fresh review replaces only a
stale review for that version; reviews for older pinned versions and unrelated
records are preserved. Auto entries are rebuilt from the current index on every
run.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
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
    if not isinstance(index, dict) or not isinstance(index.get("steps"), list):
        raise SystemExit(f"{index_path}: expected a `steps` array")
    if not all(isinstance(step, dict) for step in index["steps"]):
        raise SystemExit(f"{index_path}: every step must be an object")
    if not all(
        all(key in step for key in ("id", "version", "sha256"))
        for step in index["steps"]
    ):
        raise SystemExit(f"{index_path}: each step needs id, version, and sha256")

    steps_by_pair: dict[tuple[str, str], dict] = {}
    for step in index["steps"]:
        steps_by_pair[(step["id"], step["version"])] = step
    return steps_by_pair


def auto_entries(args: argparse.Namespace) -> list[dict]:
    by_pair = load_index()
    official = [
        (step_id, version, step)
        for (step_id, version), step in by_pair.items()
        if step_id.startswith("buz/")
    ]
    if not official:
        raise SystemExit("no buz/* templates in index.json — nothing to auto-badge")
    return [
        {
            "id": step_id,
            "version": version,
            "sha256": step["sha256"],
            "reviewed_at": args.date,
            "review_commit": args.commit,
            "scope": AUTO_SCOPE,
            "source": AUTO_SOURCE,
            **({"category": step["category"]} if step.get("category") else {}),
        }
        for step_id, version, step in sorted(official)
    ]


def manual_entries(args: argparse.Namespace) -> list[dict]:
    by_pair = load_index()
    reviews = []
    for step_id in args.ids:
        candidates = [
            (version, entry)
            for (indexed_id, version), entry in by_pair.items()
            if indexed_id == step_id
        ]
        if not candidates:
            raise SystemExit(f"id {step_id!r} not present in index.json")
        version, entry = max(candidates, key=lambda candidate: semver_key(candidate[0]))
        reviews.append(
            {
                "id": entry["id"],
                "version": version,
                "sha256": entry["sha256"],
                "reviewed_at": args.date,
                "review_commit": args.commit,
                "scope": args.scope,
                "source": "human",
                **({"category": entry["category"]} if entry.get("category") else {}),
            }
        )
    return reviews


def semver_key(version: str) -> tuple[int, int, int]:
    """Return a numeric key for the index's strict major.minor.patch versions."""
    import re

    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version)
    if not match:
        raise SystemExit(f"index.json: invalid semantic version {version!r}")
    return tuple(int(part) for part in match.groups())


def merge_reviews(
    existing: list[dict], new_entries: list[dict], keep_manual: bool
) -> list[dict]:
    """Upsert exact content reviews without erasing unrelated evidence."""
    if keep_manual:
        replaced = {(entry["id"], entry["version"]) for entry in new_entries}
        retained = [
            entry
            for entry in existing
            if entry.get("source") != AUTO_SOURCE
            and (entry.get("id"), entry.get("version")) not in replaced
        ]
    else:
        replaced = {(entry["id"], entry["version"]) for entry in new_entries}
        retained = [
            entry
            for entry in existing
            if (entry.get("id"), entry.get("version")) not in replaced
        ]
    return new_entries + retained


def merge_and_write(new_entries: list[dict], keep_manual: bool) -> None:
    out_path = resolve("reviews.json")
    existing: list[dict] = []
    if out_path.exists():
        data = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
            raise SystemExit(f"{out_path}: expected a `reviews` array")
        existing = data["reviews"]
        if not all(isinstance(review, dict) for review in existing):
            raise SystemExit(f"{out_path}: every review must be an object")
    merged = merge_reviews(existing, new_entries, keep_manual)
    content = json.dumps({"reviews": merged}, indent=2, ensure_ascii=False) + "\n"
    # Write atomically so an interrupted command cannot truncate the trust file.
    fd, temporary = tempfile.mkstemp(prefix=".reviews.", dir=out_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, out_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    auto_n = sum(1 for r in merged if r.get("source") == AUTO_SOURCE)
    print(f"reviews.json: {len(merged)} entr(ies) ({auto_n} ci, {len(merged) - auto_n} human)")


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
