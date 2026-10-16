#!/usr/bin/env python3
"""Extract outbound endpoints mentioned by shell network commands in templates.

This is deliberately heuristic evidence for review, not a complete shell
interpreter. URLs are extracted from all run text; common network clients are
parsed for literal and variable destinations. Variable destinations are
reported as endpoint inputs so the official allowlist detects new runtime
network surfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

URL_RE = re.compile(r"""https?://[^\s'"<>\\]+""", re.IGNORECASE)
ENDPOINT_WORDS = {
    "webhook", "url", "uri", "host", "port", "endpoint", "server", "addr",
    "api", "target", "destination", "origin", "registry",
}
ENDPOINT_LABEL_PRIORITY = (
    "webhook", "url", "uri", "host", "port", "endpoint", "server", "addr",
    "api", "target", "destination", "origin",
)
NETWORK_COMMANDS = {"nc", "netcat", "ncat", "curl", "wget", "ssh", "scp", "sftp", "ping", "telnet", "aws", "ossutil"}
VARIABLE_RE = re.compile(
    r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\})"
)
VARIABLE_RE = re.compile(
    r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)(?::-[^}]*)?\})"
)



def _endpoint_words(name: str) -> list[str]:
    """Split snake_case and camelCase input names into lowercase words."""
    return [
        word.lower()
        for word in re.findall(
            r"[A-Z]+(?=[A-Z][a-z]|[^A-Za-z]|$)|[A-Z]?[a-z]+|[0-9]+", name
        )
    ]


def _endpoint_input(name: str) -> bool:
    return any(word in ENDPOINT_WORDS for word in _endpoint_words(name))


def _endpoint_label(value: str) -> str | None:
    names = [group1 or group2 for group1, group2 in VARIABLE_RE.findall(value)]
    for name in names:
        normalized = name.removeprefix("INPUT_").lower()
        words = _endpoint_words(name.removeprefix("INPUT_"))
        for preferred in ENDPOINT_LABEL_PRIORITY:
            if preferred in words or normalized == preferred:
                return preferred
    return names[0].removeprefix("INPUT_").lower() if names else None


NO_VALUE_FLAGS = {
    "nc": {"-4", "-6", "-d", "-k", "-l", "-n", "-r", "-u", "-v", "-z"},
    "netcat": {"-4", "-6", "-d", "-k", "-l", "-n", "-r", "-u", "-v", "-z"},
    "ncat": {"-4", "-6", "-c", "-k", "-l", "-n", "-v", "-z"},
    "ssh": {"-4", "-6", "-A", "-a", "-C", "-f", "-G", "-g", "-K", "-k", "-M", "-N", "-n", "-q", "-s", "-T", "-t", "-V", "-v", "-X", "-x", "-Y", "-y"},
    "curl": {"-f", "-s", "-S", "-L", "-k", "-v", "-I", "-i", "-G", "-g", "-N", "-n", "-O", "-J", "-4", "-6", "-h", "--fail", "--silent", "--show-error", "--location", "--insecure", "--verbose", "--head", "--include", "--get", "--globoff", "--no-buffer", "--remote-name", "--remote-header-name", "--ipv4", "--ipv6"},
    "wget": {"-q", "-v", "-nv", "-c", "-N", "-S", "-d", "--quiet", "--verbose", "--no-verbose", "--continue", "--timestamping", "--server-response", "--debug", "--no-proxy", "--spider"},
    "ping": {"-4", "-6", "-n", "-q", "-v"},
    "telnet": {"-8", "-E", "-L"},
    "scp": {"-3", "-4", "-6", "-A", "-B", "-C", "-q", "-r", "-T", "-v"},
    "sftp": {"-4", "-6", "-A", "-B", "-C", "-q", "-r", "-v"},
}
OPTION_VALUE_FLAGS = {
    "nc": {"-w", "-p", "-s", "-i", "-q", "-b", "-T", "-X", "-x", "-M", "-m"},
    "netcat": {"-w", "-p", "-s", "-i", "-q", "-b", "-T", "-X", "-x", "-M", "-m"},
    "ncat": {"-w", "-p", "-s", "-i", "-q", "-b", "-T", "-x", "--proxy", "--proxy-type", "--proxy-auth"},
    "ssh": {"-p", "-l", "-i", "-o", "-F", "-J", "-W", "-b", "-c", "-D", "-E", "-L", "-R", "-S", "-w"},
    "scp": {"-c", "-D", "-F", "-i", "-J", "-l", "-o", "-P", "-S"},
    "sftp": {"-b", "-c", "-D", "-F", "-i", "-J", "-l", "-o", "-P", "-R", "-S"},
    "curl": {"-o", "--output", "-w", "--write-out", "-X", "--request", "-H", "--header", "-d", "--data", "--data-raw", "--data-binary", "-u", "--user", "-e", "--referer", "-A", "--user-agent", "-m", "--max-time", "-F", "--form", "-x", "--proxy", "--proxy-user", "--connect-timeout", "--retry", "--retry-delay", "--interface", "--resolve", "--cacert", "--cert", "--key", "--limit-rate", "--max-redirs", "--proto", "--url"},
    "wget": {"-O", "--output-document", "-o", "--output-file", "--header", "--post-data", "--post-file", "--user", "--password", "--timeout", "--tries", "--bind-address", "--proxy", "--execute", "--directory-prefix", "--ca-certificate", "--certificate", "--private-key"},
    "ping": {"-c", "-i", "-W", "-w", "-s", "-t"},
    "telnet": {"-a", "-b", "-c", "-d", "-e", "-l", "-n"},
}


