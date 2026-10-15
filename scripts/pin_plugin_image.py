#!/usr/bin/env python3
"""Prepare an immutable plugin spec update for a published image digest."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "oss-tools": (
        "buz/oss-upload",
        "docker.io/schiplat/buz-plugins-oss-tools",
        "plugins/buz/oss-upload",
    ),
    "aws-tools": (
        "buz/s3-upload",
        "docker.io/schiplat/buz-plugins-aws-tools",
        "plugins/buz/s3-upload",
    ),
    "rust-tools": (
        "buz/setup-rust",
        "docker.io/schiplat/buz-plugins-rust-tools",
        "plugins/buz/setup-rust",
    ),
    "ruby-tools": (
        "buz/setup-ruby",
        "docker.io/schiplat/buz-plugins-ruby-tools",
        "plugins/buz/setup-ruby",
    ),
    "php-tools": (
        "buz/setup-php",
        "docker.io/schiplat/buz-plugins-php-tools",
        "plugins/buz/setup-php",
    ),
    "lua-tools": (
        "buz/setup-lua",
        "docker.io/schiplat/buz-plugins-lua-tools",
        "plugins/buz/setup-lua",
    ),
    "python-tools": (
        "buz/setup-python",
        "docker.io/schiplat/buz-plugins-python-tools",
        "plugins/buz/setup-python",
    ),
    "node-tools": (
        "buz/setup-node",
        "docker.io/schiplat/buz-plugins-node-tools",
        "plugins/buz/setup-node",
    ),
    "java-tools": (
        "buz/setup-java",
        "docker.io/schiplat/buz-plugins-java-tools",
        "plugins/buz/setup-java",
    ),
    "go-tools": (
        "buz/setup-go",
        "docker.io/schiplat/buz-plugins-go-tools",
        "plugins/buz/setup-go",
    ),
}
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def pin_spec(root: Path, family: str, digest: str) -> Path | None:
    if family not in FAMILIES:
        raise SystemExit(f"unsupported image family: {family}")
    if not DIGEST_RE.fullmatch(digest):
        raise SystemExit("image digest must be a lowercase sha256 digest")

    step_id, image, relative_dir = FAMILIES[family]
    plugin_dir = root / relative_dir
    versions: list[tuple[tuple[int, int, int], Path, dict, str]] = []
    for path in plugin_dir.glob("*.yaml"):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or spec.get("id") != step_id:
            continue
        version = spec.get("version")
        match = VERSION_RE.fullmatch(str(version))
        if not match or path.name != f"{version}.yaml":
            raise SystemExit(f"{path}: version must match its X.Y.Z filename")
        reference = spec.get("image")
        if not isinstance(reference, str) or not reference.startswith(f"{image}:") and not re.fullmatch(
            re.escape(image) + r"@sha256:[0-9a-f]{64}", reference
        ):
            raise SystemExit(f"{path}: image reference does not match {image}")
        versions.append((tuple(map(int, match.groups())), path, spec, reference))

    if not versions:
        raise SystemExit(f"no template versions found for {step_id}")
    if len({item[0] for item in versions}) != len(versions):
        raise SystemExit(f"duplicate template version found for {step_id}")
    versions.sort(key=lambda item: item[0])
    current_tuple, current_path, current_spec, current_reference = versions[-1]
    target_reference = f"{image}@{digest}"
    if current_reference == target_reference:
        print(f"{step_id}@{current_spec['version']} already pins {digest}", file=sys.stderr)
        return None

    if current_reference == f"{image}:1.0.0" and current_tuple == (1, 0, 0):
        target_path = current_path
        target_version = "1.0.0"
        text = current_path.read_text(encoding="utf-8")
    else:
        current_digest = current_reference.partition("@sha256:")[2]
        if not DIGEST_RE.fullmatch(f"sha256:{current_digest}"):
            raise SystemExit(f"{current_path}: refusing to replace an existing non-initial image tag")
        target_version = f"{current_tuple[0]}.{current_tuple[1]}.{current_tuple[2] + 1}"
        target_path = plugin_dir / f"{target_version}.yaml"
        if target_path.exists():
            raise SystemExit(f"refusing to overwrite existing template version: {target_path}")
        text = current_path.read_text(encoding="utf-8")
        substitutions = (
            (r"(?m)^version:\s*[^\n]+$", f"version: {target_version}"),
            (
                r"(?m)^source_repo:\s*[^\n]+$",
                f"source_repo: https://github.com/schiplat/buz-plugins/blob/master/{relative_dir}/{target_version}.yaml",
            ),
        )
        for pattern, replacement in substitutions:
            text, count = re.subn(pattern, replacement, text, count=1)
            if count != 1:
                raise SystemExit(f"{current_path}: expected exactly one matching field for {pattern}")

    text, count = re.subn(r"(?m)^image:\s*[^\n]+$", f"image: {target_reference}", text, count=1)
    if count != 1:
        raise SystemExit(f"{current_path}: expected exactly one image field")
    updated_spec = yaml.safe_load(text)
    if updated_spec.get("id") != step_id or updated_spec.get("version") != target_version:
        raise SystemExit(f"generated template identity is invalid: {target_path}")
    if updated_spec.get("image") != target_reference:
        raise SystemExit(f"generated image pin is invalid: {target_path}")

    target_path.write_text(text, encoding="utf-8")
    print(f"prepared {step_id}@{target_version} with {target_reference}")
    return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=sorted(FAMILIES))
    parser.add_argument("--digest", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    pin_spec(args.root.resolve(), args.family, args.digest)


if __name__ == "__main__":
    main()
