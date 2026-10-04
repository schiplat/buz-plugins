#!/usr/bin/env python3
"""Heuristic lint over step-template `run:` blocks (ADR §6.7.2, layer 1).

Scans every plugins/*.yaml|yml `run:` block for patterns that usually mean
"arbitrary code execution" or "secrets leaving the host". Hits are not
proof of malice — but every hit needs a human reason in review.

Stdlib only; exits non-zero when anything is found.
"""

import re
import sys
from pathlib import Path

# (pattern, reason) — matched case-insensitively against non-comment lines
# inside a `run: |` block.
PATTERNS = [
    (r"\beval\b", "eval — dynamic code execution"),
    (r"\|\s*(sudo\s+)?(ba|z|da)?sh(\s|$)", "pipe into a shell interpreter"),
    (r"\|\s*(sudo\s+)?python(3)?(\s|$)", "pipe into an interpreter"),
    (r"base64\s+(-d|--decode)", "base64 decode — often obfuscated payload staging"),
    (r"/dev/tcp/", "bash /dev/tcp reverse-shell primitive"),
    (r"\bnc\b[^|]*\s-e\b", "nc -e — binds a shell"),
    (r"\bcurl\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh", "curl | sh — remote code install"),
    (r"\bwget\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh", "wget | sh — remote code install"),
    (r"\b(curl|wget)\s+http://", "plaintext HTTP download — integrity unverifiable"),
    (r"\bhistory\s+-c\b", "history wipe — hides operator traces"),
    (r"\bchmod\s+\+?x[^&|;]*(&&|\||;)\s*\./", "chmod +x followed by immediate execution"),
]


def run_blocks(raw: str) -> list[tuple[int, list[str]]]:
    """Yield (start_line, lines) for each `run: |` block's shell content."""
    blocks: list[tuple[int, list[str]]] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"^\s*run:\s*\|", lines[i]):
            start = i + 1
            body: list[str] = []
            j = start
            while j < len(lines):
                line = lines[j]
                if line.strip() == "" :
                    body.append(line)
                    j += 1
                    continue
                indent = len(line) - len(line.lstrip())
                # Block scalar indent is set by the first content line; a
                # non-empty line at indent <= the `run:` key's indent ends it.
                key_indent = len(lines[i]) - len(lines[i].lstrip())
                if indent <= key_indent:
                    break
                body.append(line)
                j += 1
            blocks.append((start, body))
            i = j
        else:
            i += 1
    return blocks


def main() -> None:
    plugin_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "plugins")
    files = sorted(p for p in plugin_dir.iterdir() if p.suffix in (".yaml", ".yml"))
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    findings: list[str] = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        for start, body in run_blocks(raw):
            for offset, line in enumerate(body):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                for pattern, reason in PATTERNS:
                    if re.search(pattern, stripped, re.IGNORECASE):
                        findings.append(
                            f"{path}:{start + offset + 1}: {reason}\n    {stripped}"
                        )

    if findings:
        print(f"lint: {len(findings)} finding(s) — every hit needs a human reason:")
        for finding in findings:
            print(f"  - {finding}")
        raise SystemExit(1)
    print(f"lint: clean ({len(files)} spec(s))")


if __name__ == "__main__":
    main()