def _parse_network_args(name: str, args: list[str]) -> tuple[list[str], dict[str, list[str]], bool]:
    """Parse known option forms; unknown or incomplete options are ambiguous."""
    positional: list[str] = []
    options: dict[str, list[str]] = {}
    switches = NO_VALUE_FLAGS.get(name, set())
    value_flags = OPTION_VALUE_FLAGS.get(name, set())
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            positional.extend(args[index + 1 :])
            break
        if not arg.startswith("-") or arg == "-":
            positional.append(arg)
            index += 1
            continue
        if arg in value_flags:
            if index + 1 >= len(args):
                return positional, options, False
            options.setdefault(arg, []).append(args[index + 1])
            index += 2
            continue
        if arg.startswith("--"):
            flag, equals, value = arg.partition("=")
            if flag in switches:
                options.setdefault(flag, []).append(value if equals else "")
            elif flag in value_flags and equals:
                options.setdefault(flag, []).append(value)
            else:
                return positional, options, False
            index += 1
            continue

        # Support combined switches (e.g. curl -fsSL), and attached short
        # option values (e.g. ssh -Jjump or curl -xproxy:8080).
        chars = arg[1:]
        offset = 0
        while offset < len(chars):
            flag = "-" + chars[offset]
            if flag in value_flags:
                value = chars[offset + 1 :]
                if not value:
                    if index + 1 >= len(args):
                        return positional, options, False
                    index += 1
                    value = args[index]
                options.setdefault(flag, []).append(value)
                offset = len(chars)
            elif flag in switches:
                options.setdefault(flag, []).append("")
                offset += 1
            else:
                return positional, options, False
        index += 1
    return positional, options, True


def _cli_endpoint_destinations(
    args: list[str], flags: set[str], env_names: tuple[str, ...], assignments: dict[str, str]
) -> tuple[list[str], bool]:
    """Extract explicit endpoint options or known endpoint environment variables."""
    destinations: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        flag = arg.partition("=")[0]
        if flag in flags:
            if "=" in arg:
                value = arg.partition("=")[2]
            elif len(arg) > len(flag):
                value = arg[len(flag):]
            elif index + 1 < len(args):
                index += 1
                value = args[index]
            else:
                return destinations, False
            if not value:
                return destinations, False
            destinations.append(value)
        index += 1
    if destinations:
        return destinations, True
    for name in env_names:
        if assignments.get(name):
            return [assignments[name]], True
    return [], False


