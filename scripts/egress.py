#!/usr/bin/env python3
"""Extract declared outbound endpoints from step-template run blocks.

Machine-review evidence (ADR §6.7.6, machine step 3): for every
plugins/*.yaml, parse the `run:` block and pull out every URL and network
host the script touches. The reviewer's job shrinks to judging whether the
declared endpoint list is sensible for what the template claims to do.

Prints a human-readable table, optionally writes machine-readable evidence
JSON, and can enforce `--expect egress-allowlist.json`: for official
(`buz/*`) templates the extracted surface must stay within the reviewed
baseline, which is what lets green CI stand in for a human sign-off
(ADR §6.7.6). Stdlib only; paths resolve against the repo root so it runs
from any working directory.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

URL_RE = re.compile(r"""https?://[^\s'"<>\\]+""", re.IGNORECASE)
# Input names that smell like a network endpoint (webhook, url, host, …):
# their values are runtime-supplied, so static extraction can't see the
# actual destination — flag them as declared runtime egress instead.
ENDPOINT_INPUT_RE = re.compile(r"webhook|url|host|endpoint|server|addr|api", re.IGNORECASE)


def run_block(spec: dict) -> str:
    return spec.get("run") or ""


def check_allowlist(evidence: list[dict], allow_path: Path) -> list[str]:
    """Compare extracted egress against the reviewed baseline.

    Shape of egress-allowlist.json:
        { "<template-id>": { "hosts": [...], "endpoint_inputs": [...] } }

    Only `buz/*` templates are enforced — community templates are human-
    reviewed as a whole and have no allowlist obligation. Hosts are a
    subset check (the allowlist is an upper bound); endpoint inputs must
    match exactly, because a new network-touching input is precisely the
    kind of change a reviewer has to see.
    """
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for entry in evidence:
        tid = entry["id"] or ""
        if not tid.startswith("buz/"):
            continue
        rule = allow.get(tid)
        if rule is None:
            violations.append(f"{tid}: no allowlist entry — add one to {allow_path.name}")
            continue
        extra_hosts = sorted(set(entry["egress_hosts"]) - set(rule.get("hosts", [])))
        if extra_hosts:
            violations.append(f"{tid}: undeclared egress hosts: {', '.join(extra_hosts)}")
        input_diff = sorted(
            set(entry["endpoint_inputs"]) ^ set(rule.get("endpoint_inputs", []))
        )
        if input_diff:
            violations.append(
                f"{tid}: endpoint inputs differ from baseline: {', '.join(input_diff)}"
            )
    return violations


def extract_egress(run: str) -> tuple[list[str], list[str]]:
    """Return (full_urls, bare_hosts) mentioned in the script."""
    urls: list[str] = []
    hosts: list[str] = []
    for match in URL_RE.finditer(run):
        url = match.group(0).rstrip(".,;)")
        urls.append(url)
        host = urlparse(url).netloc
        if host:
            hosts.append(host)
    # also catch bare-host references like nc example.com 443
    for match in re.finditer(r"\bnc\s+(?:-z\s+)?(?:-w\s+\d+\s+)?([a-z0-9.-]+)\s+(\d+)", run, re.IGNORECASE):
        hosts.append(f"{match.group(1)}:{match.group(2)}")
    return urls, hosts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Paths resolve against the repo root (script's parent), so the script
    # behaves identically from any working directory.
    root = Path(__file__).resolve().parent.parent

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument(
        "--output",
        default=None,
        help="Write machine-readable evidence JSON here (default: print only)",
    )
    parser.add_argument(
        "--print",
        dest="print_table",
        action="store_true",
        help="Print the human-readable egress table",
    )
    parser.add_argument(
        "--expect",
        default=None,
        help="Path to egress-allowlist.json. Every buz/* template must have "
        "an entry there; extracted hosts must stay within the allowed set "
        "and endpoint inputs must match exactly. Exits non-zero on any "
        "deviation — the allowlist is the reviewed baseline, so changing it "
        "is part of review, not a build fix.",
    )
    args = parser.parse_args()

    plugin_dir = resolve(args.plugins_dir)
    files = sorted(p for p in plugin_dir.iterdir() if p.suffix in (".yaml", ".yml"))
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    evidence = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        spec = yaml.safe_load(raw)
        if not spec or not isinstance(spec, dict):
            raise SystemExit(f"{path}: not a valid step spec — run step-validate")
        run = spec.get("run") or ""
        urls: list[str] = []
        hosts: list[str] = []
        endpoint_inputs: set[str] = set()
        for match in URL_RE.finditer(run):
            url = match.group(0).rstrip(".,;)")
            urls.append(url)
            host = urlparse(url).netloc
            if host:
                hosts.append(host)
        for input_name in spec.get("inputs") or {}:
            if ENDPOINT_INPUT_RE.search(input_name):
                endpoint_inputs.add(input_name)
        evidence.append(
            {
                "file": str(path),
                "id": spec.get("id"),
                "version": spec.get("version"),
                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "egress_urls": sorted(set(urls)),
                "egress_hosts": sorted(set(hosts)),
                "endpoint_inputs": sorted(endpoint_inputs),
            }
        )

    if args.print_table:
        for entry in evidence:
            print(f"{entry['id']}@{entry['version']}  ({entry['file']})")
            for host in entry["egress_hosts"]:
                print(f"    → {host}")
            for input_name in entry["endpoint_inputs"]:
                print(f"    → runtime endpoint via input: {input_name}")
            if not entry["egress_hosts"] and not entry["endpoint_inputs"]:
                print("    → (no outbound endpoints declared)")

    if args.expect:
        violations = check_allowlist(evidence, resolve(args.expect))
        if violations:
            for v in violations:
                print(f"EGRESS VIOLATION: {v}", file=sys.stderr)
            raise SystemExit(
                f"{len(violations)} egress allowlist violation(s) — the "
                "allowlist is the reviewed baseline: a deviation needs human "
                "review before the allowlist is updated"
            )
        official = sum(1 for e in evidence if (e["id"] or "").startswith("buz/"))
        print(f"egress allowlist: {official} official template(s) within baseline")

    output = args.output
    if output:
        out_path = resolve(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"evidence: {len(evidence)} entr(ies) → {out_path}")


if __name__ == "__main__":
    sys.exit(main())
