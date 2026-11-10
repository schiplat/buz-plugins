#!/usr/bin/env python3
"""Verify the catalog a publish job is about to sign.

Both publishers — the site build on `master` and the snapshot release on a
tag — regenerate and sign `plugins/index.json`. The committed copy is the
single source of truth: `validate` already proves it matches the specs, so a
publisher must reproduce those exact entries and nothing else. Two kinds of
drift are possible, and neither is visible in the published artifact once the
bytes are out:

1. **Tool drift.** The pinned `buz-plugin` regenerates a catalog the committed
   copy does not contain — e.g. a tool release predating a field silently
   drops it (`deprecated`) and walks `sequence` forward. The release then
   disagrees with the site and with the reviewed manifest.
2. **Rollback.** The committed `sequence` is not ahead of what a previous
   release already published. A Manager refuses a lower sequence; at an equal
   sequence with different bytes it refuses the second catalog. The fix is
   always to reissue the committed index, never to sign around it.

Usage:

    python3 scripts/check_release_index.py \
        --committed "$RUNNER_TEMP/committed-index.json" \
        --generated plugins/index.json \
        --plugins-dir plugins \
        [--published "$RUNNER_TEMP/published/index.json"]

Exit codes: 0 = safe to sign, 1 = do not publish.
"""

import argparse
import json
import sys
from pathlib import Path

# Print this many field-level differences before collapsing to a count; the
# first few name the real cause, the rest are usually the same cause repeated.
MAX_DETAILS = 12


def load_json(path: str, label: str):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"{label}: {path}: missing")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"{label}: {path}: invalid JSON: {error}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"{label}: {path}: expected a JSON object")
    if not isinstance(data.get("steps"), list):
        raise SystemExit(f"{label}: {path}: expected a `steps` array")
    return data


def entry_key(step: dict) -> tuple:
    return (str(step.get("id")), str(step.get("version")))


def compare_entries(committed: dict, generated: dict) -> list:
    """Every field of every entry must match — this is the tool-drift gate."""
    errors = []
    left = {entry_key(step): step for step in committed["steps"]}
    right = {entry_key(step): step for step in generated["steps"]}

    for pair in sorted(set(left) - set(right)):
        errors.append(
            f"{pair[0]}@{pair[1]}: in the committed index but the regenerated "
            f"catalog dropped it"
        )
    for pair in sorted(set(right) - set(left)):
        errors.append(
            f"{pair[0]}@{pair[1]}: regenerated but not in the committed index — "
            f"regenerate and commit plugins/index.json first"
        )
    details = 0
    for pair in sorted(set(left) & set(right)):
        for field in sorted(set(left[pair]) | set(right[pair])):
            if left[pair].get(field) == right[pair].get(field):
                continue
            if details < MAX_DETAILS:
                errors.append(
                    f"{pair[0]}@{pair[1]}: field `{field}` is "
                    f"{right[pair].get(field)!r} in the regenerated index but "
                    f"{left[pair].get(field)!r} in the committed one"
                )
            details += 1
    if details > MAX_DETAILS:
        errors.append(f"... and {details - MAX_DETAILS} more field difference(s)")
    return errors


def compare_header(committed: dict, generated: dict) -> list:
    """Publishers sign the committed header; they never re-derive it."""
    errors = []
    if committed.get("sequence") != generated.get("sequence"):
        errors.append(
            f"sequence: regenerated {generated.get('sequence')!r} but the committed "
            f"index declares {committed.get('sequence')!r} — pass "
            f"`--sequence <committed>` so a publish never advances it implicitly"
        )
    if committed.get("issued_at") != generated.get("issued_at"):
        errors.append(
            f"issued_at: regenerated {generated.get('issued_at')!r} but the committed "
            f"index declares {committed.get('issued_at')!r} — pass "
            f"`--updated-at <committed>`"
        )
    return errors


