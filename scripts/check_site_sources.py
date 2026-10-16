#!/usr/bin/env python3
"""Verify published templates have working source links on static detail pages."""

import argparse
import json
import os
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


def template_filename(file_value: str) -> str:
    """Map a full indexed path to its matching static detail-page path."""
    parts = PurePosixPath(file_value.replace("\\", "/")).parts
    if parts and parts[0] == "plugins":
        parts = parts[1:]
    if not parts:
        return ""
    return PurePosixPath(*parts).with_suffix(".html").as_posix()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {"href": dict(attrs).get("href"), "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.anchors.append(self.current)
            self.current = None


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", default="dist", type=Path)
    args = parser.parse_args()

    bundle_path = args.dist_dir / "site-data.json"
    if not bundle_path.is_file():
        raise SystemExit(f"missing site data bundle: {bundle_path}")

    templates = json.loads(bundle_path.read_text(encoding="utf-8")).get("templates", [])
    errors = []
    checked = 0
    for tmpl in templates:
        source = tmpl.get("source_repo")
        if tmpl.get("publisher") == "official" and not source:
            errors.append(f"{tmpl.get('id')}: official template is missing source_repo")
            continue
        # The link must resolve to a real file in this repo — stale flat-layout
        # paths (plugins/buz-<name>.yaml) 404'd on the published site.
        if source and source.startswith("https://github.com/schiplat/buz-plugins/blob/master/"):
            rel = source.split("blob/master/", 1)[1]
            if not os.path.exists(os.path.join(repo_root(), rel)):
                errors.append(
                    f"{tmpl.get('id')}: source_repo path does not exist in the repo: {rel}"
                )
        if not source:
            continue

        if not isinstance(source, str):
            errors.append(f"{tmpl.get('id')}: source_repo must be a valid HTTPS URL: {source!r}")
            continue
        try:
            parsed = urlsplit(source)
            hostname = parsed.hostname
            parsed.port
        except ValueError:
            hostname = None
            parsed = None
        if (
            parsed is None
            or parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(char.isspace() for char in source)
            or "'" in source
            or '"' in source
        ):
            errors.append(f"{tmpl.get('id')}: source_repo must be a valid HTTPS URL: {source!r}")
            continue

        page_name = template_filename(tmpl.get("file", ""))
        page_path = args.dist_dir / "templates" / page_name
        if not page_path.is_file():
            errors.append(f"{tmpl.get('id')}: missing static detail page: {page_path}")
            continue

        links = Links()
        links.feed(page_path.read_text(encoding="utf-8"))
        if not any(link["href"] == source and link["text"].strip() == "Source repository" for link in links.anchors):
            errors.append(f"{tmpl.get('id')}: detail page is missing its source_repo link")
            continue
        checked += 1

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"source links: {checked}/{len(templates)} template detail page(s) verified")


if __name__ == "__main__":
    main()
