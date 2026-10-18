#!/usr/bin/env python3
"""Build the static-site data bundle: dist/site-data.json (ADR §6.3).

The browse site is a single static page that renders this bundle — no
backend, no client-side YAML parsing. Also stages the deployable
directory (`dist/` — what `wrangler pages deploy dist` ships):

    dist/
├── index.html / assets/*             (Vue build output from frontend/)
├── site-data.json                    (generated)
├── templates/*.html                  (generated — crawlable per-template pages)
├── robots.txt / sitemap.xml          (generated)
├── index.json                        (copied — Phase 2 Manager sync endpoint)
├── plugins/*.yaml                    (copied — index `file` targets)
└── reviews.json                      (copied when present)

Requires PyYAML (CI installs it; the strict validator remains the Rust
`buz-manager step-validate` — this script only renders what already passed).
"""

import argparse
import hashlib
import json
import os
import posixpath
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional

import yaml

SITE_URL = "https://plugins.buz.schiplat.com"

SUMMARY_FIELDS = [
    "name",
    "category",
    "description",
    "description_zh",
    "author",
    "author_url",
    "source_repo",
    "publisher",
    "license",
    "default_timeout",
    "default_dir",
    "requires_buz",
    "capabilities",
]

GA_SNIPPET = (
    '<script async src="https://www.googletagmanager.com/gtag/js?id=G-71C16BC1N6"></script>\n'
    "<script>\n"
    "  window.dataLayer = window.dataLayer || [];\n"
    "  function gtag(){dataLayer.push(arguments);}\n"
    "  gtag('js', new Date());\n"
    "  gtag('config', 'G-71C16BC1N6');\n"
    "</script>"
)


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def description_for(tmpl: dict, lang: str) -> str:
    primary = f"description_{lang}"
    return tmpl.get(primary) or tmpl.get("description") or ""


def usage_example(tmpl: dict) -> str:
    lines = [
        f"- name: {str(tmpl['id']).split('/')[-1]}",
        f"  uses: {tmpl['id']}@{tmpl['version']}",
    ]
    required = [item for item in tmpl.get("inputs", []) if item.get("required")]
    if required:
        lines.append("  with:")
        lines.extend(f"    {item['name']}: " for item in required)
    if tmpl.get("default_dir"):
        # Harness template: the engine selects the step directory from
        # default_dir (a step-level work_dir overrides it) and Buz appends
        # the caller's commands after the template's own setup.
        lines.append("  run: |")
        lines.append("    # your commands — executed after the template setup")
    return "\n".join(lines)


def template_filename(file_value: str) -> str:
    """Map a full indexed path to a unique detail-page path."""
    parts = PurePosixPath(file_value.replace("\\", "/")).parts
    if parts and parts[0] == "plugins":
        parts = parts[1:]
    if not parts:
        raise ValueError(f"invalid plugin file path: {file_value!r}")
    return PurePosixPath(*parts).with_suffix(".html").as_posix()


def page_relative_links(file_value: str) -> tuple[str, str, str]:
    """Return the home, favicon, and stylesheet URLs from a detail page."""
    page_path = PurePosixPath("templates") / template_filename(file_value)
    page_dir = page_path.parent.as_posix()
    prefix = posixpath.relpath(".", page_dir)
    if prefix != ".":
        prefix += "/"
    else:
        prefix = ""
    return prefix, f"{prefix}favicon.svg", f"{prefix}style.css"


def discover_plugin_files(plugin_dir: Path) -> list[Path]:
    """Return sorted YAML specs, excluding hidden paths and symlinks."""
    if plugin_dir.is_symlink() or not plugin_dir.is_dir():
        return []

    files: list[Path] = []
    for current, dirs, names in os.walk(plugin_dir, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".")
            and not (current_path / name).is_symlink()
        )
        for name in names:
            path = current_path / name
            if (
                name.startswith(".")
                or path.is_symlink()
                or path.suffix not in (".yaml", ".yml")
            ):
                continue
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(plugin_dir).as_posix())


def jsonld_software(tmpl: dict) -> str:
    template_path = template_filename(tmpl["file"])
    payload = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": tmpl.get("name") or tmpl["id"],
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Any",
        "softwareVersion": tmpl.get("version"),
        "description": description_for(tmpl, "en"),
        "author": {"@type": "Organization", "name": tmpl.get("author") or "Buz"},
        "license": tmpl.get("license") or "Apache-2.0",
        "url": f"{SITE_URL}/templates/{template_path}",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def template_page_html(tmpl: dict) -> str:
    template_id = tmpl["id"]
    name = tmpl.get("name") or template_id
    desc_en = description_for(tmpl, "en")
    template_path = template_filename(tmpl["file"])
    page_url = f"{SITE_URL}/templates/{template_path}"
    home_href, favicon_href, stylesheet_href = page_relative_links(tmpl["file"])

    input_rows = "".join(
        f"<tr><td class='mono'>{esc(i.get('name'))}</td>"
        f"<td>{esc(i.get('type') or 'string')}</td>"
        f"<td>{'yes' if i.get('required') else 'no'}</td>"
        f"<td>{'yes' if i.get('masking') else 'no'}</td>"
        f"<td class='dim'>{esc(i.get('description') or '')}</td></tr>"
        for i in tmpl.get("inputs", [])
    )
    inputs_html = (
        f"<table class='inputs'><thead><tr><th>Name</th><th>Type</th><th>Required</th>"
        f"<th>Masking</th><th>Description</th></tr></thead><tbody>{input_rows}</tbody></table>"
        if input_rows
        else "<p class='dim'>This template takes no inputs.</p>"
    )

    usage = esc(usage_example(tmpl))
    jsonld = jsonld_software(tmpl)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="icon" type="image/svg+xml" href="{favicon_href}" />
