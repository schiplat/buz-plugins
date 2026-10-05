#!/usr/bin/env python3
"""Build the static-site data bundle: site/site-data.json (ADR §6.3).

The browse site is a single static page that renders this bundle — no
backend, no client-side YAML parsing. Also stages a deployable directory:

    site/
├── index.html / app.js / style.css   (committed)
├── site-data.json                    (generated)
├── index.json                        (copied — Phase 2 Manager sync endpoint)
├── plugins/*.yaml                    (copied — index `file` targets)
└── reviews.json                      (copied when present)

Requires PyYAML (CI installs it; the strict validator remains the Rust
`buz-manager step-validate` — this script only renders what already passed).
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SUMMARY_FIELDS = [
    "name",
    "description",
    "description_zh",
    "author",
    "author_url",
    "source_repo",
    "publisher",
    "license",
    "default_timeout",
    "requires_buz",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--reviews", default="reviews.json")
    parser.add_argument("--site-dir", default="site")
    parser.add_argument(
        "--dist-dir",
        default=None,
        help="Prebuilt frontend dist to seed the site dir with (Vue build output). "
        "When omitted, the committed static files in --site-dir are used.",
    )
    args = parser.parse_args()

    # Paths resolve against the repo root (script's grandparent), so the
    # script behaves identically from any working directory.
    root = Path(__file__).resolve().parent.parent

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    site_dir = resolve(args.site_dir)
    if args.dist_dir:
        dist = resolve(args.dist_dir)
        if dist.exists():
            shutil.rmtree(site_dir, ignore_errors=True)
            shutil.copytree(dist, site_dir)
    plugin_dir = resolve(args.plugins_dir)
    files = sorted(p for p in plugin_dir.iterdir() if p.suffix in (".yaml", ".yml"))
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    reviewed_hashes: dict[str, dict] = {}
    reviews_path = Path(args.reviews)
    if reviews_path.exists():
        for entry in json.loads(reviews_path.read_text(encoding="utf-8")).get("reviews", []):
            reviewed_hashes[entry["sha256"]] = entry

    templates = []
    seen: dict[tuple[str, str], str] = {}
    for path in files:
        raw = path.read_text(encoding="utf-8")
        spec = yaml.safe_load(raw)
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        key = (str(spec.get("id")), str(spec.get("version")))
        if key in seen:
            raise SystemExit(
                f"{path}: duplicate id+version {key} (already in {seen[key]}) — "
                "keep one file per id+version"
            )
        seen[key] = str(path)
        item = {
            "id": spec.get("id"),
            "version": spec.get("version"),
            "file": str(path),
            "sha256": sha,
            "engine": (spec.get("engine") or "shell").strip(),
            "keywords": spec.get("keywords") or [],
            "inputs": [
                {"name": name, **{k: v for k, v in fields.items()}}
                for name, fields in (spec.get("inputs") or {}).items()
            ],
            "reviewed": sha in reviewed_hashes,
            "reviewed_at": (reviewed_hashes.get(sha) or {}).get("reviewed_at"),
        }
        for field in SUMMARY_FIELDS:
            item[field] = spec.get(field)
        # Any future locale field (description_ja, description_ko, …) flows
        # into the bundle without touching this script.
        for key, value in spec.items():
            if key.startswith("description_") and value:
                item[key] = value
        templates.append(item)

    templates.sort(key=lambda t: (t["id"] or "", t["version"] or ""))
    site_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "templates": templates,
    }
    (site_dir / "site-data.json").write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Stage the rest of the deployable directory (Phase 2 Manager sync
    # consumes index.json and the raw plugin files from the same origin).
    index_path = root / "index.json"
    if not index_path.exists():
        raise SystemExit("index.json not found — run scripts/gen_index.py first")
    shutil.copy(index_path, site_dir / "index.json")
    plugins_out = site_dir / "plugins"
    if plugins_out.exists():
        shutil.rmtree(plugins_out)
    shutil.copytree(plugin_dir, plugins_out)
    if reviews_path.exists():
        shutil.copy(reviews_path, site_dir / "reviews.json")

    print(f"site: {len(templates)} template(s) → {site_dir}/")


if __name__ == "__main__":
    sys.exit(main())
