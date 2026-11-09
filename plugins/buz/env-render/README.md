# Env render

Expands a dotenv-style template (`env.example`) into an env file, substituting `${secrets.NAME}` placeholders with values from the step's **own environment** — the plugin form of the kernel `config.render` block. Each referenced secret is mapped on the call site (`env: <values_prefix><NAME>: ${secrets.NAME}`), so secrets transit the standard masked env channel and are declared where they are used. Dual engine, declared via `engines: [shell, ssh]`:

- **`engine: shell` (default)** — renders into a **relative** `dest_dir` inside the Runner job workspace.
- **`engine: ssh`** — renders into an **absolute** `dest_dir` on each target host (`host:` list).

Runs on any POSIX sh — dash, ash, bash 3+ — no bash and no GNU tools required.

## Usage

```yaml
- name: render env
  uses: buz/env-render@1.1.1
  with:
    dest_dir: config          # engine: ssh → absolute path on the target host
    template: env.example
    output: .env
    mode: "0600"
    on_missing: fail
    backup_keep: 3
  env:
    BUZV_POSTGRES_PASSWORD: ${secrets.POSTGRES_PASSWORD}
    BUZV_SMTP_PASSWORD: ${secrets.SMTP_PASSWORD}
```

Every `${secrets.NAME}` the template references must map to an environment variable named `<values_prefix><NAME>` (default prefix `BUZV_`). A referenced name whose variable is **unset** counts as missing: `on_missing: fail` (the default) names the reference and refuses the render (no silent empty values); `warn` writes the key empty, annotates the file with a `# WARNING` comment, and lists the missing references on stderr; `blank` writes the key empty quietly. A mapped-but-empty value renders empty — it is not treated as missing.

## Semantics (matches the kernel render)

- Values must be **single-line**; a mapped multi-line value is rejected (exit 5) instead of silently corrupting the dotenv layout. Double-quoted values keep their inner text verbatim.
- Substitution is **single-pass**: values are never re-scanned for `${secrets.…}` placeholders.
- `${vars.X}` placeholders are **not** expanded by this plugin (the kernel render supported them) — bake variable values into the template at bundle time.
- Output is written atomically (temp file + rename) with `mode` (default `0600`); a previously existing output rotates into `output.bak.1 … output.bak.N` (`backup_keep`, `0` disables). Change detection uses `cmp` (no `sha256sum` dependency).
- Secret values never appear in step logs: they transit the `env:` channel, which the Manager masks (`secret_env_keys`).

## Version history

| Version | Notes |
|---|---|
| 1.0.0 | `values:` input channel. Superseded — the current validator requires masking inputs to be a single `${secrets.NAME}` reference, which a multi-line `values:` cannot satisfy. Kept only for pipelines pinned to it. |
| 1.1.0 | Env channel (`values_prefix`). Bash-only (`declare -A`, herestrings — failed on dash and macOS `/bin/sh`); `on_missing` never fired (every discovered reference was pre-seeded into its lookup map); the `: "${VAR:-x}"` default guards were no-ops. Kept only for pipelines pinned to it. |
| 1.1.1 | POSIX sh rewrite (dash/ash/bash 3+); `on_missing` enforced; real script-side defaults; multi-line values rejected; `cmp`-based change detection. Execution-level tests live in `tests/test_scripts.py::EnvRenderTests`. |

## Spec note

The spec sets `processes_secret_placeholders: true` — this plugin matches `${secrets.NAME}` placeholder **text** inside external template files (values themselves flow through the masked `env:` channel). The flag is the validator's opt-in that permits the placeholder literal in the `run` block.

## Pairing

Typically preceded by [`buz/config-fetch`](../config-fetch) (bundle download + unpack), with this step rendering the unpacked `env.example`.