def _network_destinations(
    command: str, args: list[str], assignments: dict[str, str] | None = None
) -> tuple[list[str], bool]:
    name = Path(command).name.lower()
    assignments = assignments or {}
    if name == "aws":
        return _cli_endpoint_destinations(
            args,
            {"--endpoint-url"},
            ("AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3"),
            assignments,
        )
    if name == "ossutil":
        return _cli_endpoint_destinations(
            args,
            {"--endpoint", "-e"},
            ("OSSUTIL_ENDPOINT", "OSS_ENDPOINT"),
            assignments,
        )

    positional, options, parsed = _parse_network_args(name, args)
    if not parsed:
        return [], False

    destinations: list[str] = []
    if name in {"nc", "netcat", "ncat"}:
        proxy_values = options.get("-x", []) + options.get("--proxy", [])
        destinations.extend(proxy_values)
        destinations.extend(positional[:2])
        if not positional:
            return destinations, False
    elif name in {"ssh", "scp", "sftp"}:
        jump_values = options.get("-J", [])
        for value in options.get("-o", []):
            setting = re.match(r"(?i)^ProxyJump(?:\s+|=)(.+)$", value)
            proxy_command = re.match(r"(?i)^ProxyCommand(?:\s+|=)(.*)$", value)
            if setting:
                jump_values.append(setting.group(1))
            elif proxy_command:
                return destinations, False
        for value in jump_values:
            destinations.extend(jump.strip() for jump in value.split(",") if jump.strip())
        if name == "ssh":
            if options.get("-W"):
                destinations.extend(options["-W"])
            if options.get("-L") or options.get("-R") or options.get("-D"):
                return destinations, False
            if positional:
                destinations.append(positional[0])
        else:
            remote_items = [item for item in positional if ":" in item and not item.startswith("-")]
            if not remote_items:
                return destinations, False
            destinations.extend(item.split(":", 1)[0] for item in remote_items)
    elif name in {"curl", "wget"}:
        for flag in ("-x", "--proxy"):
            for value in options.get(flag, []):
                proxy = urlparse(value if "://" in value else "//" + value)
                destinations.append(proxy.netloc or value)
        urls = positional + options.get("--url", [])
        if not urls:
            return destinations, False
        destinations.extend(urls)
    else:
        if positional:
            destinations.append(positional[0])

    if not destinations or any(not item for item in destinations):
        return destinations, False
    return destinations, True


def _endpoint_host(value: str) -> str:
    if value.startswith(("http://", "https://", "socks://", "socks4://", "socks5://")):
        return urlparse(value).netloc or value
    return value.split("@", 1)[-1]


SHELL_SUBSTITUTION_MARKER_RE = re.compile(r"__SHELL_SUBST_\d+__")


