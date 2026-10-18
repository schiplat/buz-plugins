#!/usr/bin/env python3
"""Heuristic lint over step-template `run:` blocks (ADR §6.7.2, layer 1).

Recursively scans visible plugins/**/*.yaml|yml specs for patterns that usually mean
"arbitrary code execution" or "secrets leaving the host". Hits are not
proof of malice — but every hit needs a human reason in review.

Stdlib only; exits non-zero when anything is found.
"""

import os
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

# Buz (>=1.8.1) appends a `uses:` step's caller `run:` after the template run
# in the same shell. A top-level `exit`/`exec` in the template run would
# silently skip those caller commands. Templates listed here keep a fixed
# process-replacing contract on purpose — that is the human reason their hit
# is accepted.
TERMINAL_RUN_EXCEPTIONS = {
    "buz/oss-download",  # image entrypoint: ossutil replaces the shell
    "buz/oss-upload",  # image entrypoint: upload helper replaces the shell
    "buz/s3-upload",  # image entrypoint: upload helper replaces the shell
    "buz/http-check",  # probe: `exit 1` is how the step reports failure
    "buz/ssh-wait",  # probe: `exit 1` is how the step reports timeout
}


def spec_id(raw: str) -> str:
    match = re.search(r"^id:\s*(\S+)", raw, re.MULTILINE)
    return match.group(1) if match else ""


def terminal_run_lines(body: list[str]) -> list[int]:
    """Return offsets of top-level `exit`/`exec` lines inside a run block.

    "Top-level" means the line sits at the block's base indentation (the
    indentation of its first content line). Deeper-indented exits inside
    `case`/`if` branches or `&&`/`||` lists are fine — they don't stop the
    appended caller run.
    """
    base_indent = None
    for line in body:
        if line.strip():
            base_indent = len(line) - len(line.lstrip())
            break
    if base_indent is None:
        return []
    hits: list[int] = []
    for offset, line in enumerate(body):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == base_indent and stripped.split()[0] in ("exit", "exec"):
            hits.append(offset)
    return hits


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


def main() -> None:
    plugin_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "plugins")
    files = discover_plugin_files(plugin_dir)
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    findings: list[str] = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        plugin_id = spec_id(raw)
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
            if plugin_id in TERMINAL_RUN_EXCEPTIONS:
                continue
            for offset in terminal_run_lines(body):
                stripped = body[offset].strip()
                findings.append(
                    f"{path}:{start + offset + 1}: top-level {stripped.split()[0]} — "
                    "Buz appends the caller run: after the template run; this line "
                    "would prevent the caller's commands from executing\n"
                    f"    {stripped}"
                )

    if findings:
        print(f"lint: {len(findings)} finding(s) — every hit needs a human reason:")
        for finding in findings:
            print(f"  - {finding}")
        raise SystemExit(1)
    print(f"lint: clean ({len(files)} spec(s))")


if __name__ == "__main__":
    main()
