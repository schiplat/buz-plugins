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

# ── POSIX-sh compat gate ─────────────────────────────────────────────────
# The Runner executes `run:` blocks via `sh -e -c` (crates/runner
# engine/shell.rs), and the ssh engine prepends exports to the same line —
# so a template's run block must parse under POSIX sh. Bash-only constructs
# kill the step on Debian/Ubuntu (dash), Alpine (ash), and macOS (bash 3.2)
# with anything from a syntax error to a silent `set -e` early exit. Text
# review cannot be trusted to catch this (env-render 1.0.0 shipped
# `declare -A` and ran on none but RHEL-family hosts), so the lint does.
# Case-sensitive matching on purpose: `select`/`source`/`function` are only
# keywords when lowercase and line-initial.
BASHISM_PATTERNS = [
    (r"\b(?:declare|typeset)\b", "bash-only: declare/typeset — absent from dash/ash; assign directly or use export"),
    (r"\[\[", "bash-only: [[ ]] compound test — use [ ] with ="),
    (r"<<<", "bash-only: herestring <<< — use printf | while read"),
    (r"\$'", "bash-only: ANSI-C quoting $'…' — use printf/tr for control characters"),
    (r"<\(|>\(", "bash-only: process substitution — use a temp file"),
    (r"\$\{!", "bash-only: indirect/array-key expansion ${!name}"),
    (r"^\s*[A-Za-z_][A-Za-z0-9_]*=\(", "bash-only: array assignment NAME=(…) — POSIX sh has no arrays"),
    (r"^\s*[A-Za-z_][A-Za-z0-9_]*\+=", 'bash-only: append assignment NAME+=… — write NAME="${NAME}…"'),
    (r"\$\{[A-Za-z_][A-Za-z0-9_]*:[0-9]", "bash-only: substring ${var:offset} — use awk/cut"),
    (r"\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^)", "bash-only: case modification ${var,,}/${var^^} — use tr"),
    (r"^\s*select\s", "bash-only: select loop"),
    (r"\bcoproc\b", "bash-only: coproc"),
    (r"^\s*source\s", "bash-only: source — use `. ./script`"),
    (r"^\s*function\s", "bash-only: function keyword — write name() …"),
    (r"\bshopt\b", "bash-only: shopt"),
]

# (plugin_id, version) → human reason. Published specs are content-frozen
# (fixes ship as new versions), so the bash-era env-render releases stay
# listed until they age out of every Manager's local index.
BASHISM_EXCEPTIONS = {
    ("buz/env-render", "1.0.0"): "bash-only original shipped before this gate; frozen at publish — 1.1.1+ is the POSIX line",
    ("buz/env-render", "1.1.0"): "env-channel redesign, still bash; frozen at publish — 1.1.1+ is the POSIX line",
}


def bashism_hits(body: list[str]) -> list[tuple[int, str]]:
    """Return (offset, reason) for bash-only constructs, one per line.

    Comment lines are skipped; the first matching pattern per line wins so a
    line like `declare -A m=()` reports once, not twice.
    """
    hits: list[tuple[int, str]] = []
    for offset, line in enumerate(body):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern, reason in BASHISM_PATTERNS:
            if re.search(pattern, stripped):
                hits.append((offset, reason))
                break
    return hits


def spec_id(raw: str) -> str:
    match = re.search(r"^id:\s*(\S+)", raw, re.MULTILINE)
    return match.group(1) if match else ""


def spec_version(raw: str) -> str:
    match = re.search(r"^version:\s*['\"]?([^'\"\s]+)", raw, re.MULTILINE)
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

        # POSIX-sh compat gate (see BASHISM_PATTERNS). Exceptions are keyed
        # by (id, version): published specs are frozen, fixes are new versions.
        if (plugin_id, spec_version(raw)) in BASHISM_EXCEPTIONS:
            continue
        for start, body in run_blocks(raw):
            for offset, reason in bashism_hits(body):
                findings.append(f"{path}:{start + offset + 1}: {reason}\n    {body[offset].strip()}")

    if findings:
        print(f"lint: {len(findings)} finding(s) — every hit needs a human reason:")
        for finding in findings:
            print(f"  - {finding}")
        raise SystemExit(1)
    print(f"lint: clean ({len(files)} spec(s), POSIX-sh gate on)")


if __name__ == "__main__":
    main()