def _substitution_end(text: str, start: int) -> int:
    """Return the end of a $(...) expression, accounting for nested groups."""
    depth = 1
    quote: str | None = None
    escaped = False
    index = start + 2
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote == "'":
            if char == "'":
                quote = None
        elif quote == '"':
            if char == '"':
                quote = None
            elif text.startswith("$(", index):
                depth += 1
                index += 1
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index + 1
        elif char in "'\"":
            quote = char
        elif text.startswith("$(", index):
            depth += 1
            index += 1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def _backtick_end(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
        elif text[index] == "`":
            return index + 1
        else:
            index += 1
    return len(text)


def _shell_command_segments(text: str) -> list[str]:
    """Split common shell command boundaries and inspect substitutions.

    This is a deliberately limited lexer, not a shell parser. Unsupported shell
    syntax and execution semantics cannot be resolved here.
    """
    segments: list[str] = []
    marker_number = 0

    def scan(source: str, inspect: bool = True) -> None:
        nonlocal marker_number
        segment: list[str] = []
        quote: str | None = None
        index = 0

        def flush() -> None:
            value = "".join(segment).strip()
            if value:
                segments.append(value)
            segment.clear()

        while index < len(source):
            char = source[index]
            if char == "\\" and index + 1 < len(source):
                segment.extend((char, source[index + 1]))
                index += 2
                continue
            if quote != "'" and source.startswith("$(", index):
                end = _substitution_end(source, index)
                inner = source[index + 2 : max(index + 2, end - 1)]
                if inspect:
                    scan(inner, inspect=False)
                segment.append(f"__SHELL_SUBST_{marker_number}__")
                marker_number += 1
                index = end
                continue
            if quote != "'" and char == "`":
                end = _backtick_end(source, index)
                inner = source[index + 1 : max(index + 1, end - 1)]
                if inspect:
                    scan(inner, inspect=False)
                segment.append(f"__SHELL_SUBST_{marker_number}__")
                marker_number += 1
                index = end
                continue
            if quote:
                segment.append(char)
                if char == quote:
                    quote = None
                index += 1
                continue
            if char in "'\"":
                quote = char
                segment.append(char)
                index += 1
                continue
            if char == "#" and (not segment or segment[-1].isspace()):
                while index < len(source) and source[index] != "\\n":
                    index += 1
                continue
            if char in ";&|\n()":
                flush()
                if char in "&|" and index + 1 < len(source) and source[index + 1] == char:
                    index += 2
                elif char == "|" and index + 1 < len(source) and source[index + 1] == "&":
                    index += 2
                else:
                    index += 1
                continue
            segment.append(char)
            index += 1
        flush()

    scan(text)
    return segments


def _is_dynamic_endpoint(value: str) -> bool:
    return bool(VARIABLE_RE.search(value) or SHELL_SUBSTITUTION_MARKER_RE.search(value))


def _expand_known_variables(value: str, assignments: dict[str, str]) -> str:
    return VARIABLE_RE.sub(
        lambda match: assignments.get(match.group(1) or match.group(2), match.group(0)),
        value,
    )


def _resolve_dynamic(
    value: str, assignments: dict[str, str], fallback: str
) -> tuple[str, str | None]:
    actual = value
    for _ in range(len(assignments) + 1):
        expanded = _expand_known_variables(actual, assignments)
        if expanded == actual:
            break
        actual = expanded
    dynamic = _endpoint_label(actual)
    if not dynamic and _is_dynamic_endpoint(actual):
        if actual.startswith("$"):
            variable_match = VARIABLE_RE.search(actual)
            variable_name = (
                (variable_match.group(1) or variable_match.group(2))
                if variable_match
                else ""
            )
            dynamic = variable_name.removeprefix("INPUT_").lower()
        else:
            dynamic = fallback
    return actual, dynamic


def _assignment(word: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", word)
    return (match.group(1), match.group(2)) if match else None


def _unwrap_command(words: list[str], assignments: dict[str, str]) -> tuple[list[str], dict[str, str], bool]:
    """Remove understood command wrappers; report unrecognized wrapper syntax."""
    local_assignments = dict(assignments)
    control_words = {"if", "then", "elif", "else", "while", "until", "do", "!"}
    while words and words[0].lower() in control_words:
        words.pop(0)
    while words and _assignment(words[0]):
        key, value = _assignment(words.pop(0))  # type: ignore[misc]
        local_assignments[key] = value
    while words:
        wrapper = Path(words[0]).name.lower()
        if wrapper in {"sudo", "command", "exec", "builtin"}:
            words.pop(0)
            if words and words[0] == "--":
                words.pop(0)
            continue
        if wrapper == "timeout":
            words.pop(0)
            while words and words[0].startswith("-"):
                option = words.pop(0)
                if option in {"--signal", "-s", "--kill-after", "-k"}:
                    if not words:
                        return words, local_assignments, False
                    words.pop(0)
                elif option.startswith("--signal=") or option.startswith("--kill-after="):
                    continue
                elif option in {"--foreground", "--preserve-status", "--verbose"}:
                    continue
                else:
                    return words, local_assignments, False
            if words and re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?)(?:s|m|h|d)?", words[0]):
                words.pop(0)
            else:
                return words, local_assignments, False
            continue
        if wrapper == "env":
            words.pop(0)
            while words:
                option = words[0]
                if option == "--":
                    words.pop(0)
                    break
                if option in {"-i", "--ignore-environment", "-0", "--null"}:
                    words.pop(0)
                    continue
                if option in {"-u", "--unset", "-C", "--chdir"}:
                    if len(words) < 2:
                        return words, local_assignments, False
                    words = words[2:]
                    continue
                if option.startswith("--unset=") or option.startswith("--chdir="):
                    words.pop(0)
                    continue
                assignment = _assignment(option)
                if assignment:
                    key, value = assignment
                    local_assignments[key] = value
                    words.pop(0)
                    continue
                if option.startswith("-"):
                    return words, local_assignments, False
                break
            continue
        break
    return words, local_assignments, True


def _resolve_and_record(value: str, assignments: dict[str, str], fallback: str, hosts: list[str]) -> str:
    actual, dynamic = _resolve_dynamic(value, assignments, fallback)
    if dynamic:
        hosts.append(f"<dynamic-endpoint:{dynamic}>")
    elif SHELL_SUBSTITUTION_MARKER_RE.search(actual):
        hosts.append("<unparsed-network-command>")
    elif actual.startswith(("http://", "https://", "socks://", "socks4://", "socks5://")):
        hosts.append(urlparse(actual).netloc or "<invalid-endpoint-url>")
    else:
        hosts.append(_endpoint_host(actual))
    return actual


def extract_egress(run: str) -> tuple[list[str], list[str]]:
    """Return literal URLs and network destinations, failing closed on unknown syntax."""
    logical_lines: list[str] = []
    pending = ""
    for line in run.splitlines():
        stripped = line.rstrip()
        continued = stripped.endswith("\\")
        pending += (stripped[:-1] if continued else stripped) + (" " if continued else "")
        if not continued:
            logical_lines.append(pending)
            pending = ""
    if pending:
        logical_lines.append(pending)

    segments = _shell_command_segments("\n".join(logical_lines))
    urls: list[str] = []
    for segment in segments:
        for match in URL_RE.finditer(segment):
            url = match.group(0).rstrip(".,;)")
            urls.append(url)

    assignments: dict[str, str] = {}
    hosts: list[str] = []
    for segment in segments:
        try:
            words = shlex.split(segment, comments=True)
        except ValueError:
            if re.search(r"\b(?:" + "|".join(sorted(NETWORK_COMMANDS)) + r")\b", segment):
                hosts.append("<unparsed-network-command>")
            continue
        if not words:
            continue

        if words[0] == "export":
            exported = [_assignment(word) for word in words[1:]]
            if exported and all(exported):
                for item in exported:
                    key, value = item  # type: ignore[misc]
                    value = _expand_known_variables(value, assignments)
                    assignments[key] = value
                continue

        # Standalone simple assignments take effect only from this point onward.
        if all(_assignment(word) for word in words):
            for word in words:
                key, value = _assignment(word)  # type: ignore[misc]
                # Preserve the value established by an earlier assignment when
                # shell code appends suffixes (URL="${URL}&token=...").
                previous = assignments.get(key)
                if previous is not None and re.search(
                    rf"\$(?:{re.escape(key)}|\{{{re.escape(key)}(?:[:-][^}}]*)?\}})",
                    value,
                ):
                    value = VARIABLE_RE.sub(
                        lambda match: previous if (match.group(1) or match.group(2)) == key else match.group(0),
                        value,
                    )
                else:
                    value = _expand_known_variables(value, assignments)
                assignments[key] = value
            continue

        words, command_assignments, parsed_wrapper = _unwrap_command(words, assignments)
        if not parsed_wrapper:
            if any(Path(word).name.lower() in NETWORK_COMMANDS for word in words):
                hosts.append("<unparsed-network-command>")
            continue
        if not words:
            continue
        command, args = words[0], words[1:]
        command_name = Path(command).name.lower()
        if command_name not in NETWORK_COMMANDS:
            # Do not silently assume arbitrary wrappers are harmless.
            if any(Path(word).name.lower() in NETWORK_COMMANDS for word in args):
                hosts.append("<unparsed-network-command>")
            continue

        args = [arg for arg in args if not re.match(r"^\d*(?:>|<)", arg)]
        expanded_args: list[str] = []
        for arg in args:
            expanded = _expand_known_variables(arg, command_assignments)
            if expanded != arg and expanded.startswith("-"):
                try:
                    expanded_args.extend(shlex.split(expanded))
                except ValueError:
                    hosts.append("<unparsed-network-command>")
                    expanded_args = []
                    break
            else:
                expanded_args.append(expanded)
        if not expanded_args and args:
            continue
        destinations, parsed_args = _network_destinations(
            command, expanded_args, command_assignments
        )
        if not parsed_args:
            hosts.append("<unparsed-network-command>")
            continue
        if not destinations:
            hosts.append("<missing-destination>")
            continue
        if command_name in {"nc", "netcat", "ncat"}:
            _, options, _ = _parse_network_args(command_name, args)
            proxy_count = len(options.get("-x", []) + options.get("--proxy", []))
            for destination in destinations[:proxy_count]:
                _resolve_and_record(destination, command_assignments, "host", hosts)
            host_index = proxy_count
            host_arg = destinations[host_index] if host_index < len(destinations) else None
            port_arg = destinations[host_index + 1] if host_index + 1 < len(destinations) else None
            if host_arg:
                actual_host, dynamic_host = _resolve_dynamic(host_arg, command_assignments, "host")
                actual_port, dynamic_port = (
                    _resolve_dynamic(port_arg, command_assignments, "port")
                    if port_arg
                    else (None, None)
                )
                if dynamic_host:
                    hosts.append(f"<dynamic-endpoint:{dynamic_host}>")
                if dynamic_port:
                    hosts.append(f"<dynamic-endpoint:{dynamic_port}>")
                if not dynamic_host:
                    hosts.append(
                        f"{_endpoint_host(actual_host)}:{actual_port}"
                        if actual_port and not dynamic_port
                        else _endpoint_host(actual_host)
                    )
            else:
                hosts.append("<missing-destination>")
            continue
        fallback = "url" if command_name in {"curl", "wget"} else "host"
        for destination in destinations:
            _resolve_and_record(destination, command_assignments, fallback, hosts)

    return urls, sorted(set(hosts))


def check_allowlist(evidence: list[dict], allow_path: Path) -> list[str]:
    """Enforce reviewed hosts as an upper bound and runtime inputs exactly."""
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for entry in evidence:
        template_id = entry["id"] or ""
        if not template_id.startswith("buz/"):
            continue
        rule = allow.get(template_id)
        if rule is None:
            violations.append(f"{template_id}: no allowlist entry — add one to {allow_path.name}")
            continue
        extra_hosts = sorted(set(entry["egress_hosts"]) - set(rule.get("hosts", [])))
        if extra_hosts:
            violations.append(f"{template_id}: undeclared egress hosts: {', '.join(extra_hosts)}")
        input_diff = sorted(set(entry["endpoint_inputs"]) ^ set(rule.get("endpoint_inputs", [])))
        if input_diff:
            violations.append(f"{template_id}: endpoint inputs differ from baseline: {', '.join(input_diff)}")
    return violations


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
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent.parent

    def resolve(path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    parser.add_argument("--plugins-dir", default="plugins")
    parser.add_argument("--output", default=None, help="Write machine-readable evidence JSON here")
    parser.add_argument("--print", dest="print_table", action="store_true", help="Print the human-readable egress table")
    parser.add_argument(
        "--expect",
        default=None,
        help="Enforce egress-allowlist.json for all official buz/* templates",
    )
    args = parser.parse_args()
    plugin_dir = resolve(args.plugins_dir)
    if not plugin_dir.is_symlink():
        plugin_dir = plugin_dir.resolve()
    files = discover_plugin_files(plugin_dir)
    if not files:
        raise SystemExit(f"{plugin_dir}: no step specs found")

    evidence = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        spec = yaml.safe_load(raw)
        if not spec or not isinstance(spec, dict):
            raise SystemExit(f"{path}: not a valid step spec — run step-validate")
        urls, hosts = extract_egress(spec.get("run") or "")
        endpoint_inputs = {
            str(name) for name in (spec.get("inputs") or {}) if _endpoint_input(str(name))
        }
        dynamic_hosts = [host for host in hosts if host.startswith("<dynamic-endpoint:")]
        endpoint_inputs.update(host[len("<dynamic-endpoint:") : -1] for host in dynamic_hosts)
        hosts = [host for host in hosts if host not in dynamic_hosts]
        evidence.append(
            {
                "file": path.resolve().relative_to(root).as_posix(),
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
            for name in entry["endpoint_inputs"]:
                print(f"    → runtime endpoint via input: {name}")
            if not entry["egress_hosts"] and not entry["endpoint_inputs"]:
                print("    → (no outbound endpoints declared)")

    if args.expect:
        violations = check_allowlist(evidence, resolve(args.expect))
        if violations:
            for violation in violations:
                print(f"EGRESS VIOLATION: {violation}", file=sys.stderr)
            raise SystemExit(
                f"{len(violations)} egress allowlist violation(s) — the allowlist is the reviewed baseline"
            )
        official = sum(1 for entry in evidence if (entry["id"] or "").startswith("buz/"))
        print(f"egress allowlist: {official} official template(s) within baseline")

    if args.output:
        out_path = resolve(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"evidence: {len(evidence)} entr(ies) → {out_path}")


if __name__ == "__main__":
    sys.exit(main())
