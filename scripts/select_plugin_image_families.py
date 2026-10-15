#!/usr/bin/env python3
"""Select Docker image families affected by commits in a push range."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

FAMILY_PATHS = {
    "oss-tools": ("plugins/buz/oss-upload",),
    "aws-tools": ("plugins/buz/s3-upload",),
    "rust-tools": ("plugins/buz/setup-rust",),
    "ruby-tools": ("plugins/buz/setup-ruby",),
    "php-tools": ("plugins/buz/setup-php",),
    "lua-tools": ("plugins/buz/setup-lua",),
    "python-tools": ("plugins/buz/setup-python",),
    "node-tools": ("plugins/buz/setup-node",),
    "java-tools": ("plugins/buz/setup-java",),
    "go-tools": ("plugins/buz/setup-go",),
}
SKIP_MARKER = "[skip image build]"
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout


def changed_paths(root: Path, commit: str) -> list[str]:
    parents = git(root, "show", "-s", "--format=%P", commit).split()
    if not parents:
        return git(
            root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
    return git(root, "diff", "--name-only", parents[0], commit).splitlines()


def select_families(root: Path, before: str, after: str) -> list[str]:
    if set(before) == {"0"}:
        commits = git(root, "rev-list", "--first-parent", "--reverse", after).splitlines()
    else:
        commits = git(
            root, "rev-list", "--first-parent", "--reverse", f"{before}..{after}"
        ).splitlines()

    families: set[str] = set()

    def collect(paths: list[str]) -> None:
        for path in paths:
            for family, (plugin_dir,) in FAMILY_PATHS.items():
                if path.startswith(f"{plugin_dir}/image/") or (
                    path.startswith(f"{plugin_dir}/")
                    and "/" not in path[len(plugin_dir) + 1 :]
                    and Path(path).suffix in {".yaml", ".yml"}
                ):
                    families.add(family)

    for commit in commits:
        message = git(root, "show", "-s", "--format=%B", commit)
        parents = git(root, "show", "-s", "--format=%P", commit).split()
        if len(parents) < 2:
            if SKIP_MARKER not in message:
                collect(changed_paths(root, commit))
            continue

        introduced = git(
            root, "rev-list", "--reverse", "--topo-order", commit, f"^{parents[0]}"
        ).splitlines()
        linear_introduced = []
        for introduced_commit in introduced:
            if introduced_commit == commit:
                continue
            introduced_parents = git(
                root, "show", "-s", "--format=%P", introduced_commit
            ).split()
            if len(introduced_parents) > 1:
                continue
            linear_introduced.append(introduced_commit)
            introduced_message = git(root, "show", "-s", "--format=%B", introduced_commit)
            if SKIP_MARKER not in introduced_message:
                collect(changed_paths(root, introduced_commit))
        if not linear_introduced and SKIP_MARKER not in message:
            collect(changed_paths(root, commit))

    return sorted(families)


def latest_template_version(root: Path, family: str) -> str:
    if family not in FAMILY_PATHS:
        raise ValueError(f"unsupported image family: {family}")
    plugin_dir = root / FAMILY_PATHS[family][0]
    versions = []
    for path in plugin_dir.iterdir():
        if not path.is_file() or path.suffix not in {".yaml", ".yml"}:
            continue
        match = VERSION_PATTERN.fullmatch(path.stem)
        if match:
            versions.append((tuple(int(part) for part in match.groups()), path.stem))
    if not versions:
        raise SystemExit(f"{plugin_dir}: no X.Y.Z plugin template versions found")
    return max(versions)[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    families = select_families(args.root.resolve(), args.before, args.after)
    versions = {
        family: latest_template_version(args.root.resolve(), family)
        for family in families
    }
    output = args.output or Path(os.environ.get("GITHUB_OUTPUT", "/dev/stdout"))
    with output.open("a", encoding="utf-8") as stream:
        stream.write(f"families={json.dumps(families)}\n")
        stream.write(f"versions={json.dumps(versions, sort_keys=True)}\n")


if __name__ == "__main__":
    raise SystemExit(main())
