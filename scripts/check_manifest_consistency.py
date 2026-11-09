#!/usr/bin/env python3
"""Verify the generated manifests agree with each other.

`index.json` answers *what exists*; `reviews.json` answers *what was
approved*; `revision.json` names *which catalog this is*. Every version
published in the index must carry a review entry bound to the **same**
content sha256, and the sentinel must equal the catalog digest:

- a missing review entry means `require_reviewed` deployments reject that
  version (and a mirror trusting the index ships it unreviewed);
- a mismatched sha256 means the review predates a content change, so the
  badge no longer applies;
- a stale sentinel means mirrors compare a value that no longer describes
  this catalog. The value is catalog-derived (`scripts/gen_revision.py`), so
  this is always "forgot to regenerate", never a build-order race.

This runs in the `validate` job. Reviews are refreshed by
`scripts/gen_reviews.py --auto` (blessed ids) or a manual first review
(new ids); the fix for a failure is always to regenerate and commit the
manifest, never to edit hashes by hand.

Usage:

    python3 scripts/check_manifest_consistency.py

Exit codes: 0 = consistent (warnings allowed), 1 = inconsistencies.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def resolve(path: str) -> Path:
    """Resolve against the repo root so the script runs from any cwd."""
    root = Path(__file__).resolve().parent.parent
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"{path}: missing — generated manifests must be committed")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: invalid JSON: {error}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return data


def catalog_revision(index: dict) -> str:
    """Content identity of one catalog — see `scripts/gen_revision.py`.

    Kept in sync with that script on purpose (both derive the same value from
    the same `(id, version, sha256)` triples); a test pins the two together so
    they cannot drift apart unnoticed.
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


def check_revision(index: dict, revision: dict) -> list[str]:
    """The sentinel must name the catalog this index publishes."""
    expected = catalog_revision(index)
    actual = revision.get("revision")
    if actual == expected:
        return []
    return [
        f"revision.json: stale sentinel {actual!r}, expected {expected!r} for this "
        f"catalog — run `python3 scripts/gen_revision.py` and commit the result"
    ]


