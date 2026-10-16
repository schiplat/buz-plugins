# Config fetch

Downloads a configuration bundle (`.tar.gz`) and unpacks it — the delivery half of the Config Block flow, for pipelines that keep their config in object storage. Dual engine, declared via `engines: [shell, ssh]`:

- **`engine: shell` (default)** — unpacks into a **relative** `dest` inside the Runner job workspace; requires `curl` and `tar` on the runner host.
- **`engine: ssh`** — unpacks into an **absolute** `dest` on each target host (`host:` list); the target hosts pull directly and need `curl`, `tar`, and egress to the storage endpoint.

## Authentication samples

All credential inputs (`url`, `password`, `headers`) are masked. Pick **one** method per step.

### 1. Presigned URL (recommended — no credentials in the pipeline at all)

```yaml
- name: fetch config
  uses: buz/config-fetch@1.1.0
  with:
    url: ${secrets.CONFIG_BUNDLE_URL}   # auth is embedded in the signed URL
    dest: config
```

Generate/refresh the signed URL per deploy — OSS, S3, MinIO, and R2 all issue them:

```bash
ossutil sign oss://<bucket>/config_tpl/<app>/<tag>/configs.tar.gz
aws s3 presign s3://<bucket>/config_tpl/<app>/<tag>/configs.tar.gz --expires-in 3600
```

### 2. HTTP Basic (1.1.0+) — artifact servers like Nexus / Artifactory

```yaml
- name: fetch config
  uses: buz/config-fetch@1.1.0
  with:
    url: https://nexus.example.com/repository/raw/configs.tar.gz
    username: ${secrets.ARTIFACT_USER}
    password: ${secrets.ARTIFACT_PASSWORD}
    dest: config
```

`username` and `password` must be set together. Credentials are delivered via a curl config file — never CLI arguments.

### 3. Bearer token (1.1.0+)

```yaml
- name: fetch config
  uses: buz/config-fetch@1.1.0
  with:
    url: https://api.example.com/artifacts/configs.tar.gz
    headers: "Authorization: Bearer ${secrets.ARTIFACT_TOKEN}"
    dest: config
```

### 4. Multiple custom headers (1.1.0+) — e.g. API key + request signing

```yaml
- name: fetch config
  uses: buz/config-fetch@1.1.0
  with:
    url: https://api.example.com/artifacts/configs.tar.gz
    headers: |
      Authorization: Bearer ${secrets.ARTIFACT_TOKEN}
      X-Api-Key: ${secrets.ARTIFACT_KEY}
    dest: config
```

`headers` accepts multiple lines — each non-empty line is passed as a single curl `-H`, and every line is masked in logs.

### 5. Bucket AK/SK direct — planned (tool image)

Native `ossutil` / `aws cli` downloads with raw access keys are deferred until the tool-image channel ships. Today, generate a presigned URL with your AK/SK instead (`ossutil sign` uses them server-side) — same result, no credentials on the Runner.

## Notes

- `url` is masked. `dest` semantics follow the engine (relative workspace path on shell; absolute target path on ssh).
- `strip_components` maps to `tar --strip-components`, `max_time` to the curl download timeout.
- `username` and `password` must be set together; header values with leading/trailing whitespace are trimmed by curl's config parser.
- Pair with a `config.render` block on later steps (render-only mode) to render `.env` files from the unpacked templates.
