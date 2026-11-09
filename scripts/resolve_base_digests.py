#!/usr/bin/env python3
"""Rewrite Dockerfile `FROM` tags as `tag@sha256:<manifest-list digest>`.

Pins every `plugins/buz/*/image/Dockerfile` base image to the digest of the
manifest it currently resolves to, so rebuilding the same recipe is
deterministic until a base is deliberately refreshed. Re-running is the
refresh path: the tag stays readable, the digest is re-resolved and updated
only when upstream moved. Lines already carrying the current digest are left
byte-identical (idempotent).

Digest resolution talks to the image registry's manifest API and reports the
digest of the top-level manifest — for a multi-arch tag that is the manifest
list/index digest, so `FROM` stays platform-portable. Anonymous pulls only:
every base image is a public official image. Run from CI (the publish
runner reaches the registry); `--check` mode reports stale lines without
writing.

Stdlib only. Network failures are fatal — a half-pinned tree is worse than a
failed run (the caller opens one PR only when every base resolved).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILES = sorted((ROOT / "plugins").glob("buz/*/image/Dockerfile"))

FROM_RE = re.compile(r"^FROM\s+(\S+)(.*)$")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
# Top-level manifest types: OCI index, Docker manifest list, or a bare
# single-arch manifest (some tags publish no list).
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
])


def split_image_ref(image: str) -> tuple[str, str, str]:
    """Split an image reference into (registry, repo, tag).

    `debian:bookworm-slim` → docker.io + library/debian; named repos keep
    their path; an explicit registry host is honored; a digest is dropped
    (re-resolving the tag is the refresh path).
    """
    remainder = image
    registry = "docker.io"
    first, sep, rest = remainder.partition("/")
    if sep and ("." in first or ":" in first or first == "localhost"):
        registry = first
        remainder = rest
    remainder = remainder.partition("@")[0]  # drop any existing digest
    name, sep, tag = remainder.partition(":")
    if not sep:
        tag = ""
    if "/" not in name:
        name = f"library/{name}"
    return registry, name, tag or "latest"


def resolve_digest(registry: str, repo: str, tag: str) -> str:
    """Return the digest of the tag's top-level manifest (list/index/bare)."""
    if registry != "docker.io":
        raise SystemExit(f"unsupported registry {registry} — only docker.io bases are pinned")
    token = json.load(urllib.request.urlopen(
        "https://auth.docker.io/token?service=registry.docker.io"
        f"&scope=repository:{repo}:pull"
    ))["token"]
    request = urllib.request.Request(
        f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}",
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
    )
    with urllib.request.urlopen(request) as response:
        digest = response.headers.get("Docker-Content-Digest", "")
    if not (digest.startswith("sha256:") and DIGEST_RE.fullmatch(digest)):
        raise SystemExit(f"{repo}:{tag}: registry returned no usable digest ({digest!r})")
    return digest


def pin_file(path: Path, resolver, write: bool = True) -> list[tuple[str, str]]:
    """Rewrite the file's FROM lines; return (before, after) changed lines."""
    changed: list[tuple[str, str]] = []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = FROM_RE.match(line.rstrip("\n"))
        if not match:
            continue
        image, tail = match.group(1), match.group(2)
        if "@sha256:" in image:
            image = image.partition("@")[0]
        registry, repo, tag = split_image_ref(image)
        digest = resolver(registry, repo, tag)
        pinned = f"FROM {image}@{digest}{tail}\n"
        if pinned != line:
            changed.append((line.rstrip("\n"), pinned.rstrip("\n")))
            lines[index] = pinned
    if changed and write:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main(argv: list[str] | None = None, resolver=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when a FROM digest is missing or stale; write nothing",
    )
    args = parser.parse_args(argv)
    resolver = resolver or resolve_digest

    if not DOCKERFILES:
        raise SystemExit("no plugins/buz/*/image/Dockerfile found")
    stale: list[tuple[Path, str, str]] = []
    for path in DOCKERFILES:
        for before, after in pin_file(path, resolver, write=not args.check):
            stale.append((path, before, after))
            print(f"{path}: {before}\n  → {after}")
    if stale and args.check:
        raise SystemExit(f"{len(stale)} FROM line(s) stale or unpinned — run the pin pass")
    if not stale:
        print(f"{len(DOCKERFILES)} Dockerfile(s) already pin current digests")


if __name__ == "__main__":
    main()