def meta_errors(committed: dict, plugins_dir: str) -> list:
    """Per-plugin `meta.json` must be the committed index's projection.

    `meta.json` is the Manager's single-plugin refresh path, so a publish that
    drops a field there (a second generator is a second implementation!) is as
    harmful as one that drops it from the index. Expected entries are derived
    from the committed catalog — `{id, versions: [entry minus id]}` — not from
    the regenerated files, so a shared mistake in both writers is still caught
    by the index check above.
    """
    errors = []
    root = Path(plugins_dir)
    groups: dict = {}
    for step in committed["steps"]:
        rel = step.get("file")
        if not isinstance(rel, str) or not rel:
            errors.append(
                f"{step.get('id')}@{step.get('version')}: committed entry has no `file` path"
            )
            continue
        groups.setdefault(str(Path(rel).parent), []).append(step)

    for rel_dir, steps in sorted(groups.items()):
        meta_path = root / rel_dir / "meta.json"
        expected_id = str(steps[0].get("id"))
        expected = {}
        for step in steps:
            expected[str(step.get("version"))] = {
                key: value for key, value in step.items() if key != "id"
            }
        if not meta_path.exists():
            errors.append(
                f"{meta_path}: missing — the publish must ship the committed "
                f"per-plugin meta.json"
            )
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"{meta_path}: invalid JSON: {error}")
            continue
        if not isinstance(meta, dict):
            errors.append(f"{meta_path}: expected a JSON object")
            continue
        if meta.get("id") != expected_id:
            errors.append(
                f"{meta_path}: id {meta.get('id')!r} but the committed catalog says "
                f"{expected_id!r}"
            )
        versions = meta.get("versions")
        if not isinstance(versions, list):
            errors.append(f"{meta_path}: expected a `versions` array")
            continue
        actual = {
            str(entry.get("version")): entry
            for entry in versions
            if isinstance(entry, dict)
        }
        for version in sorted(set(expected) - set(actual)):
            errors.append(
                f"{meta_path}: version {version} is in the committed catalog but "
                f"missing from the regenerated meta"
            )
        for version in sorted(set(actual) - set(expected)):
            errors.append(
                f"{meta_path}: version {version} is in the regenerated meta but not "
                f"in the committed catalog"
            )
        for version in sorted(set(actual) & set(expected)):
            for field in sorted(set(expected[version]) | set(actual[version])):
                if expected[version].get(field) != actual[version].get(field):
                    errors.append(
                        f"{meta_path}: version {version} field `{field}` is "
                        f"{actual[version].get(field)!r} in the regenerated meta but "
                        f"{expected[version].get(field)!r} in the committed index"
                    )
    return errors


def check_published(committed: dict, published: dict) -> list:
    """Mirror the Manager's acceptance rule: sequence must never go back."""
    errors = []
    sequence = committed.get("sequence")
    published_sequence = published.get("sequence")
    if not isinstance(sequence, int):
        return [
            "committed index has no integer `sequence` — regenerate it with "
            "`python3 scripts/gen_index.py` and commit the result"
        ]
    if not isinstance(published_sequence, int):
        # A release that predates `sequence` could never have been accepted by
        # a Manager with rollback protection on, so it sets no watermark and
        # anchors nothing — skip it instead of blocking the first reissue.
        print(
            f"note: the published catalog has no integer `sequence` (predates "
            f"rollback protection) — no baseline to compare against",
            file=sys.stderr,
        )
        return []
    if sequence < published_sequence:
        errors.append(
            f"committed sequence {sequence} is behind the published release "
            f"(sequence {published_sequence}); a Manager refuses it as a rollback — "
            f"reissue with `python3 scripts/gen_index.py --sequence "
            f"{published_sequence + 1} --updated-at <now>` and commit the result"
        )
    elif sequence == published_sequence and committed != published:
        errors.append(
            f"committed sequence {sequence} was already published with different "
            f"content; a publisher must not sign two catalogs under one sequence — "
            f"reissue with `--sequence {published_sequence + 1}`"
        )
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--committed", required=True, help="the committed plugins/index.json")
    parser.add_argument("--generated", required=True, help="the freshly regenerated index.json")
    parser.add_argument(
        "--published",
        help="the previous release's index.json (enables the rollback check)",
    )
    parser.add_argument(
        "--plugins-dir",
        help="source root whose per-plugin meta.json must match the committed index",
    )
    args = parser.parse_args(argv)

    committed = load_json(args.committed, "committed")
    generated = load_json(args.generated, "generated")

    errors = compare_entries(committed, generated)
    errors.extend(compare_header(committed, generated))
    if args.plugins_dir:
        errors.extend(meta_errors(committed, args.plugins_dir))
    if args.published:
        errors.extend(check_published(committed, load_json(args.published, "published")))

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            f"\n{len(errors)} release-catalog inconsistency(ies) — refusing to sign. "
            f"This is a publisher/tool mismatch, not a catalog problem: bump the "
            f"pinned buz-plugin or reissue and commit plugins/index.json, never "
            f"edit the generated bytes.",
            file=sys.stderr,
        )
        return 1
    print(
        f"release catalog OK ({len(committed['steps'])} version(s), "
        f"sequence {committed.get('sequence')})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