def check(index: dict, reviews: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one index/ledger pair."""
    errors: list[str] = []
    warnings: list[str] = []

    steps = index.get("steps")
    if not isinstance(steps, list):
        return ["index.json: expected a `steps` array"], warnings
    entries = reviews.get("reviews")
    if not isinstance(entries, list):
        return ["reviews.json: expected a `reviews` array"], warnings

    published: dict[tuple[str, str], str] = {}
    for step in steps:
        if not isinstance(step, dict) or not all(
            key in step for key in ("id", "version", "sha256")
        ):
            errors.append(f"index.json: entry without id/version/sha256: {step!r}")
            continue
        pair = (str(step["id"]), str(step["version"]))
        sha = str(step["sha256"]).lower()
        if not SHA256_RE.fullmatch(sha):
            errors.append(
                f"{pair[0]}@{pair[1]}: index sha256 is not 64 lowercase hex chars: {sha!r}"
            )
        if pair in published:
            errors.append(
                f"{pair[0]}@{pair[1]}: duplicate index entry — one (id, version) must be one file"
            )
        published[pair] = sha

    reviewed: dict[tuple[str, str], str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"reviews.json: entry is not an object: {entry!r}")
            continue
        pair = (str(entry.get("id")), str(entry.get("version")))
        sha = str(entry.get("sha256", "")).lower()
        if pair in reviewed and reviewed[pair] != sha:
            errors.append(
                f"{pair[0]}@{pair[1]}: conflicting review entries bind different sha256 "
                f"({reviewed[pair]}, {sha}) — keep exactly one"
            )
        reviewed[pair] = sha

    reviewed_ids = {entry.get("id") for entry in entries if isinstance(entry, dict)}
    for pair, sha in sorted(published.items()):
        if pair not in reviewed:
            if pair[0] in reviewed_ids:
                errors.append(
                    f"{pair[0]}@{pair[1]}: no review entry — refresh the ledger with "
                    f"`python3 scripts/gen_reviews.py --auto` and commit reviews.json"
                )
            else:
                errors.append(
                    f"{pair[0]}@{pair[1]}: no review entry and this id has no first review — "
                    f"review the exact file, then record it with "
                    f"`python3 scripts/gen_reviews.py --date <YYYY-MM-DD> "
                    f"--commit <sha> --scope '<what you checked>' {pair[0]}`"
                )
        elif reviewed[pair] != sha:
            errors.append(
                f"{pair[0]}@{pair[1]}: review binds sha256 {reviewed[pair]} but the index "
                f"publishes {sha} — the content changed after review; re-review and refresh "
                f"the ledger"
            )

    for pair in sorted(reviewed):
        if pair not in published:
            warnings.append(
                f"{pair[0]}@{pair[1]}: review entry with no matching index version "
                f"(removed or pinned version) — kept for audit"
            )

    return errors, warnings


def check_meta(index: dict, plugins_root: Path) -> tuple[list[str], list[str]]:
    """Every indexed version must appear in its plugin's `meta.json` unchanged.

    `meta.json` is the per-plugin manifest Manager fetches for a single-plugin
    refresh; a stale or missing copy advertises a version (or hash) the index
    no longer agrees with. This is a content check, so it also catches files
    that were never committed (which `git diff` cannot see).
    """
    errors: list[str] = []
    warnings: list[str] = []
    steps = index.get("steps")
    if not isinstance(steps, list):
        return errors, warnings

    for step in steps:
        if not isinstance(step, dict):
            continue
        pair = (str(step.get("id")), str(step.get("version")))
        file_rel = step.get("file")
        if not isinstance(file_rel, str) or not file_rel:
            errors.append(f"{pair[0]}@{pair[1]}: index entry has no `file` path")
            continue
        meta_path = plugins_root / Path(file_rel).parent / "meta.json"
        display = meta_path.relative_to(plugins_root.parent)
        if not meta_path.exists():
            errors.append(
                f"{pair[0]}@{pair[1]}: {display} is missing — "
                f"run `python3 scripts/gen_index.py` and commit it"
            )
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"{display}: invalid JSON: {error}")
            continue
        if meta.get("id") != pair[0]:
            errors.append(
                f"{display}: declares id {meta.get('id')!r}, expected {pair[0]!r}"
            )
        versions = meta.get("versions")
        if not isinstance(versions, list):
            errors.append(f"{display}: expected a `versions` array")
            continue
        entry = next(
            (
                candidate
                for candidate in versions
                if isinstance(candidate, dict)
                and str(candidate.get("version")) == pair[1]
            ),
            None,
        )
        if entry is None:
            errors.append(
                f"{pair[0]}@{pair[1]}: not listed in {display} — "
                f"run `python3 scripts/gen_index.py` and commit it"
            )
            continue
        meta_sha = str(entry.get("sha256", "")).lower()
        index_sha = str(step.get("sha256", "")).lower()
        if meta_sha != index_sha:
            errors.append(
                f"{pair[0]}@{pair[1]}: meta.json binds sha256 {meta_sha} but the index "
                f"publishes {index_sha} — regenerate the manifest"
            )

    return errors, warnings


def main() -> int:
    index = load_json(resolve("plugins/index.json"))
    errors, warnings = check(
        index,
        load_json(resolve("plugins/reviews.json")),
    )
    errors.extend(check_revision(index, load_json(resolve("plugins/revision.json"))))
    meta_errors, meta_warnings = check_meta(index, resolve("plugins"))
    errors.extend(meta_errors)
    warnings.extend(meta_warnings)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            f"\n{len(errors)} manifest inconsistency(ies) — index, reviews, and meta must agree",
            file=sys.stderr,
        )
        return 1
    print("manifests consistent (reviews cover every indexed version)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