<title>{esc(name)} — Buz Plugins Marketplace</title>
<meta name="description" content="{esc(desc_en[:160])}" />
<link rel="canonical" href="{esc(page_url)}" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{esc(name)} — Buz Plugins Marketplace" />
<meta property="og:description" content="{esc(desc_en[:160])}" />
<meta property="og:url" content="{esc(page_url)}" />
<meta name="twitter:card" content="summary" />
<script type="application/ld+json">
{jsonld}
</script>
<link rel="stylesheet" href="{stylesheet_href}" />
{GA_SNIPPET}
</head>
<body class="template-page">
<header class="top"><div class="wrap"><a class="home" href="{home_href}">&larr; Buz Plugins Marketplace</a></div></header>
<main class="wrap">
<h1>{esc(name)}</h1>
<p class="mono dim">{esc(template_id)} · v{esc(tmpl['version'])} · {esc(tmpl['engine'])}</p>
<p>{esc(desc_en)}</p>
<h2>Inputs</h2>
{inputs_html}
<h2>Usage</h2>
<pre class="code">{usage}</pre>
<h2>Integrity</h2>
    <p class="mono dim small">sha256: {tmpl['content_sha256']}</p>
    {f"<p>Capabilities: {esc(', '.join(tmpl.get('capabilities') or []))}</p>" if tmpl.get('capabilities') else ""}
    {f"<p>Requires Buz: {esc(tmpl['requires_buz'])}</p>" if tmpl.get('requires_buz') else ""}
<p class="dim small">{esc('Officially reviewed at this content hash' if tmpl.get('reviewed') else 'Not yet officially reviewed — the badge on the marketplace reflects the current review status')}.</p>
<p><a href="https://github.com/schiplat/buz-plugins/issues/new?template=report.yml">Report an issue with this template</a>{f" · <a href='{esc(tmpl['source_repo'])}'>Source repository</a>" if tmpl.get('source_repo') else ""}</p>
<p><a href="{home_href}">Browse all templates</a></p>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Paths resolve against the repo root (script's parent), so the
    # script behaves identically from any working directory.
    root = Path(__file__).resolve().parent.parent

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--reviews", default="reviews.json")
    parser.add_argument("--out-dir", default="dist", help="Deployable output directory")
    parser.add_argument(
        "--dist-dir",
        default=None,
        help="Prebuilt frontend dist to seed the output dir with (Vue build "
        "output from frontend/dist). When omitted, the committed static "
        "files in --out-dir are used.",
    )
    args = parser.parse_args()

    out_dir = resolve(args.out_dir)
    if args.dist_dir:
        dist = resolve(args.dist_dir)
        if dist.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            shutil.copytree(dist, out_dir)
    plugin_dir = resolve(args.plugins_dir)
    if not plugin_dir.is_symlink():
        plugin_dir = plugin_dir.resolve()
    files = discover_plugin_files(plugin_dir)
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    reviewed_hashes: dict[str, dict] = {}
    reviews_path = resolve(args.reviews)
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
            "file": path.resolve().relative_to(root.resolve()).as_posix(),
            "content_sha256": sha,
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
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "templates": templates,
    }
    (out_dir / "site-data.json").write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Per-template static pages (crawlable + shareable landing pages).
    templates_dir = out_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    page_urls = []
    for tmpl in templates:
        page = template_page_html(tmpl)
        page_file = templates_dir / template_filename(tmpl["file"])
        page_file.parent.mkdir(parents=True, exist_ok=True)
        page_file.write_text(page, encoding="utf-8")
        page_urls.append(f"{SITE_URL}/templates/{template_filename(tmpl['file'])}")

    # robots.txt + sitemap.xml
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    sitemap_entries = [f"  <url><loc>{SITE_URL}/</loc></url>"]
    sitemap_entries += [f"  <url><loc>{u}</loc></url>" for u in page_urls]
    (out_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(sitemap_entries)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    # Stage the rest of the deployable directory (Phase 2 Manager sync
    # consumes index.json and the raw plugin files from the same origin).
    index_path = root / "index.json"
    if not index_path.exists():
        raise SystemExit("index.json not found — run scripts/gen_index.py first")
    shutil.copy(index_path, out_dir / "index.json")
    for path in files:
        try:
            indexed_relative_path = path.resolve().relative_to(root.resolve())
        except ValueError:
            if args.plugins_dir != "plugins":
                raise SystemExit(
                    f"{path}: plugin files must be inside the repository root {root}"
                ) from None
            indexed_relative_path = PurePosixPath("plugins") / path.relative_to(plugin_dir)
        staged_path = out_dir / Path(indexed_relative_path)
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, staged_path)
    if reviews_path.exists():
        shutil.copy(reviews_path, out_dir / "reviews.json")

    print(
        f"site: {len(templates)} template(s) → {out_dir}/ "
        f"(+{len(templates)} template pages, robots.txt, sitemap.xml)"
    )


if __name__ == "__main__":
    sys.exit(main())
