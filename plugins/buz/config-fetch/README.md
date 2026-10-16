# Config fetch

Downloads a configuration bundle (`.tar.gz`) and unpacks it — the delivery half of the Config Block flow, for pipelines that keep their config in object storage. Dual engine, declared via `engines: [shell, ssh]`:

- **`engine: shell` (default)** — unpacks into a **relative** `dest` inside the Runner job workspace; requires `curl` and `tar` on the runner host.
- **`engine: ssh`** — unpacks into an **absolute** `dest` on each target host (`host:` list); the target hosts pull directly and need `curl`, `tar`, and egress to the storage endpoint.

```yaml
- name: fetch config
  uses: buz/config-fetch@1.0.0
  with:
    url: ${secrets.CONFIG_BUNDLE_URL}
    dest: config            # shell: workspace-relative

- name: fetch config on target
  uses: buz/config-fetch@1.0.0
  engine: ssh               # target-host filesystem
  host:
    - web-01
  with:
    url: ${secrets.CONFIG_BUNDLE_URL}
    dest: /opt/app          # ssh: absolute
```

## Authentication

| Method | Support | How |
|---|---|---|
| Presigned URL (recommended) | ✅ | Auth is embedded in the URL — OSS, S3, MinIO, and R2 all issue them (`ossutil sign oss://<bucket>/<key>` / `aws s3 presign s3://<bucket>/<key> --expires-in 3600`). Refresh the `url` secret per deploy; no bucket credentials ever appear in the pipeline. |
| HTTP Basic | ✅ (1.1.0+) | `username` + `password` inputs (both masked) — delivered via a curl config file, never a CLI argument. |
| Bearer / custom headers | ✅ (1.1.0+) | `headers` input (masked) — one curl header per line, e.g. `Authorization: Bearer <token>`. |
| Bucket AK/SK direct | planned (tool image) | Deferred until the tool-image channel ships. |

`url` is masked. `dest` semantics follow the engine (relative workspace path on shell; absolute target path on ssh). `strip_components` maps to `tar --strip-components`, `max_time` to the curl download timeout. 
Authenticated example:

```yaml
- name: fetch config (authenticated)
  uses: buz/config-fetch@1.1.0
  with:
    url: ${secrets.ARTIFACT_URL}
    username: ${secrets.ARTIFACT_USER}      # or omit user/password and use headers
    password: ${secrets.ARTIFACT_PASSWORD}  # e.g. headers: "Authorization: Bearer ${secrets.TOKEN}"
    dest: config
```

`username` and `password` must be set together. `headers` accepts multiple lines; values are written to a curl config file (never CLI arguments). Note: values with leading/trailing whitespace are trimmed by curl's config parser.

Pair with a `config.render` block on later steps (render-only mode) to render `.env` files from the unpacked templates.
