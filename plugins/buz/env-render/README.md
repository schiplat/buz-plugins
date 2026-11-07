# Env render

Expands a dotenv-style template (`env.example`) into an env file, substituting `${secrets.NAME}` placeholders from **explicit `with:` values** — the plugin form of the kernel `config.render` block. Secrets are declared where they are used (GHA-style), masked in logs, and the substitution happens where the file lives. Dual engine, declared via `engines: [shell, ssh]`:

- **`engine: shell` (default)** — renders into a **relative** `dest_dir` inside the Runner job workspace.
- **`engine: ssh`** — renders into an **absolute** `dest_dir` on each target host (`host:` list); bash required there.

## Usage

```yaml
- name: render env
  uses: buz/env-render@1.0.0
  engine: ssh
  host: $deploy_host
  with:
    dest_dir: /opt/manager
    template: env.example
    output: .env
    mode: "0600"
    on_missing: fail
    values: |
      POSTGRES_PASSWORD=${secrets.POSTGRES_PASSWORD}
      SMTP_PASSWORD=${secrets.SMTP_PASSWORD}
      TURNSTILE_SITEKEY=${secrets.TURNSTILE_SITEKEY}
```

Every `${secrets.NAME}` the template references **must** have a `values` line — `on_missing: fail` names the missing reference and refuses the render (no silent empty values). `warn` writes the key empty, annotates the file with a `# WARNING` comment, and lists the missing references on stderr; `blank` writes the key empty quietly.

## Semantics (matches the kernel render)

- Values are single-line; double-quoted values keep their inner text verbatim. Multiline values are not supported in 1.0.0.
- `${vars.X}` placeholders are **not** expanded by this plugin (kernel render supported them) — bake variable values into the template at bundle time.
- Output is written atomically (temp file + rename) with `mode` (default `0600`); a previously existing output rotates into `output.bak.1 … output.bak.N` (`backup_keep`, `0` disables).
- `values` is a masked input: the expanded secret values never appear in step logs.

## Spec note

The spec sets `processes_secret_placeholders: true` — this plugin matches `${secrets.NAME}` placeholder **text** inside external template files (it never consumes Buz-side secret values directly; values flow through the masked `values` input). The flag is the validator's opt-in that permits the placeholder literal in the `run` block and requires a masked input.

## Pairing

Typically preceded by [`buz/config-fetch`](../config-fetch) (bundle download + unpack), with this step rendering the unpacked `env.example`.
